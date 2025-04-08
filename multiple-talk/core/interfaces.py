# interfaces.py
import time
import os
import wave
import random
from abc import ABC, abstractmethod
from PySide6.QtCore import QObject, Signal, QRunnable, Slot, QThreadPool
import requests
import json
# 创建临时文件夹
TEMP_AUDIO_DIR = "_temp_audio"
if not os.path.exists(TEMP_AUDIO_DIR):
    os.makedirs(TEMP_AUDIO_DIR)

# --- TTS 接口 ---

class TTSInterface(ABC):
    """TTS 模块接口基类"""
    @abstractmethod
    def synthesize(self, text: str, output_filename: str) -> bool:
        """
        将文本合成为音频文件。
        :param text: 要合成的文本。
        :param output_filename: 保存音频的文件路径。
        :return: 成功返回 True，失败返回 False。
        """
        pass

class MyRequestsTTS(TTSInterface):
    """使用 requests 调用本地 HTTP API 实现 TTS"""

    def __init__(self, base_url="http://localhost:9880/", ref_audio_path=None, ref_text=""):
        """
        初始化 Requests TTS 接口。
        :param base_url: TTS API 的基础 URL。
        :param ref_audio_path: 参考音频文件的路径。
        :param ref_text: 参考文本。
        """
        self.base_url = base_url
        # Use provided ref_audio_path or a default if None
        self.ref_audio = ref_audio_path if ref_audio_path else r"E:\AI\AIGC-models\GPT-Sovits-自训\Okura Risona\slicer_opt\Okura Risona_vocals.wav_0000000000_0000131840.wav" # Consider making this configurable
        self.ref_text = ref_text if ref_text else "乙女理論とその後の周辺 ドラマCD" # Consider making this configurable
        print(f"[MyRequestsTTS] Initialized with URL: {self.base_url}")
        print(f"[MyRequestsTTS] Ref Audio: {self.ref_audio}")
        print(f"[MyRequestsTTS] Ref Text: {self.ref_text}")
        # Basic check if ref_audio exists
        if not os.path.exists(self.ref_audio):
             print(f"[MyRequestsTTS] 警告: 参考音频文件不存在: {self.ref_audio}")


    def synthesize(self, text: str, output_filename: str) -> bool:
        """实现 TTS 合成逻辑"""
        # Ensure base_url ends with a slash
        if not self.base_url.endswith('/'):
             self.base_url += '/'

        # Construct the full URL with URL-encoded parameters
        params = {
            'text': text,
            'ref_audio': self.ref_audio,
            'ref_text': self.ref_text
        }
        try:
            print(f"[MyRequestsTTS] Sending request to: {self.base_url} with text: {text[:30]}...")
            # Use params argument for proper URL encoding
            response = requests.get(self.base_url, params=params, timeout=60) # Add timeout
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

            # 保存音频文件
            print(f"[MyRequestsTTS] Saving audio to: {output_filename}")
            with open(output_filename, "wb") as f:
                f.write(response.content)
            print("[MyRequestsTTS] Synthesis successful.")
            return True

        except requests.exceptions.RequestException as e:
            print(f"[MyRequestsTTS] 请求失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"服务器状态码: {e.response.status_code}")
                print(f"服务器响应体: {e.response.text[:500]}...") # Limit output size
            return False
        except IOError as e:
             print(f"[MyRequestsTTS] 文件写入错误 ({output_filename}): {e}")
             return False
        except Exception as e:
            print(f"[MyRequestsTTS] 发生未预料的错误: {e}")
            return False

    # --- !!! ADD THIS METHOD BACK !!! ---
    def synthesize_async(self, text: str, output_filename: str):
        """异步启动合成任务"""
        # Option 2: Initialize threadpool lazily if not done in __init__
        if not hasattr(self, 'threadpool'):
            self.threadpool = QThreadPool()
            print(
                f"[{self.__class__.__name__}] Created ThreadPool (lazy). Max threads: {self.threadpool.maxThreadCount()}")

        # Pass 'self' (the MyRequestsTTS instance) to the task
        # Ensure SynthesizeTask is defined correctly in this file or imported
        task = SynthesizeTask(self, text, output_filename)
        self.threadpool.start(task)
        return task
    # --- END OF METHOD TO ADD ---


class SynthesizeTask(QRunnable):
    """用于在线程池中执行TTS合成的任务"""
    def __init__(self, tts_instance, text, output_filename):
        super().__init__()
        self.tts_instance = tts_instance
        self.text = text
        self.output_filename = output_filename
        self.signals = self.TaskSignals()

    class TaskSignals(QObject):
        finished = Signal(str, bool) # filename, success

    @Slot()
    def run(self):
        print(f"[TTS Task] 开始合成: {self.text[:20]}...")
        success = self.tts_instance.synthesize(self.text, self.output_filename)
        print(f"[TTS Task] 合成结束: {self.output_filename}, 成功: {success}")
        self.signals.finished.emit(self.output_filename, success)

class MockTTSInterface(TTSInterface):
    """模拟 TTS 接口"""

    def __init__(self):
        # MODIFY HERE: Remove super().__init__() if TTSInterface has no __init__
        # super().__init__() # Remove this line if TTSInterface has no __init__
        self.threadpool = QThreadPool()
        print(f"[MockTTS] 初始化，线程池最大线程数: {self.threadpool.maxThreadCount()}")

    def synthesize_async(self, text: str, output_filename: str):
        """异步启动合成任务"""
        task = SynthesizeTask(self, text, output_filename)
        # task.signals.finished.connect(self.on_synthesize_finished) # Manager直接连接Task信号
        self.threadpool.start(task)
        return task # 返回task以便连接信号

    # --- 同步实现（由 Task 调用） ---
    def synthesize(self, text: str, output_filename: str) -> bool:
        """模拟将文本合成为WAV文件"""
        # ... (rest of synthesize method remains the same)
        try:
            print(f"[MockTTS] 正在模拟合成文本: '{text}' 到 {output_filename}")
            # 模拟耗时
            time.sleep(random.uniform(0.5, 1.5))

            # 创建一个假的WAV文件 (静音)
            with wave.open(output_filename, 'wb') as wf:
                wf.setnchannels(1)       # 单声道
                wf.setsampwidth(2)       # 16位采样
                wf.setframerate(16000)   # 16kHz采样率
                duration_sec = max(1, len(text) // 5) # 简单估计时长
                num_frames = int(duration_sec * 16000)
                frames = b'\x00\x00' * num_frames # 静音数据
                wf.writeframes(frames)
            print(f"[MockTTS] 模拟合成成功: {output_filename}")
            return True
        except Exception as e:
            print(f"[MockTTS] 模拟合成失败: {e}")
            return False

    def synthesize_async(self, text: str, output_filename: str):
        """异步启动合成任务 (Mock)"""
        if not hasattr(self, 'threadpool'): self.threadpool = QThreadPool()
        task = SynthesizeTask(self, text, output_filename)
        self.threadpool.start(task)
        return task
# --- ASR 接口 ---

class ASRInterface(ABC):
    """ASR 模块接口基类"""
    @abstractmethod
    def recognize(self, audio_filename: str) -> str | None: # Keep original signature here
        """
        识别音频文件中的语音。
        :param audio_filename: 要识别的音频文件路径。
        :return: 识别出的文本，失败返回 None。
        """
        pass

class MyRequestsASR(ASRInterface):
    """使用 requests 调用本地 HTTP API 实现 ASR"""

    def __init__(self, server_url="http://localhost:5000/transcribe", expected_dtype='float32'):
        """
        初始化 Requests ASR 接口。
        :param server_url: ASR API 的 URL。
        """
        self.server_url = server_url
        # --- DEBUG: Explicitly assign and print ---
        self.expected_dtype = expected_dtype
        print(
            f"[MyRequestsASR __init__] Setting expected_dtype to: {self.expected_dtype} (Type: {type(self.expected_dtype)}) for instance {id(self)}")
        # --- END DEBUG ---
        print(f"[MyRequestsASR] Initialized with URL: {self.server_url}")
        print(
            f"[MyRequestsASR] Expecting server dtype: {self.expected_dtype}")  # Keep this too


    def recognize(self, audio_filename: str) -> str | None:
        """
        向服务器发送包含音频文件路径的 JSON 请求以实现 ASR 识别。
        注意：服务器必须能够访问 audio_filename 指定的路径。
        """
        audio_file_path = audio_filename # 使用传入的文件名作为路径

        try:
            # --- MODIFICATION START ---
            # 1. Check if the local audio file exists (optional but good practice)
            print(f"[MyRequestsASR] 检查本地文件路径: {audio_file_path}...")
            if not os.path.exists(audio_file_path):
                raise FileNotFoundError(
                    f"客户端找不到指定的音频文件 '{audio_file_path}'")
            print("[MyRequestsASR] 本地文件存在。准备发送路径给服务器...")

            # 2. Prepare the JSON payload
            payload = {"audiofile_path": audio_file_path}
            payload_json = json.dumps(payload)  # Convert dict to JSON string
            print(f"[MyRequestsASR] 构造请求 JSON: {payload_json}")

            # 3. Set correct headers for JSON
            headers = {
                'Content-Type': 'application/json'}  # <-- Change Content-Type

            # 4. Send POST request with the JSON data
            print(f"[MyRequestsASR] 正在向 {self.server_url} 发送 POST 请求...")
            response = requests.post(self.server_url,
                                     data=payload_json.encode('utf-8'),
                                     # Send encoded JSON string
                                     headers=headers,
                                     timeout=60)
            # --- MODIFICATION END ---
            # 5. 检查 HTTP 响应状态码 (4xx 或 5xx 会触发异常)
            response.raise_for_status()

            # 6. 解析 JSON 结果
            print("[MyRequestsASR] 请求成功!")
            result_json = response.json() # 解析响应体为 JSON
            print(f"[MyRequestsASR] 服务器响应 JSON: {result_json}")

            # 7. 检查服务器返回的状态和提取转写结果
            server_status = result_json.get('status', 'unknown') # 获取服务器报告的状态

            if server_status == 'OK':
                transcription = result_json.get('transcription')
                if transcription is not None:
                    print(f"[MyRequestsASR] 识别结果: '{transcription}'")
                    return transcription
                else:
                    # Status OK 但没有 transcription 字段，有点奇怪
                    print("[MyRequestsASR] 错误: 服务器状态为 OK 但响应 JSON 中未找到 'transcription' 键。")
                    return None
            elif server_status == 'error':
                # 服务器明确报告了错误
                error_message = result_json.get('message', '服务器报告了未知错误')
                print(f"[MyRequestsASR] 服务器错误: {error_message}")
                # 你可能想根据不同的错误消息做不同处理，例如文件找不到的错误
                # if "找不到指定的音频文件" in error_message:
                #    print("[MyRequestsASR] 提示: 请确保服务器可以访问提供的路径。")
                return None
            else:
                # 未知的服务器状态
                print(f"[MyRequestsASR] 警告: 服务器返回了未知的状态 '{server_status}'。")
                # 尝试获取 transcription (如果存在)
                transcription = result_json.get('transcription')
                if transcription is not None:
                     print(f"[MyRequestsASR] 尽管状态未知，但找到了转写结果: '{transcription}'")
                     return transcription
                else:
                     print("[MyRequestsASR] 错误: 未知服务器状态且未找到 'transcription'。")
                     return None


        except FileNotFoundError as e:
            # 本地文件未找到错误
            print(f"[MyRequestsASR] 错误: {e}")
            return None
        except requests.exceptions.RequestException as e:
            # 网络请求相关的错误 (连接、超时、HTTP 错误状态码等)
            print(f"[MyRequestsASR] 请求失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"服务器状态码: {e.response.status_code}")
                try:
                    # 尝试将错误响应解析为 JSON (服务器可能返回 JSON 格式的错误信息)
                    error_details = e.response.json()
                    print(f"服务器错误详情 (JSON): {error_details}")
                except json.JSONDecodeError:
                    # 如果不是 JSON，打印原始文本
                    print(f"服务器原始响应体: {e.response.text[:500]}...") # 限制输出大小
            return None
        except json.JSONDecodeError as e:
            # 解析服务器成功响应 (2xx) 的 JSON 体时失败
            print(f"[MyRequestsASR] 解析服务器成功响应 JSON 失败: {e}")
            if 'response' in locals() and response is not None:
                 print(f"原始响应内容: {response.text[:500]}...")
            return None
        except Exception as e: # 捕获其他可能的意外错误
            print(f"[MyRequestsASR] 发生未预料的错误: {e}")
            import traceback
            traceback.print_exc() # 打印详细的堆栈跟踪
            return None

    def recognize_async(self, audio_filename: str):
        """异步启动识别任务"""
        # Get or create a threadpool instance for this class instance
        if not hasattr(self, 'threadpool'):
            self.threadpool = QThreadPool()
            print(
                f"[{self.__class__.__name__}] Created ThreadPool. Max threads: {self.threadpool.maxThreadCount()}")
        # Pass 'self' (the MyRequestsASR instance) to the task
        task = RecognizeTask(self, audio_filename)
        self.threadpool.start(task)
        return task

class RecognizeTask(QRunnable):
    """用于在线程池中执行ASR识别的任务"""
    def __init__(self, asr_instance, audio_filename):
        super().__init__()
        self.asr_instance = asr_instance
        self.audio_filename = audio_filename
        self.signals = self.TaskSignals()

    class TaskSignals(QObject):
        # MODIFY HERE: Change the second argument type to str
        finished = Signal(str, str) # audio_filename, result_text (empty string if None)

    @Slot()
    def run(self):
        print(f"[ASR Task] 开始识别: {self.audio_filename}")
        result = self.asr_instance.recognize(self.audio_filename)
        print(f"[ASR Task] 识别结束: {self.audio_filename}, 结果: {result}")
        # MODIFY HERE: Emit empty string if result is None
        result_to_emit = result if result is not None else ""
        self.signals.finished.emit(self.audio_filename, result_to_emit)

class MockASRInterface(ASRInterface):
    """模拟 ASR 接口"""

    def __init__(self):
        # MODIFY HERE: Remove super().__init__() if ASRInterface has no __init__
        # super().__init__() # Remove this line if ASRInterface has no __init__
        self.threadpool = QThreadPool()
        print(f"[MockASR] 初始化，线程池最大线程数: {self.threadpool.maxThreadCount()}")


    def recognize_async(self, audio_filename: str):
        """异步启动识别任务"""
        task = RecognizeTask(self, audio_filename)
        # task.signals.finished.connect(self.on_recognize_finished) # Manager直接连接Task信号
        self.threadpool.start(task)
        return task # 返回task以便连接信号

    # --- 同步实现（由 Task 调用） ---
    def recognize(self, audio_filename: str) -> str | None:
        """模拟识别音频文件"""
        # ... (rest of recognize method remains the same)
        try:
            if not os.path.exists(audio_filename):
                print(f"[MockASR] 错误：音频文件不存在 {audio_filename}")
                return None

            print(f"[MockASR] 正在模拟识别音频: {audio_filename}")
            # 模拟耗时
            time.sleep(random.uniform(1.0, 3.0))

            # 返回一个模拟的识别结果
            possible_results = [
                "今天天气不错", "我听不太清楚", "请再说一遍",
                "你好", "早上好", "机器学习", "语音识别",
                "模拟结果文本"
            ]
            result = random.choice(possible_results)
            print(f"[MockASR] 模拟识别成功，结果: '{result}'")
            return result
        except Exception as e:
            print(f"[MockASR] 模拟识别失败: {e}")
            return None


