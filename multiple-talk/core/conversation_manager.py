# conversation_manager.py
import os
import time
from enum import Enum, auto
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from core.step import Step
from core.interfaces import TTSInterface, ASRInterface, TEMP_AUDIO_DIR
from audio.worker import AudioPlayer, AudioRecorder

class State(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    PLAYING_TTS = auto()
    WAITING_FOR_TTS_SYNTHESIS = auto()
    RECORDING_ASR = auto()
    WAITING_FOR_ASR_RECOGNITION = auto()
    FINISHED = auto()
    STOPPED = auto()
    ERROR = auto()

class ConversationManager(QObject):
    """管理对话流程、状态和与TTS/ASR模块的交互"""

    # --- Signals ---
    # 流程控制信号
    stateChanged = Signal(State)        # 状态变更信号
    conversationStarted = Signal()      # 对话流程开始
    conversationPaused = Signal()       # 对话流程暂停
    conversationResumed = Signal()      # 对话流程恢复
    conversationStopped = Signal()      # 对话流程停止 (手动或错误)
    conversationFinished = Signal()     # 对话流程正常完成

    # 步骤相关信号
    stepAdded = Signal(int)             # 步骤已添加 (索引)
    stepRemoved = Signal(int)           # 步骤已移除 (索引)
    stepMoved = Signal(int, int)        # 步骤已移动 (旧索引, 新索引)
    stepListChanged = Signal()          # 整个步骤列表发生变化 (通用)

    stepExecutionStarting = Signal(int) # 即将开始执行某一步骤 (索引)
    stepExecutionFinished = Signal(int, bool, str) # 步骤执行完成 (索引, 是否成功, ASR结果或错误信息)
    stepStatusUpdated = Signal(int, str) # 更新某个步骤的状态显示 (索引, 状态文本)
    stepResultUpdated = Signal(int, str) # 更新某个步骤的ASR结果 (索引, 结果文本)

    # TTS 相关信号
    ttsPlaybackProgress = Signal(int)   # TTS 播放进度 (百分比)
    ttsPlaybackStateChanged = Signal(bool) # TTS 是否正在播放 (True/False)

    # ASR 相关信号
    asrRecordingStarted = Signal()      # ASR 录音开始
    asrRecordingStopped = Signal(str)   # ASR 录音停止 (文件名)
    asrRecordingFailed = Signal(str)    # ASR 录音失败 (错误信息)
    asrRecognitionResult = Signal(int, str) # ASR 识别结果 (步骤索引, 结果文本) - 实时更新用
    asrRecognitionFailed = Signal(int, str) # ASR 识别失败 (步骤索引, 错误信息)


    def __init__(self, tts_api: TTSInterface, asr_api: ASRInterface, parent=None):
        super().__init__(parent)
        self.steps: list[Step] = []
        self.current_step_index: int = -1
        self._state: State = State.IDLE

        self.tts_api = tts_api
        self.asr_api = asr_api

        # 工作器实例 (在需要时创建)
        self.audio_player = AudioPlayer() # QMediaPlayer 可以在主线程控制
        self.audio_recorder: AudioRecorder | None = None

        # 连接播放器的信号
        self.audio_player.finished.connect(self._on_tts_playback_finished)
        self.audio_player.error.connect(self._on_tts_playback_error)
        self.audio_player.positionChanged.connect(self.ttsPlaybackProgress) # 直接转发
        self.audio_player.stateChanged.connect(self._on_playback_state_changed)

        # 配置项
        self.auto_proceed_after_step = True # 每个步骤完成后是否自动进行下一步
        self.trigger_asr_after_tts_delay_ms = 150 # TTS播放结束后到触发ASR的延迟(ms)，满足<200ms要求

    # --- 状态管理 ---
    def _set_state(self, new_state: State):
        if self._state != new_state:
            print(f"[Manager] 状态改变: {self._state.name} -> {new_state.name}")
            self._state = new_state
            self.stateChanged.emit(self._state)

    def get_state(self) -> State:
        return self._state

    # --- 步骤管理 ---
    def add_step(self, step_type: str, content: str = "", duration: float | None = None):
        """添加新步骤到末尾"""
        if step_type not in ["TTS", "ASR"]:
            print(f"[Manager] 错误：无效的步骤类型 {step_type}")
            return

        new_step = Step(step_type=step_type, content=content, duration=duration)
        self.steps.append(new_step)
        print(f"[Manager] 添加步骤 {len(self.steps)}: {new_step}")
        self.stepAdded.emit(len(self.steps) - 1)
        self.stepListChanged.emit() # 通知列表整体变化

    def remove_step(self, index: int):
        """移除指定索引的步骤"""
        if 0 <= index < len(self.steps):
            removed_step = self.steps.pop(index)
            print(f"[Manager] 移除步骤 {index}: {removed_step}")
            # 如果移除的是正在进行的步骤，需要停止流程
            if self._state != State.IDLE and self.current_step_index == index:
                print("[Manager] 正在执行的步骤被移除，停止流程！")
                self.stop_conversation() # 停止并重置
            elif self._state != State.IDLE and self.current_step_index > index:
                 self.current_step_index -= 1 # 调整当前索引
            self.stepRemoved.emit(index)
            self.stepListChanged.emit()
        else:
            print(f"[Manager] 错误：移除步骤索引无效 {index}")

    def move_step(self, old_index: int, new_index: int):
         """移动步骤"""
         if not (0 <= old_index < len(self.steps) and 0 <= new_index < len(self.steps)):
             print(f"[Manager] 错误：移动步骤索引无效 {old_index} -> {new_index}")
             return
         if old_index == new_index:
             return

         step = self.steps.pop(old_index)
         self.steps.insert(new_index, step)
         print(f"[Manager] 移动步骤: {old_index} -> {new_index}")

         # 如果移动影响了当前执行位置，需要调整 current_step_index
         if self._state != State.IDLE:
             if self.current_step_index == old_index:
                 self.current_step_index = new_index # 跟随移动
             elif old_index < self.current_step_index <= new_index:
                 self.current_step_index -= 1 # 向前移动，当前项被挤后了
             elif new_index <= self.current_step_index < old_index:
                 self.current_step_index += 1 # 向后移动，当前项被挤前了

         self.stepMoved.emit(old_index, new_index)
         self.stepListChanged.emit()

    def get_steps(self) -> list[Step]:
        """获取所有步骤"""
        return self.steps

    def clear_steps(self):
        """清空所有步骤"""
        if self._state != State.IDLE:
            self.stop_conversation()
        self.steps = []
        self.current_step_index = -1
        print("[Manager] 所有步骤已清空")
        self.stepListChanged.emit()


    # --- 流程控制 ---
    def start_conversation(self):
        """开始或恢复对话流程"""
        if not self.steps:
            print("[Manager] 无法开始：步骤列表为空。")
            return

        if self._state == State.IDLE or self._state == State.FINISHED or self._state == State.STOPPED or self._state == State.ERROR:
            print("[Manager] 开始对话流程...")
            self.current_step_index = -1 # 从头开始
            self._reset_steps_status() # 重置所有步骤状态
            self._set_state(State.RUNNING)
            self.conversationStarted.emit()
            self._execute_next_step()
        elif self._state == State.PAUSED:
            print("[Manager] 恢复对话流程...")
            self._set_state(State.RUNNING)
            self.conversationResumed.emit()
            # 根据暂停前的状态决定如何恢复
            last_state_before_pause = self._paused_from_state # 需要一个变量记录暂停前的状态
            print(f"[Manager] 从暂停状态 {last_state_before_pause} 恢复")
            if last_state_before_pause == State.PLAYING_TTS:
                 # 如果暂停时正在播放TTS，尝试恢复播放
                 print("[Manager] 恢复TTS播放")
                 self.audio_player.play()
            elif last_state_before_pause == State.RECORDING_ASR:
                 # 如果暂停时在录音，理论上不允许暂停录音（或很难完美续录），通常是停止
                 # 这里假设暂停=停止当前步骤，然后继续下一个。或者需要重新录制？
                 # 简化处理：从暂停恢复时，如果之前在录音，则认为该步骤失败或跳过，执行下一步
                 print("[Manager] 从暂停恢复（之前在录音），跳过当前ASR步骤，执行下一步。")
                 self._mark_step_finished(self.current_step_index, False, "因暂停而跳过")
                 QTimer.singleShot(100, self._execute_next_step) # 短暂延迟后执行下一步
            else:
                 # 其他情况（如步骤间隙暂停），直接尝试执行下一步
                 self._execute_next_step()

        else:
            print(f"[Manager] 无法在状态 {self._state.name} 下开始/恢复流程。")

    def pause_conversation(self):
        """暂停对话流程"""
        if self._state in [State.RUNNING, State.PLAYING_TTS, State.RECORDING_ASR, State.WAITING_FOR_ASR_RECOGNITION, State.WAITING_FOR_TTS_SYNTHESIS]:
            print(f"[Manager] 暂停对话流程 (当前状态: {self._state.name})")
            self._paused_from_state = self._state # 记录暂停前的状态

            # 根据当前活动暂停
            if self._state == State.PLAYING_TTS:
                self.audio_player.pause()
            elif self._state == State.RECORDING_ASR:
                # 停止录音，因为暂停录音通常不实用
                self.stop_asr_recording_manual() # 手动停止录音线程
                # 状态会在录音停止后处理

            # 停止可能在进行的后台任务（如果它们可以被中断的话）
            # TODO: 考虑是否需要取消 TTS 合成或 ASR 识别任务

            self._set_state(State.PAUSED)
            self.conversationPaused.emit()
        else:
            print(f"[Manager] 无法在状态 {self._state.name} 下暂停流程。")

    def stop_conversation(self):
        """停止对话流程"""
        if self._state != State.IDLE and self._state != State.STOPPED:
            print("[Manager] 停止对话流程...")
            original_state = self._state

            # 停止所有活动
            if original_state == State.PLAYING_TTS:
                self.audio_player.stop()
            if original_state == State.RECORDING_ASR and self.audio_recorder: # Check if recorder exists
                # Check if running before trying to stop
                if self.audio_recorder.isRunning():
                    self.stop_asr_recording_manual()
                else:
                     # Recorder exists but wasn't running (maybe stopped between check and now)
                     print("[Manager] Stop requested, but recorder was not running.")
            # TODO: 考虑取消后台任务 (TTS Synthesis, ASR Recognition) - tricky

            # Ensure state is set to STOPPED
            self._set_state(State.STOPPED) # Uses the now defined State.STOPPED
            self.conversationStopped.emit()
            # Reset pending actions if any
            self._pending_playback_file = None
            self._pending_recognition_file = None
        else:
            print(f"[Manager] 流程未运行或已停止。")


    def _reset_steps_status(self):
        """重置所有步骤的状态为 '待处理'"""
        for i, step in enumerate(self.steps):
            if step.status != "待处理":
                step.status = "待处理"
                step.result = None
                step.audio_file = None
                self.stepStatusUpdated.emit(i, step.status)
                if step.step_type == "ASR":
                    self.stepResultUpdated.emit(i, "") # 清空旧结果显示


    # --- 步骤执行核心逻辑 ---
    def _execute_next_step(self):
        """执行流程中的下一步"""
        if self._state != State.RUNNING:
            # print(f"[Manager] 状态不是 RUNNING ({self._state.name})，不执行下一步。")
            # 如果是刚完成一步，状态可能是 PLAYING/RECORDING 等，需要判断是否继续
             if self._state not in [State.PLAYING_TTS, State.RECORDING_ASR, State.WAITING_FOR_ASR_RECOGNITION, State.WAITING_FOR_TTS_SYNTHESIS]:
                 print(f"[Manager] 状态 ({self._state.name}) 不适合执行下一步。")
                 # 如果是因为错误或停止导致，则不应继续
                 if self._state in [State.ERROR, State.STOPPED]:
                      return
                 # 如果是暂停，等待恢复
                 if self._state == State.PAUSED:
                      return
                 # 如果是完成，则标记完成
                 if self._state == State.FINISHED:
                      self.conversationFinished.emit()
                      return
                 # 其他意外情况
                 print(f"[Manager] 意外状态 {self._state.name}，尝试重置为 IDLE")
                 self._set_state(State.IDLE)
                 return


        self.current_step_index += 1
        print(f"[Manager] 尝试执行步骤索引: {self.current_step_index}")

        if self.current_step_index < len(self.steps):
            current_step = self.steps[self.current_step_index]
            print(f"[Manager] 执行步骤 {self.current_step_index}: {current_step.step_type} - {current_step.content[:30] if current_step.content else '(无内容)'}")
            self.stepExecutionStarting.emit(self.current_step_index)
            current_step.status = "进行中"
            self.stepStatusUpdated.emit(self.current_step_index, current_step.status)


            if current_step.step_type == "TTS":
                self._handle_tts_step(current_step)
            elif current_step.step_type == "ASR":
                self._handle_asr_step(current_step)
            else:
                error_msg = f"未知步骤类型: {current_step.step_type}"
                print(f"[Manager] 错误: {error_msg}")
                self._mark_step_finished(self.current_step_index, False, error_msg)
                self._proceed_or_finish() # 尝试继续

        else:
            # 所有步骤完成
            print("[Manager] 对话流程执行完毕。")
            self._set_state(State.FINISHED)
            self.conversationFinished.emit()

    def _handle_tts_step(self, step: Step):
        """处理TTS步骤：合成 -> 播放"""
        self._set_state(State.WAITING_FOR_TTS_SYNTHESIS)
        filename = os.path.join(TEMP_AUDIO_DIR, f"tts_{step.id}.wav")
        step.status = "合成中..."
        self.stepStatusUpdated.emit(self.current_step_index, step.status)

        # 使用异步合成
        synthesis_task = self.tts_api.synthesize_async(step.content, filename)
        if synthesis_task:
             # 连接当前这次任务的完成信号
             synthesis_task.signals.finished.connect(self._on_tts_synthesis_finished)
        else:
             # 如果异步任务启动失败
             error_msg = "启动TTS合成任务失败"
             print(f"[Manager] 错误: {error_msg}")
             self._mark_step_finished(self.current_step_index, False, error_msg)
             self._set_state(State.ERROR) # 进入错误状态
             self.conversationStopped.emit() # 通知停止


    @Slot(str, bool)
    def _on_tts_synthesis_finished(self, audio_filename: str, success: bool):
        """TTS合成完成后的回调"""
        # 检查是否还在处理这个步骤
        if self._state != State.WAITING_FOR_TTS_SYNTHESIS or self.current_step_index >= len(self.steps) or self.steps[self.current_step_index].audio_file == audio_filename:
            print(f"[Manager] TTS合成完成信号 '{audio_filename}' 到达，但状态已改变或步骤不匹配，忽略。")
            # 可能已经被停止或移除了步骤
            # 如果是因为停止，状态已经是 STOPPED 或 IDLE
            # 如果移除步骤， current_step_index 可能变化
            # 如果是旧任务信号，也忽略
            # 这里简单处理，直接返回
            return


        current_step = self.steps[self.current_step_index]
        if success:
            print(f"[Manager] TTS 合成成功: {audio_filename}")
            current_step.audio_file = audio_filename
            current_step.status = "准备播放"
            self.stepStatusUpdated.emit(self.current_step_index, current_step.status)
            self._play_tts_audio(audio_filename)
        else:
            error_msg = "TTS 合成失败"
            print(f"[Manager] 错误: {error_msg}")
            self._mark_step_finished(self.current_step_index, False, error_msg)
            self._set_state(State.ERROR)
            self.conversationStopped.emit() # 失败则停止流程

    def _play_tts_audio(self, audio_filename: str):
        """播放TTS生成的音频"""
        if self._state not in [State.RUNNING, State.WAITING_FOR_TTS_SYNTHESIS]: # 检查状态是否允许播放
             print(f"[Manager] 状态 ({self._state.name}) 不允许播放TTS，取消播放。")
             # 可能是被暂停或停止了
             if self._state == State.PAUSED:
                  # 记录需要播放的文件，等待恢复
                  self._pending_playback_file = audio_filename
                  print(f"[Manager] 流程已暂停，将文件 {audio_filename} 标记为待播放。")
             # else: # STOPPED or ERROR, do nothing
             return

        print(f"[Manager] 准备播放TTS音频: {audio_filename}")
        self._set_state(State.PLAYING_TTS)
        current_step = self.steps[self.current_step_index]
        current_step.status = "播放中"
        self.stepStatusUpdated.emit(self.current_step_index, current_step.status)
        self.audio_player.set_source(audio_filename)
        self.audio_player.play()


    @Slot()
    def _on_tts_playback_finished(self):
        """TTS音频播放完成后的回调"""
        # 确保是在播放TTS的状态下完成的
        if self._state == State.PLAYING_TTS:
            print("[Manager] TTS 播放完成.")
            self._mark_step_finished(self.current_step_index, True)

            # 检查完成后是否需要自动触发ASR (如果下一 P 步是ASR) - 这是文档要求
            next_index = self.current_step_index + 1
            if next_index < len(self.steps) and self.steps[next_index].step_type == 'ASR':
                 print(f"[Manager] TTS播放完毕，延时 {self.trigger_asr_after_tts_delay_ms}ms 后自动触发下一步ASR。")
                 self._set_state(State.RUNNING) # 转回RUNNING状态准备下一步
                 QTimer.singleShot(self.trigger_asr_after_tts_delay_ms, self._execute_next_step)
            else:
                # 如果下一步不是ASR或已经是最后一步，则按常规流程处理
                self._proceed_or_finish()
        else:
             print(f"[Manager] 接收到播放完成信号，但当前状态为 {self._state.name}，忽略。")


    @Slot(str)
    def _on_tts_playback_error(self, error_string: str):
        """TTS音频播放错误处理"""
        if self._state == State.PLAYING_TTS:
            error_msg = f"TTS 播放失败: {error_string}"
            print(f"[Manager] 错误: {error_msg}")
            self._mark_step_finished(self.current_step_index, False, error_msg)
            self._set_state(State.ERROR)
            self.conversationStopped.emit() # 播放失败通常意味着流程中断
        else:
            print(f"[Manager] 接收到播放错误信号，但状态非播放 ({self._state.name})，忽略。")


    @Slot(QMediaPlayer.PlaybackState)
    def _on_playback_state_changed(self, state):
         """监听播放器状态变化，主要用于更新UI的播放状态"""
         is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
         self.ttsPlaybackStateChanged.emit(is_playing)
         # 如果从播放中变成暂停，且manager状态是PLAYING_TTS，则manager也要进入PAUSED
         if state == QMediaPlayer.PlaybackState.PausedState and self._state == State.PLAYING_TTS:
              print("[Manager] 检测到播放器暂停，将Manager状态同步为PAUSED")
              self.pause_conversation() # 调用pause来处理状态转换


    def _handle_asr_step(self, step: Step):
        """处理ASR步骤：启动录音"""
        self._set_state(State.RECORDING_ASR)
        step.status = "等待录音"
        self.stepStatusUpdated.emit(self.current_step_index, step.status)

        # 创建录音器实例 (每次都创建新的，确保状态干净)
        # 如果之前的录音器还在运行（理论上不应该），先尝试停止
        if self.audio_recorder and self.audio_recorder.isRunning():
            print("[Manager] 警告：之前的录音器似乎还在运行，尝试停止...")
            self.audio_recorder.stop_recording()
            self.audio_recorder.wait(1000) # 等待一小段时间

        filename = f"asr_{step.id}.wav"
        self.audio_recorder = AudioRecorder(filename=filename, duration=step.duration)

        # 连接信号
        self.audio_recorder.recording_started.connect(self._on_asr_recording_started)
        self.audio_recorder.recording_stopped.connect(self._on_asr_recording_stopped)
        self.audio_recorder.recording_failed.connect(self._on_asr_recording_failed)
        # self.audio_recorder.update_meter.connect(...) # 可选：连接音量信号

        print(f"[Manager] 启动ASR录音，时长限制: {step.duration} 秒")
        self.audio_recorder.start() # 启动录音线程

    @Slot()
    def _on_asr_recording_started(self):
        """录音实际开始后的回调"""
        if self._state == State.RECORDING_ASR:
             print("[Manager] ASR 录音已开始.")
             current_step = self.steps[self.current_step_index]
             current_step.status = "录音中..."
             self.stepStatusUpdated.emit(self.current_step_index, current_step.status)
             self.asrRecordingStarted.emit()
        else:
             print("[Manager] 收到录音开始信号，但状态不匹配，可能已停止或改变。")
             # 如果状态不对，尝试停止刚启动的录音器
             if self.audio_recorder and self.audio_recorder.isRunning():
                 self.audio_recorder.stop_recording()


    def stop_asr_recording_manual(self):
        """手动停止ASR录音"""
        if self._state == State.RECORDING_ASR and self.audio_recorder and self.audio_recorder.isRunning():
            print("[Manager] 手动请求停止 ASR 录音...")
            self.audio_recorder.stop_recording()
            # 状态转换和后续处理将在 recording_stopped 信号中进行
        else:
            print("[Manager] 无法手动停止录音：状态不正确或录音器未运行。")

    @Slot(str)
    def _on_asr_recording_stopped(self, audio_filename: str):
        """录音停止（正常完成或手动停止）后的回调"""
         # 检查状态是否是录音中或者暂停（因为暂停时也可能调用stop）
        if self._state == State.RECORDING_ASR or self._state == State.PAUSED:
            print(f"[Manager] ASR 录音已停止. 文件: {audio_filename}")
            self.asrRecordingStopped.emit(audio_filename) # 通知UI录音结束

            # 检查文件是否存在且有效
            if not audio_filename or not os.path.exists(audio_filename) or os.path.getsize(audio_filename) <= 44: # 44是WAV头大小
                 error_msg = "录音文件无效或为空"
                 print(f"[Manager] 错误: {error_msg}")
                 self._mark_step_finished(self.current_step_index, False, error_msg)
                 # 如果是因为暂停导致的停止，状态已经是PAUSED，不需要改
                 # 如果是正常录音但文件无效，进入ERROR状态
                 if self._state != State.PAUSED:
                     self._set_state(State.ERROR)
                     self.conversationStopped.emit()
                 return # 不进行识别


            current_step = self.steps[self.current_step_index]
            current_step.audio_file = audio_filename
            current_step.status = "识别中..."
            self.stepStatusUpdated.emit(self.current_step_index, current_step.status)

            # 如果当前是暂停状态，则不启动识别，等待恢复
            if self._state == State.PAUSED:
                 print("[Manager] 流程已暂停，录音文件已保存，等待恢复后识别。")
                 self._pending_recognition_file = audio_filename
                 return

            # 启动 ASR 识别
            self._set_state(State.WAITING_FOR_ASR_RECOGNITION)
            recognition_task = self.asr_api.recognize_async(audio_filename)
            if recognition_task:
                 recognition_task.signals.finished.connect(self._on_asr_recognition_finished)
            else:
                 error_msg = "启动ASR识别任务失败"
                 print(f"[Manager] 错误: {error_msg}")
                 self._mark_step_finished(self.current_step_index, False, error_msg)
                 self._set_state(State.ERROR)
                 self.conversationStopped.emit()
        else:
             print(f"[Manager] 收到录音停止信号，但状态 ({self._state.name}) 不匹配，忽略。")


    @Slot(str)
    def _on_asr_recording_failed(self, error_string: str):
        """录音失败后的回调"""
        if self._state == State.RECORDING_ASR:
            error_msg = f"ASR 录音失败: {error_string}"
            print(f"[Manager] 错误: {error_msg}")
            self.asrRecordingFailed.emit(error_msg)
            self._mark_step_finished(self.current_step_index, False, error_msg)
            self._set_state(State.ERROR)
            self.conversationStopped.emit()
        else:
             print(f"[Manager] 收到录音失败信号，但状态 ({self._state.name}) 不匹配，忽略。")

    @Slot(str, str)
    def _on_asr_recognition_finished(self, audio_filename: str,
                                     result_text: str):
        """ASR识别完成后的回调"""
        # Handle pause state first
        if self._state == State.PAUSED and self._paused_from_state == State.WAITING_FOR_ASR_RECOGNITION:
            print(
                f"[Manager] ASR识别在暂停期间完成. 文件: {audio_filename}, 结果: '{result_text}'. 等待恢复...")
            if self.current_step_index >= 0 and self.steps[
                self.current_step_index].audio_file == audio_filename:
                step = self.steps[self.current_step_index]
                success = bool(result_text)  # Empty string is False
                step.result = result_text if success else "[识别失败]"
                step.status = "已完成 (暂停中)" if success else "失败 (暂停中)"
                self.asrRecognitionResult.emit(self.current_step_index,
                                               step.result)
                self.stepResultUpdated.emit(self.current_step_index,
                                            step.result)
                self.stepStatusUpdated.emit(self.current_step_index,
                                            step.status)
            return  # Wait for resume
        # Check if state is correct
        if self._state != State.WAITING_FOR_ASR_RECOGNITION:
            print(
                f"[Manager] ASR识别完成信号到达，但状态 ({self._state.name}) 不匹配，忽略。")
            return

        # Check filename match
        current_audio_file = self.steps[
            self.current_step_index].audio_file if self.current_step_index < len(
            self.steps) else None
        if self.current_step_index >= len(
                self.steps) or not current_audio_file or os.path.normpath(
                current_audio_file) != os.path.normpath(audio_filename):
            print(
                f"[Manager] ASR识别完成信号到达，但文件名 ({audio_filename}) 与当前步骤 ({current_audio_file}) 不符，忽略。")
            return

        current_step = self.steps[self.current_step_index]

        # --- !!! MODIFY THIS CONDITION !!! ---
        # if result_text is not None: # <--- INCORRECT CHECK
        if result_text:  # <--- CORRECT CHECK (non-empty string means success)
            # --- Success Path ---
            print(f"[Manager] ASR 识别成功: '{result_text}'")
            current_step.result = result_text
            self.asrRecognitionResult.emit(self.current_step_index,
                                           result_text)
            self.stepResultUpdated.emit(self.current_step_index,
                                        result_text)
            self._mark_step_finished(self.current_step_index, True,
                                     result_text)
        else:
            # --- Failure Path (result_text is "") ---
            error_msg = "ASR 识别失败 (空结果)"  # More specific message
            print(f"[Manager] 错误: {error_msg}")
            current_step.result = "[识别失败]"
            # Use detail_str in the emit call below for consistency
            # self.asrRecognitionFailed.emit(self.current_step_index, error_msg) # This signal might be redundant now
            self.stepResultUpdated.emit(self.current_step_index,
                                        current_step.result)
            # Pass the specific error message to _mark_step_finished
            self._mark_step_finished(self.current_step_index, False,
                                     error_msg)

        # Proceed regardless of success/failure (unless configured otherwise)
        self._proceed_or_finish()


    def _mark_step_finished(self, index: int, success: bool, result_or_error: str | None = None):
        """标记一个步骤完成，并发出信号"""
        if 0 <= index < len(self.steps):
            step = self.steps[index]
            step.status = "已完成" if success else "失败"
            status_detail = result_or_error if result_or_error else ("成功" if success else "失败")
            print(f"[Manager] 步骤 {index} 完成，状态: {step.status}, 详情: {status_detail}")
            self.stepStatusUpdated.emit(index, step.status)

            # Prepare the string argument for the signal (use empty string if None)
            detail_str = result_or_error if result_or_error is not None else ""
            # The emit call is now correct because the signal definition matches
            self.stepExecutionFinished.emit(index, success, detail_str)
        else:
             print(f"[Manager] 尝试标记完成的步骤索引 {index} 无效。")


    def _proceed_or_finish(self):
        """决定是继续下一步还是结束流程"""
        # 检查当前状态，如果已被停止/暂停/错误，则不继续
        if self._state in [State.STOPPED, State.PAUSED, State.ERROR]:
            print(f"[Manager] 状态为 {self._state.name}，不自动进行下一步。")
            # 如果是错误，确保已发停止信号
            if self._state == State.ERROR and self.get_state() != State.STOPPED: # 避免重复发信号
                 self.conversationStopped.emit()
            return

        # 如果配置了自动进行下一步
        if self.auto_proceed_after_step:
            # 延迟很短时间后执行下一步，给UI一点反应时间，并满足步骤切换<500ms的要求
            self._set_state(State.RUNNING) # 切换回准备执行的状态
            # QTimer.singleShot(50, self._execute_next_step) # 50ms 延迟
            # 发现TTS->ASR时已经有延时了，这里如果不是这种情况就直接调用
            # 检查上一步是否是TTS，下一步是否是ASR
            prev_step_finished = self.current_step_index
            next_step_index = prev_step_finished + 1
            is_tts_to_asr_transition = False
            if 0 <= prev_step_finished < len(self.steps) and next_step_index < len(self.steps):
                 if self.steps[prev_step_finished].step_type == 'TTS' and self.steps[next_step_index].step_type == 'ASR':
                      is_tts_to_asr_transition = True

            if not is_tts_to_asr_transition: # 如果不是特殊的TTS->ASR转换（那个有自己的延时）
                 print("[Manager] 步骤完成，立即准备执行下一步...")
                 # 使用 0ms 定时器将执行推迟到事件循环的下一个迭代，避免递归过深
                 QTimer.singleShot(0, self._execute_next_step)
            else:
                 print("[Manager] TTS->ASR转换已处理延时，此处不重复调用 _execute_next_step。")

        else:
            # 需要手动触发下一步，流程暂停在这里，可以认为是 PAUSED 或 IDLE?
            # 设为 PAUSED 似乎更合理，表示等待用户操作
            print("[Manager] 自动进行下一步已禁用，流程暂停，等待手动触发。")
            self._set_state(State.PAUSED) # 或者一个专门的 WAITING_FOR_USER 状态？
            self.conversationPaused.emit() # 发出暂停信号