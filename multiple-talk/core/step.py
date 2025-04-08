# step.py
import uuid
from dataclasses import dataclass, field

@dataclass
class Step:
    """代表对话流程中的一个步骤"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())) # 唯一ID，方便管理
    step_type: str = ""  # "TTS" 或 "ASR"
    content: str = ""    # TTS的文本内容
    duration: float | None = None # ASR的建议录音时长 (秒), None表示不限制或手动停止
    status: str = "待处理" # 步骤执行状态: 待处理, 进行中, 已完成, 失败
    result: str | None = None # ASR的识别结果
    audio_file: str | None = None # TTS生成的或ASR录制的音频文件路径