# Interactive English Dialogue Simulator - Multiple Talk

## 项目简介

这是一个基于FunASR语音识别模型的英语对话模拟器，提供HTTP接口进行音频转写服务。项目包含完整的音频处理模块和对话管理功能。

## 主要功能

- 提供HTTP服务接口进行音频转写
- 支持POST请求发送音频文件路径进行转写
- 提供健康检查接口
- 支持CORS跨域请求
- 内置音频录制和播放功能
- 对话管理和交互功能

## 系统架构

- `audio/`: 音频处理模块(录制、播放、转写)
- `core/`: 核心对话管理模块
- `ui/`: 用户界面组件
- `utils/`: 工具类和配置

## 安装指南

1. 克隆项目仓库: `git clone https://github.com/your-repo/Interactive-English-Dialogue-Simulator.git`
2. 安装依赖：`pip install -r requirements.txt`
3. 下载FunASR模型并配置模型路径(修改funasr_http_server.py中的模型路径)

## 使用方法

### HTTP服务

1. 启动服务：`python multiple-talk/funasr_http_server.py`
2. 服务默认监听5000端口
3. 可用接口：
   - GET /health - 检查服务状态
   - POST /transcribe - 发送音频文件路径进行转写

### 示例请求

```json
{
  "audiofile_path": "/path/to/your/audio.wav"
}
```

### 图形界面

运行主程序: `python multiple-talk/main.py`

## 开发指南

1. 代码结构遵循模块化设计原则
2. 使用logging模块进行日志记录
3. 配置信息存储在utils/config.py中

## 贡献指南

欢迎提交Pull Request或Issue报告问题。请遵循现有代码风格和提交规范。
