# main.py
import sys
import os
import signal
import traceback
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer # 用于优雅退出

from qt_material import apply_stylesheet # 应用主题

from ui.main_window import MainWindow
from core.conversation_manager import ConversationManager
from core.interfaces import MyRequestsTTS, MyRequestsASR, MockTTSInterface, MockASRInterface
from audio.player import AudioPlayer
from audio.recorder import AudioRecorder
from utils.config import Config
from utils.logger import setup_logger

# --- 全局设置 ---
APP_NAME = "MultiTurnDialogSimulator"
APP_VERSION = "1.0.0"

# 临时音频目录 (确保存在)
TEMP_AUDIO_DIR = "_temp_audio"
if not os.path.exists(TEMP_AUDIO_DIR):
    os.makedirs(TEMP_AUDIO_DIR)


def main():
    """应用程序主入口点"""
    # 初始化配置和日志
    config = Config()
    logger = setup_logger('main')
    
    try:
        config.validate_paths()
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        sys.exit(1)

    app = QApplication(sys.argv)
    
    # 初始化音频组件
    player = AudioPlayer()
    recorder = AudioRecorder()
    
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # --- 应用主题 (qt-material) ---
    # 可选主题: 'dark_teal.xml', 'light_blue.xml' 等
    try:
        apply_stylesheet(app, theme='dark_blue.xml')
        print("[Main] 应用 qt-material 主题: dark_blue.xml")
    except Exception as e:
        print(f"[Main]应用 qt-material 主题失败: {e}. 使用默认样式。")

    # --- 初始化核心组件 ---
    # MODIFY HERE: Instantiate your actual API classes
    tts_interface = None
    asr_interface = None
    print("[Main] 初始化 Requests TTS/ASR 接口...")
    # You can pass configuration here if needed, e.g.:
    # tts_interface = MyRequestsTTSAsync(base_url="http://your_tts_ip:port/")
    # asr_interface = MyRequestsASRAsync(server_url="http://your_asr_ip:port/")
    try:
        tts_interface = MyRequestsTTS()  # Uses defaults
        asr_interface = MyRequestsASR()  # Uses defaults
        # --- DEBUG: Check attribute right after creation ---
        if hasattr(asr_interface, 'expected_dtype'):
            print(
                f"[Main]   -> MyRequestsASR instance HAS expected_dtype: {asr_interface.expected_dtype}")
        else:
            print(
                "[Main]   -> CRITICAL: MyRequestsASR instance LACKS expected_dtype immediately after init!")
        # --- END DEBUG ---
        print("[Main] 使用 Requests API 接口。")


    except Exception as e:

        print(f"[Main] 初始化 Requests API 失败:")

        # MODIFY HERE: Print full traceback for the initialization error

        traceback.print_exc()

        # Fallback logic
        if tts_interface is None:
            print("[Main] 回退到 Mock TTS 接口。")
            # MODIFY HERE: Instantiate the base mock class
            tts_interface = MockTTSInterface()
            # Ensure the async method exists (it should if defined in interfaces.py)
            if not hasattr(tts_interface, 'synthesize_async'):
                print(
                    "[Main] CRITICAL: MockTTSInterface is missing synthesize_async method!")
                # Attempt dynamic add as last resort (very unclean)
                # tts_interface.threadpool = QThreadPool()
                # tts_interface.synthesize_async = lambda text, fname: getattr(tts_interface, 'threadpool').start(SynthesizeTask(tts_interface, text, fname))

        if asr_interface is None:
            print("[Main] 回退到 Mock ASR 接口。")
            # MODIFY HERE: Instantiate the base mock class
            asr_interface = MockASRInterface()
            # Ensure the async method exists
            if not hasattr(asr_interface, 'recognize_async'):
                print(
                    "[Main] CRITICAL: MockASRInterface is missing recognize_async method!")
                # Attempt dynamic add as last resort
                # asr_interface.threadpool = QThreadPool()
                # asr_interface.recognize_async = lambda fname: getattr(asr_interface, 'threadpool').start(RecognizeTask(asr_interface, fname))

        # --- DEBUG: Final check before passing to Manager ---
        print("-" * 20)
        print(f"[Main] Final check before ConversationManager:")
        print(
            f"[Main]   tts_interface: type={type(tts_interface)}, obj={tts_interface}")
        print(
            f"[Main]   asr_interface: type={type(asr_interface)}, obj={asr_interface}")
        if isinstance(asr_interface, MyRequestsASR):
            if hasattr(asr_interface, 'expected_dtype'):
                print(
                    f"[Main]   asr_interface (MyRequestsASR) HAS expected_dtype: {asr_interface.expected_dtype}")
            else:
                print(
                    "[Main]   CRITICAL: asr_interface (MyRequestsASR) LACKS expected_dtype before Manager init!")
        elif isinstance(asr_interface, MockASRInterface):
            print("[Main]   asr_interface is MockASRInterface.")
        else:
            print("[Main]   asr_interface is of unexpected type.")
        print("-" * 20)
        # --- END DEBUG ---

    print("[Main] 初始化 ConversationManager...")
    conversation_manager = ConversationManager(tts_api=tts_interface, asr_api=asr_interface)

    print("[Main] 初始化 MainWindow...")
    main_window = MainWindow(manager=conversation_manager)
    main_window.show()

    # --- 优雅退出处理 ---
    def safe_exit(sig=None, frame=None):
        print("[Main] 请求退出应用程序...")
        # main_window.close() # closeEvent 会处理停止 manager
        app.quit()

    # 允许 Ctrl+C 退出
    signal.signal(signal.SIGINT, lambda sig, frame: safe_exit())
    signal.signal(signal.SIGTERM, lambda sig, frame: safe_exit())

    # 设置一个定时器，使得 Python 解释器能响应信号
    timer = QTimer()
    timer.start(500)  # 每 500ms 检查一次
    timer.timeout.connect(lambda: None) # 无操作，仅用于唤醒解释器

    print("[Main] 启动应用程序事件循环...")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
