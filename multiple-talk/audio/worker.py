# workers.py
import time
import os
import numpy as np # Import numpy
import sounddevice as sd # Import sounddevice
from scipy.io import wavfile # Import wavfile for saving numpy arrays
from PySide6.QtCore import QThread, Signal, QUrl, QObject, Slot
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

TEMP_AUDIO_DIR = "_temp_audio" # 确保目录存在
if not os.path.exists(TEMP_AUDIO_DIR):
    os.makedirs(TEMP_AUDIO_DIR)


# --- AudioPlayer class remains the same ---
class AudioPlayer(QObject):
    """使用 QMediaPlayer 播放音频 (在主线程或由Manager移交线程)"""
    started = Signal()
    finished = Signal()
    error = Signal(str)
    positionChanged = Signal(int) # 播放进度 (百分比)
    stateChanged = Signal(QMediaPlayer.PlaybackState) # 播放状态

    def __init__(self, parent=None):
        super().__init__(parent)
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.errorOccurred.connect(self._handle_error)
        self._media_player.playbackStateChanged.connect(self._handle_state_changed)
        self._media_player.positionChanged.connect(self._handle_position_changed)
        self._media_player.durationChanged.connect(self._handle_duration_changed)
        self._duration = 0

    def set_source(self, file_path: str):
        if not os.path.exists(file_path):
            self.error.emit(f"音频文件不存在: {file_path}")
            print(f"[AudioPlayer] 错误: 音频文件不存在: {file_path}")
            return
        print(f"[AudioPlayer] 设置播放源: {file_path}")
        self._media_player.setSource(QUrl.fromLocalFile(file_path))
        self._duration = self._media_player.duration()

    def play(self):
        if self._media_player.source().isEmpty():
            self.error.emit("未设置播放源")
            print("[AudioPlayer] 错误: 未设置播放源")
            return
        print("[AudioPlayer] 请求播放...")
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
             print("[AudioPlayer] 从暂停处继续播放")
        elif self._media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
             print("[AudioPlayer] 从头开始播放")
             self._media_player.setPosition(0)
        self._media_player.play()

    def pause(self):
        print("[AudioPlayer] 请求暂停")
        self._media_player.pause()

    def stop(self):
        print("[AudioPlayer] 请求停止")
        self._media_player.stop()
        self.positionChanged.emit(0)

    def _handle_error(self, error, error_string):
        print(f"[AudioPlayer] 错误: {error}, {error_string}")
        self.error.emit(f"播放错误: {error_string}")

    def _handle_state_changed(self, state):
        print(f"[AudioPlayer] 状态改变: {state}")
        self.stateChanged.emit(state)
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.started.emit()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            current_pos = self._media_player.position()
            print(f"[AudioPlayer] 停止时位置: {current_pos}, 总时长: {self._duration}")
            # Check for natural end with tolerance
            if self._duration > 0 and abs(current_pos - self._duration) < 150 : # Increased tolerance slightly
                 print("[AudioPlayer] 播放自然结束.")
                 self.finished.emit()
            else:
                 # Covers manual stop, error stop, or stop before playing fully
                 print("[AudioPlayer] 播放被手动停止、因错误停止或未完成.")
                 # Do not emit finished signal on manual/error stop here
                 pass

    def _handle_position_changed(self, position):
        if self._duration > 0:
            progress_percent = int((position / self._duration) * 100)
            self.positionChanged.emit(progress_percent)
        else:
             self.positionChanged.emit(0)

    def _handle_duration_changed(self, duration):
        print(f"[AudioPlayer] 总时长更新: {duration} ms")
        self._duration = duration


