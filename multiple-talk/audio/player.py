from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import os

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