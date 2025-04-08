import requests # 导入 requests 库，用于发送网络请求

SERVER_URL = "http://localhost:5000/transcribe" # 定义服务器转写接口的 URL
# --- !! 重要 !! ---
# 将下面替换成你实际的音频文件路径
# 这个文件必须已经是服务器期望的原始字节格式 (例如 16kHz, float32, 单声道)
AUDIO_FILE_PATH = r"E:\somepys\testeverything312\multiple-talk\_temp_audio\tts_0d943f6b-eca0-4d61-a20b-459aa1383748.wav" # <--- 在这里指定你的音频文件路径

try:
    # 1. 以二进制模式('rb')打开并读取整个音频文件内容
    # print(f"正在读取音频文件: {AUDIO_FILE_PATH}...")
    # with open(AUDIO_FILE_PATH, 'rb') as f:
    #     audio_bytes = f.read() # 读取文件的全部字节
    # print(f"读取了 {len(audio_bytes)} 字节。")

    # 2. 设置请求头，指明发送的是原始字节流
    headers = {'Content-Type': 'application/json'}

    # 3. 发送 POST 请求，将文件字节作为请求体(data)发送
    print(f"正在向 {SERVER_URL} 发送请求...")
    # 设置一个超时时间（秒），防止请求无限期等待
    response = requests.post(SERVER_URL, json={'audiofile_path': AUDIO_FILE_PATH}, headers=headers, timeout=60)

    # 4. 检查 HTTP 响应状态码，如果不是 2xx (成功范围)，则抛出异常
    response.raise_for_status()

    # 5. 如果请求成功，打印服务器返回的 JSON 结果
    print("\n请求成功!")
    print("服务器响应:")
    print(response.json()) # 解析并打印 JSON 响应

except FileNotFoundError:
    # 处理文件未找到的错误
    print(f"错误: 指定的音频文件未找到 '{AUDIO_FILE_PATH}'")
except requests.exceptions.RequestException as e:
    # 捕获所有 requests 相关的错误 (如连接错误、超时等)
    print(f"\n请求失败: {e}")
    # 如果响应存在，尝试打印服务器返回的具体错误信息
    if hasattr(e, 'response') and e.response is not None:
          print(f"服务器状态码: {e.response.status_code}")
          print(f"服务器响应体: {e.response.text}")
except Exception as e:
    # 捕获其他未预料的 Python 错误
    print(f"\n发生未预料的错误: {e}")