# 原生 Opus codec 基线

> 状态：真实 `libopus` raw-packet 编解码已接入
> 云端 API、模型下载与音频硬件：均不需要

## 依赖与发现

`LibOpusCodec` 直接通过 Python 标准库 `ctypes` 调用系统 `libopus`，不依赖 Python Opus wrapper。macOS 开发机可安装：

```sh
brew install opus
```

codec 按以下顺序发现库：构造函数显式路径、平台动态库查询结果、常见 Homebrew/Unix 路径。显式路径不可用时不会静默回退；初始化会抛出 stage 为 `terminal_audio_codec` 的稳定错误，也不会把搜索路径写入消息。

```python
from dolls_orchestrator.opus_codec import LibOpusCodec

codec = LibOpusCodec()
print(codec.version)
```

系统库是运行时依赖，不会由应用下载或打包。当前验证版本为 `libopus 1.6.1`。

## 帧与状态边界

- 每个 WebSocket binary message 是一个 raw Opus packet，不使用 Ogg/WebM 容器；
- 上行协商为 16 kHz、mono、60 ms，解码为 `pcm_s16le`；
- 下行协商为 24 kHz、mono、60 ms，每 1440 个 sample 编码一个 packet；
- 一次 encode/decode 调用各自创建一个 native state，按序处理全部 packet，并在成功、失败或取消时销毁；
- PCM 不是 24 kHz 时使用确定性的单声道线性插值；最后不足 60 ms 的一帧补静音。

raw packet 不携带采样率、声道或 pre-skip 元数据，双方必须使用握手协商参数。当前基线不实现 jitter buffer、乱序恢复、PLC/FEC、容器封装或跨 turn codec state。

## 离线验证

安装 `libopus` 和 `.[terminal]` 后运行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m unittest tests.test_opus_codec -v
```

测试使用合成音调验证 16/24 kHz 编解码、60 ms 分帧、末帧 padding、重采样、坏包与依赖错误，并启动真实 localhost WebSocket，把 raw Opus 上行送入离线 ASR/LLM/TTS 编排器，再将返回包解码为非静音 PCM。整个流程不读取 API key、不访问外网，也不使用麦克风或扬声器。
