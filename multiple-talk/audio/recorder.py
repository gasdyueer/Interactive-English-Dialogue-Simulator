import time
import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from PySide6.QtCore import QThread, Signal
import os
from utils.config import Config

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
        config = Config()
        temp_audio_dir = config.audio_temp_dir
        if not os.path.exists(temp_audio_dir):
            os.makedirs(temp_audio_dir)
        self.filename = os.path.join(temp_audio_dir, filename)
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