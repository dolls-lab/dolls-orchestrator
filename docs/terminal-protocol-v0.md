# 小智兼容终端协议草案 v0

> 草案版本：0
> 调查日期：2026-09-07
> 上游基线：`78/xiaozhi-esp32` release `v2.4.2`（GitHub 显示提交 `e8d8a40`）
> 实体设备验证：尚未进行

## 定位

本草案把项目阶段二需要的终端语音子集固化为可执行的 Python codec、连接级状态机和非敏感 JSON fixtures。它基于小智官方 [WebSocket Communication Protocol](https://github.com/78/xiaozhi-esp32/blob/v2.4.2/docs/websocket.md) 与 [v2.4.2 release](https://github.com/78/xiaozhi-esp32/releases/tag/v2.4.2)。官方文档明确要求服务端实现继续对照实际代码，因此本项目在 Atom VoiceS3R 实机联调前不会把它标记为协议 v1。

## 支持范围

| 边界 | 草案 v0 |
|---|---|
| 传输 | WebSocket 语义，但当前不打开网络监听 |
| 协议版本 | 上游 version 1 |
| 文本帧 | JSON |
| 二进制帧 | 原样、无自定义头的 Opus payload |
| 上行音频 | Opus、16 kHz、单声道、60 ms |
| 下行音频 | Opus、24 kHz、单声道、60 ms |
| 设备消息 | `hello`、`listen start/stop`、`abort`、`goodbye` |
| 服务消息 | `hello`、`stt`、`llm`、`tts start/sentence_start/stop` |
| 身份头 | `Protocol-Version`、`Device-Id`、`Client-Id`、Bearer `Authorization` |

当前不支持二进制协议 v2/v3、MCP、IoT、AEC、唤醒词、OTA、Opus 编解码、重采样和 TLS 部署。这些内容不会被静默接受为已兼容。

## 会话状态

```text
awaiting_hello
      │ hello
      ▼
    idle ── listen/start ──> listening ── listen/stop ──> processing
      ▲                                                       │
      │                                                       │ begin response
      └──────────── response complete <── speaking <──────────┘

listening / processing / speaking ── abort ──> idle
any open state ── disconnect or goodbye ──> closed
```

每次 `listen/start` 分配一个更大的 generation。只有 `listening` 接收上行 Opus，只有 `speaking` 且 generation 仍为当前值时才释放下行 Opus。abort、goodbye 和 disconnect 会先令当前 generation 失效；稍后完成的旧 LLM/TTS 或旧音频帧只能被丢弃。

草案保持上游 version 1 的裸 Opus 帧，不添加项目自定义 generation 帧头。真实设备侧还必须在取消或新一轮开始时清空播放缓冲；只有实测仍发生旧音频误播，才重新评估自定义 framing。

## 身份与数据安全

- 握手必须携带非空设备 ID、客户端 ID 和 bearer token；
- 配置了预期 token 时使用常量时间比较；
- 解析后的身份对象不保存 token；
- 验证错误不回显 header 或 token 内容；
- fixtures 使用虚构 ID，不包含 Wi-Fi、真实设备标识、录音或密钥；
- codec 不记录或解码 Opus payload。

## 离线验证

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m unittest tests.test_terminal_protocol -v
```

测试覆盖握手身份、凭据拒绝、hello 音频协商、listen/abort/goodbye、服务消息稳定序列化、原始二进制边界、完整半双工流程、乱序事件、外来 session、取消、断线和 stale generation 音频。

fixtures 位于 `tests/fixtures/terminal_protocol_v0.json`，供后续 loopback WebSocket 服务和 `dolls-terminal` 主机侧兼容测试共同消费。

## 尚待实机确认

- 项目称呼 “Atom VoiceS3R” 与上游固件资产 `atom-echos3r` 是否指向同一目标板配置；
- v2.4.2 对该板的实际构建、默认协议版本和音频参数；
- 24 kHz/60 ms 下行在目标固件上的解码与播放表现；
- abort 后设备播放缓冲是否可靠清空；
- 家庭局域网地址、TLS 与 token 配置方式。

下一项可离线完成的 change 是 loopback WebSocket transport：把真实文本/二进制帧适配到本模块，但仍使用内存客户端和伪 Opus payload，不依赖设备、模型 API 或角色声音。
