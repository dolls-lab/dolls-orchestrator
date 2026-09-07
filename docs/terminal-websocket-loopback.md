# 终端 WebSocket loopback 基线

> 状态：协议草案 v0 的传输验证
> 验证环境：Python 3.9 + `websockets` 15.x
> 外部网络、云端 API、真实设备：均不需要

## 目标

`terminal_transport.py` 把已经验证的终端 codec 和 `TerminalSession` 接到真实 WebSocket 握手与帧传输上。它用于证明协议边界在网络库中仍然成立，为后续 Opus 和编排器桥接提供稳定入口。

```text
localhost client
  │ authenticated WebSocket upgrade
  ▼
TerminalWebSocketConnection
  ├── text ──> draft-v0 codec ──> TerminalSession
  ├── bytes ─> raw bounded uplink buffer
  └── stop ──> injected async turn handler
                      │
                      ▼
       STT / LLM / TTS JSON + raw audio bytes
```

## 安装与验证

`websockets` 是可选依赖，避免改变标准库离线核心：

```sh
uv pip install -e '.[terminal]'

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m unittest tests.test_terminal_transport -v
```

依赖限制为 `websockets>=15,<16`。15.x 支持项目当前 Python 3.9 下限，并提供新的 `websockets.asyncio` API；更新到更高 major 前需要同时调整 Python 下限和重新验证握手 API。

## 端点与认证

- 默认地址：`127.0.0.1:8765`；
- 路径：`/xiaozhi/v1/`；
- 必需 headers：`Protocol-Version: 1`、非空 `Device-Id`、非空 `Client-Id`、`Authorization: Bearer ...`；
- 服务端 token 只作为 `serve_terminal` 参数注入，不进入 session identity；
- 未知路径返回固定 404，认证失败返回固定 401；响应和异常不回显 header 或 token；
- WebSocket 压缩关闭，因为 Opus payload 已压缩。

默认 localhost 绑定是开发安全边界。后续硬件联调如果改为局域网地址，必须另行确定 TLS、访问 token 的生成/保存方式和防火墙范围。

## Turn handler 边界

传输层在收到合法 `listen/stop` 后创建不可变 `TerminalTurnRequest`：

- 非敏感 device/client identity；
- 当前 connection session ID；
- 当前 generation；
- 保持顺序的原始上行帧 tuple。

注入的异步 handler 返回不可变 `TerminalTurnResponse`，包含 transcript、reply、emotion 和原始下行帧。传输层在发送前再次验证文本和每个二进制帧，然后按以下顺序下发：

1. STT；
2. LLM；
3. TTS start；
4. TTS sentence_start；
5. 一到多个原始音频帧；
6. TTS stop。

每轮累计上行数据默认最多 4 MiB，每个 WebSocket 消息仍受协议 codec 的 64 KiB 限制。超限、畸形 JSON 或非法控制顺序会以固定协议错误关闭连接，不会把不合法 turn 交给 handler。

## 取消与清理

响应 handler 属于当前 connection。receive loop 在 handler 等待期间继续接收控制消息：

- abort 使 generation 失效、取消 handler、清空缓存并返回 idle；
- goodbye 取消 handler并正常关闭；
- 断线取消 handler、关闭 session 并释放缓存；
- 每个服务文本或音频帧发送前都重新检查 generation；
- 新连接获得独立 session ID，不能复用旧连接的控制消息。

## 当前不代表

- synthetic bytes 不是经过验证的 Opus 音频；
- loopback 成功不代表 Atom VoiceS3R 固件已经兼容；
- 尚未连接 `TurnOrchestrator`，不会运行 ASR、LLM 或 TTS；
- 尚未提供生产服务命令、TLS、LAN 部署或重连策略；
- 协议仍为 draft v0，必须通过指定固件实测后才能冻结 v1。
