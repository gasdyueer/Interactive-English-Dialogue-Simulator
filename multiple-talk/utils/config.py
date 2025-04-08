import os

class Config:
    def __init__(self):
        self.model_path = r"E:\AI\funasr_model\sensevoice"
        self.audio_temp_dir = "_temp_audio"
        self.allowed_audio_dirs = []  # 可配置允许的音频目录
        
    def validate_paths(self):
        if not os.path.exists(self.model_path):
            raise ValueError(f"模型路径不存在: {self.model_path}")
        if not os.path.isdir(self.audio_temp_dir):
            os.makedirs(self.audio_temp_dir)