# --- Rewritten AudioRecorder using sounddevice ---
class AudioRecorder(QThread):
    """使用 sounddevice 在单独线程中录制音频"""
    recording_started = Signal()
    recording_stopped = Signal(str) # 发送录音文件路径
    recording_failed = Signal(str)  # 发送错误信息
    # update_meter = Signal(int) # Optional: Calculating volume from numpy array needs extra work

    def __init__(self, filename="recording.wav", duration=None, channels=1, rate=16000, chunk=1024, dtype='float32', parent=None):
        """
        初始化录音器。
        :param filename: 保存的文件名 (在 TEMP_AUDIO_DIR 下)。
        :param duration: 最大录音时长 (秒), None 表示手动停止。
        :param channels: 声道数。
        :param rate: 采样率 (Hz)。
        :param chunk: 每次读取的帧数 (块大小)。
        :param dtype: NumPy 数据类型 (例如 'int16', 'int32', 'float32')。
        :param parent: 父对象。
        """
        super().__init__(parent)
        self.filename = os.path.join(TEMP_AUDIO_DIR, filename)
        self.duration = duration
        self.samplerate = int(rate)
        self.channels = int(channels)
        self.blocksize = int(chunk)
        self.dtype = dtype # e.g., 'int16', 'int32', 'float32'

        self._is_running = False
        self._frames = [] # Will store numpy arrays

    def run(self):
        """线程执行体，进行录音"""
        self._is_running = True
        self._frames = []
        stream = None # Initialize stream variable

        try:
            print(f"[AudioRecorder] sounddevice: 准备录音 (Rate: {self.samplerate}, Channels: {self.channels}, DType: {self.dtype}, Blocksize: {self.blocksize})")
            # Use sounddevice InputStream
            stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.blocksize
            )

            # Use the stream as a context manager for automatic start/stop/close
            with stream:
                print("[AudioRecorder] sounddevice: 开始录音...")
                self.recording_started.emit()
                start_time = time.time()

                while self._is_running:
                    # Read audio data chunk
                    # stream.read() is blocking
                    indata, overflowed = stream.read(self.blocksize)
                    if overflowed:
                        print("[AudioRecorder] sounddevice: 警告 - 输入溢出!")
                    # Append a copy of the data
                    self._frames.append(indata.copy())

                    # Check for duration limit
                    if self.duration and (time.time() - start_time) >= self.duration:
                        print(f"[AudioRecorder] sounddevice: 达到最大录音时长 {self.duration} 秒，自动停止。")
                        self._is_running = False # Signal loop to stop
                        # break # Exit loop immediately

            print("[AudioRecorder] sounddevice: 录音流已停止/关闭.")

        except sd.PortAudioError as pae:
             error_msg = f"sounddevice PortAudio 错误: {pae}"
             print(f"[AudioRecorder] {error_msg}")
             self.recording_failed.emit(error_msg)
             self._is_running = False
        except Exception as e:
            error_msg = f"sounddevice 录音失败: {e}"
            print(f"[AudioRecorder] {error_msg}")
            self.recording_failed.emit(error_msg)
            self._is_running = False
        # finally block is not strictly needed as 'with stream:' handles cleanup

        # Check if recording should be saved (stopped normally/duration, and has frames)
        # Note: _is_running will be False if stopped via duration or stop_recording()
        if not self._is_running and self._frames:
            self.save_recording()
        elif not self._frames:
             print("[AudioRecorder] sounddevice: 没有录制到有效数据或因错误退出，不保存文件.")


    def save_recording(self):
        """使用 scipy.io.wavfile 保存录音数据到WAV文件"""
        if not self._frames:
            print("[AudioRecorder] sounddevice: 无数据帧可保存。")
            return

        print(f"[AudioRecorder] sounddevice: 准备合并和保存录音到: {self.filename}")
        try:
            # Concatenate all recorded numpy arrays
            recording_data = np.concatenate(self._frames, axis=0)
            print(f"[AudioRecorder] sounddevice: 合并后数据 shape: {recording_data.shape}, dtype: {recording_data.dtype}")

            # Save using scipy.io.wavfile
            wavfile.write(self.filename, self.samplerate, recording_data)

            print(f"[AudioRecorder] sounddevice: 录音已保存: {self.filename}")
            self.recording_stopped.emit(self.filename) # Emit signal AFTER successful save
        except Exception as e:
             error_msg = f"sounddevice 保存录音文件失败: {e}"
             print(f"[AudioRecorder] {error_msg}")
             self.recording_failed.emit(error_msg)


    def stop_recording(self):
        """外部调用此方法来请求停止录音"""
        if self._is_running:
            print("[AudioRecorder] sounddevice: 请求停止录音...")
            self._is_running = False # Set flag, the run() loop will detect and exit
        else:
            print("[AudioRecorder] sounddevice: 录音已经不在运行状态。")