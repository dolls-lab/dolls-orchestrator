# 终端音频编排桥接基线

> 状态：协议草案 v0 的 codec-neutral 编排桥接
> 自动验证：合成 codec + 原生 Opus + 离线 ASR/LLM/TTS
> 硬件和云端 API：均未启用

## 数据路径

`OrchestratorTerminalBridge` 实现 WebSocket transport 所需的异步 turn handler：

```text
16 kHz mono raw Opus frames
  │ TerminalAudioCodec.decode_uplink
  ▼
16 kHz mono PCM s16le
  │ private per-turn input.wav
  ▼
TurnOrchestrator
  │ ASR → character LLM → TTS
  ▼
PCM + transcript + reply
  │ TerminalAudioCodec.encode_downlink
  ▼
24 kHz mono raw Opus frames
```

桥接器不认识具体 Opus 库，也不改变 ASR、LLM 或 TTS adapter。仓库提供的 `LibOpusCodec` 通过系统 `libopus` 实现以下两个异步方法：

- `decode_uplink(frames, UPLINK_AUDIO)`：保持帧顺序，返回 `DecodedTerminalAudio`；
- `encode_downlink(pcm, source_format, DOWNLINK_AUDIO)`：完成需要的重采样和编码，返回有序 bytes 帧。

## 输入与输出约束

解码结果必须是：

- 16 kHz；
- 单声道；
- 16-bit little-endian PCM；
- 非空并按 sample frame 完整对齐。

编排器输出的 PCM 和实际 `AudioFormat` 原样交给 encoder，目标参数固定为协议 draft v0 的 24 kHz、单声道、Opus、60 ms。encoder 必须返回至少一个非空且不超过协议单帧上限的 bytes payload。

完成后，桥接器生成 `TerminalTurnResponse`：

- transcript 和 reply 来自编排器结果；
- emotion 暂时固定为白名单值 `neutral`；
- audio frames 保持 encoder 返回顺序；
- WebSocket session ID 原样用作编排器 session ID；
- device/client identity 不进入 prompt、对话上下文或 telemetry。

## 临时数据与取消

现有 ASR contract 使用 WAV 路径，因此桥接器为每轮创建权限受操作系统保护的临时目录并写入 `input.wav`。目录在以下所有路径退出时删除：

- 正常完成；
- codec 失败或返回非法数据；
- ASR、LLM 或 TTS 失败；
- WebSocket abort、goodbye 或断线取消。

编排器会把底层 task cancellation 规范化为 `TurnCancelledError`。桥接器在最外层把它恢复为 `asyncio.CancelledError`，让 transport 将其视为预期取消，不发送 1011 内部错误，也不允许旧 generation 返回任何文本或音频。

## 离线验证

不安装 WebSocket extra 也可运行桥接单元测试：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m unittest \
  tests.test_terminal_bridge.TerminalBridgeTests -v
```

安装 `.[terminal]` 后，完整测试会额外启动真实 `127.0.0.1` 临时端口，验证：

- synthetic uplink bytes 到达 codec；
- codec 生成的 WAV 实际经过离线 `TurnOrchestrator`；
- STT、LLM、TTS 生命周期和 synthetic downlink bytes 按协议返回；
- abort 能取消正在等待 ASR 的编排器；
- 取消后连接仍保持 idle，可接受下一轮；
- 不产生外部网络、模型下载、麦克风或 API 操作。

原生库安装、发现顺序、raw packet 限制和真实回环测试见 [原生 Opus codec](./native-opus-codec.md)。协议、transport、bridge、codec 和离线 profile 已由 [终端服务 runner](./terminal-service-runner.md) 完成显式装配；局域网实机兼容与生产级抖动处理仍属于 [外部验证范围](./automated-mvp-status.md#必须等待外部证据)。
