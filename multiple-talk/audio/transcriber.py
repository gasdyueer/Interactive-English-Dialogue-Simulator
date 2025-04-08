from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
import traceback
import os

class AudioTranscriber:
    def __init__(self, model_path):
        self.model = None
        self.model_loaded = False
        self.model_path = model_path
        self.chunk_size = [0, 10, 5]
        self.encoder_chunk_look_back = 4
        self.decoder_chunk_look_back = 1
        
    def load_model_func(self):
        """加载语音识别模型"""
        if self.model_loaded:
            print("模型已加载。")
            return True
            
        print("开始加载模型...")
        try:
            self.model = AutoModel(
                model=self.model_path,
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device="cuda:0"
            )
            self.model_loaded = True
            print(f"模型加载完成: {self.model_path}")
            return True
        except Exception as e:
            print(f"模型加载失败: {e}")
            traceback.print_exc()
            return False

    def transcribe(self, audio_path):
        """转写音频文件"""
        if not self.model_loaded:
            return "错误：模型未加载或加载失败，无法执行转写。"
            
        # 文件验证
        if not os.path.exists(audio_path):
            return f"错误：找不到指定的音频文件: {audio_path}"
        if not os.path.isfile(audio_path):
            return f"错误：提供的路径不是一个有效的文件: {audio_path}"

        try:
            result = self.model.generate(
                input=audio_path,
                cache={},
                is_final=True,
                encoder_chunk_look_back=self.encoder_chunk_look_back,
                decoder_chunk_look_back=self.decoder_chunk_look_back,
                language="auto",
            )
            
            if isinstance(result, list) and result:
                first_item = result[0]
                if isinstance(first_item, dict) and 'text' in first_item:
                    try:
                        return rich_transcription_postprocess(first_item['text'])
                    except Exception as e:
                        return f"错误: 后处理转写结果时失败: {e}"
                return "错误: 模型返回数据格式无效。"
            return "错误: 模型未返回任何结果 (可能音频无语音)。"
            
        except Exception as e:
            traceback.print_exc()
            return f"错误: 转写过程中发生异常: {e}"