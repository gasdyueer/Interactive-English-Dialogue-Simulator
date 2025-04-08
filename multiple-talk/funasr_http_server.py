#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.server import HTTPServer, BaseHTTPRequestHandler
from http import HTTPStatus
import json
import traceback
from audio.transcriber import AudioTranscriber  # 修改导入路径

# 初始化转写器
transcriber = AudioTranscriber(r"E:\AI\funasr_model\sensevoice")
transcriber.load_model_func()

class SimpleHandler(BaseHTTPRequestHandler):
    def _send_response(self, status_code, message, content_type='application/json'):
        """发送 HTTP 响应。"""
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*') # 可选：允许 CORS
        self.end_headers()
        if message:
            if isinstance(message, dict):
                message_bytes = json.dumps(message, ensure_ascii=False).encode('utf-8')
            elif isinstance(message, str):
                 # 将字符串包装在 JSON 对象中以便一致性
                message_bytes = json.dumps({"message": message}, ensure_ascii=False).encode('utf-8')
            else:
                 message_bytes = str(message).encode('utf-8')
            self.wfile.write(message_bytes)

    def do_POST(self):
        """
        处理 POST 请求，期望请求体是包含 'audiofile_path' 键的 JSON 对象。
        例如: {"audiofile_path": "/path/to/your/audio.wav"}
        """
        if self.path == '/transcribe':
            if not transcriber.model_loaded:
                self._send_response(HTTPStatus.SERVICE_UNAVAILABLE, 
                    {"status": "error", "message": "模型正在加载或加载失败，请稍后再试。"})
                return
                
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    self._send_response(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "请求体为空，需要包含 JSON 数据。"})
                    return

                # 读取请求体中的 JSON 数据
                post_data_bytes = self.rfile.read(content_length)
                try:
                    request_data = json.loads(post_data_bytes.decode('utf-8'))
                except json.JSONDecodeError:
                    self._send_response(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "无效的 JSON 请求体。"})
                    return

                # 检查 JSON 中是否包含 audiofile_path 键
                if not isinstance(request_data, dict) or 'audiofile_path' not in request_data:
                    self._send_response(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "请求的 JSON 中缺少 'audiofile_path' 键。"})
                    return

                audio_file_path = request_data['audiofile_path']

                # 验证路径是否为字符串 (基本类型检查)
                if not isinstance(audio_file_path, str) or not audio_file_path:
                     self._send_response(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "'audiofile_path' 必须是一个非空字符串。"})
                     return

                print(f"收到转写请求，音频文件路径: {audio_file_path}")

                # --- 重要安全提示 ---
                # 直接使用客户端提供的文件路径存在安全风险！
                # 生产环境中，应严格验证路径是否在允许的目录下，
                # 防止访问服务器上的任意文件 (路径遍历攻击)。
                # 例如:
                # ALLOWED_AUDIO_DIR = "/path/to/safe/audio/storage"
                # if not os.path.abspath(audio_file_path).startswith(ALLOWED_AUDIO_DIR):
                #     self._send_response(HTTPStatus.FORBIDDEN, {"status": "error", "message": "禁止访问指定路径。"})
                #     return
                # 这里为了示例简单，暂时省略了严格的路径验证。

                # 使用提供的文件路径执行转写
                # 修改转写调用方式
                transcription_result = transcriber.transcribe(audio_file_path)
                
                # 检查转写函数是否返回了错误消息 (包括文件不存在等)
                if "错误" in transcription_result or "失败" in transcription_result or "异常" in transcription_result:
                     # 如果是找不到文件等客户端可修复的错误，可以用 BAD_REQUEST
                     if "找不到指定的音频文件" in transcription_result or "不是一个有效的文件" in transcription_result:
                         response_status = HTTPStatus.BAD_REQUEST
                     else: # 其他内部错误
                         response_status = HTTPStatus.INTERNAL_SERVER_ERROR
                     response_message = {"status": "error", "message": transcription_result}
                     self._send_response(response_status, response_message)
                else:
                     # 成功
                     response_message = {"status": "OK", "transcription": transcription_result}
                     self._send_response(HTTPStatus.OK, response_message)

            except Exception as e:
                print(f"处理 /transcribe 请求时发生意外错误: {e}")
                traceback.print_exc()
                response_message = {"status": "error", "message": f"服务器处理请求时发生内部错误: {e}"}
                self._send_response(HTTPStatus.INTERNAL_SERVER_ERROR, response_message)
        else:
            # POST 方法的路径未找到
            self._send_response(HTTPStatus.NOT_FOUND, {"status": "error", "message": f"接口 (POST {self.path}) 未找到"})

    def do_GET(self):
        """处理 GET 请求，用于基本状态检查。"""
        if self.path == '/' or self.path == '/health':
            if model_loaded:
                response_message = {"status": "OK", "message": "服务运行中，模型已加载。"}
                self._send_response(HTTPStatus.OK, response_message)
            else:
                # 指示服务正在运行但模型未就绪
                response_message = {"status": "error", "message": "服务运行中，但模型加载失败或尚未加载。"}
                self._send_response(HTTPStatus.SERVICE_UNAVAILABLE, response_message)
        else:
            # GET 方法的路径未找到
            self._send_response(HTTPStatus.NOT_FOUND, {"status": "error", "message": f"接口 (GET {self.path}) 未找到"})

    def do_OPTIONS(self):
        """处理 OPTIONS 请求，用于 CORS 预检。"""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


# --- 服务端启动 ---
def run_server(server_class=HTTPServer, handler_class=SimpleHandler, port=5000):
    """启动 HTTP 服务器。"""
    server_address = ('', port) # 在所有可用接口上监听
    httpd = server_class(server_address, handler_class)
    print(f"启动 HTTP 服务，监听端口: {port}")
    print(f"模型状态: {'已加载' if model_loaded else '加载失败或未加载'}")
    print("端点:")
    print("  GET  /health        - 检查服务和模型状态")
    print("  POST /transcribe    - 发送包含 'audiofile_path' 的 JSON 请求进行转写")
    print("                      - (例: {\"audiofile_path\": \"/path/to/audio.wav\"})")
    print("  *** 安全警告: 服务器需要有权限访问请求中指定的路径! ***")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭服务器...")
    finally:
        httpd.server_close()
        print("HTTP 服务已停止。")

if __name__ == '__main__':
    # 脚本启动时立即加载模型
    transcriber.load_model_func()
    model_loaded = transcriber.model_loaded

    # 仅在模型成功加载后启动服务器
    if model_loaded:
        run_server()
    else:
        print("模型未能成功加载，服务器无法启动。请检查模型路径和错误信息。")
        # import sys
        # sys.exit(1)