# 终端服务 runner

> 状态：可启动的 draft-v0 WebSocket + raw Opus + 编排器离线基线
> 默认网络边界：`127.0.0.1:8765`

## 前置条件

安装 WebSocket extra 与系统 `libopus`：

```sh
uv pip install -e '.[terminal]'
brew install opus
```

服务 token 只从 `DOLLS_TERMINAL_TOKEN` 读取。命令没有 token 参数，health、启动状态、异常和 `Settings` repr 都不会输出其值。可以在当前 shell 中生成临时 token：

```sh
export DOLLS_TERMINAL_TOKEN="$(openssl rand -hex 32)"
```

## 预检与启动

先运行无副作用预检：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m dolls_orchestrator health \
  --profile offline --terminal
```

报告在原有 character、ASR、LLM、TTS 后追加：

- `terminal_transport`：只检查 `websockets` 是否可发现；
- `terminal_audio_codec`：只发现并加载 `libopus`、读取版本；
- `terminal_auth`：只报告 token 为 configured 或 credential_missing。

全部 ready 后启动：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m dolls_orchestrator serve-terminal \
  --profile offline
```

`offline` profile 使用合成 ASR、固定回复和音调 TTS，可在没有 API、模型和音频设备的环境中验证终端网络链路。启动成功后只输出 profile、host、port 和 `listening` 状态。

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---:|---|
| `DOLLS_TERMINAL_TOKEN` | 无 | 必需的 bearer token，不能含空白字符 |
| `DOLLS_TERMINAL_HOST` | `127.0.0.1` | WebSocket 监听地址 |
| `DOLLS_TERMINAL_PORT` | `8765` | 1–65535 |
| `DOLLS_LIBOPUS_PATH` | 自动发现 | 可选的明确动态库路径 |

`--host` 和 `--port` 可覆盖普通监听配置，`--profile` 可选择已有 adapter profile，`--character-package` 可选择三月七 contract-v1 角色包。token 不提供命令行覆盖，避免进入 shell history 与进程参数。

## LAN 安全边界

非回环地址必须同时显式传入 `--allow-lan`：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m dolls_orchestrator serve-terminal \
  --profile offline --host 0.0.0.0 --allow-lan
```

当前是明文 `ws://` 基线，只适用于受信任的家庭局域网。不要直接暴露到公网或不受信任网络；这类部署需要独立的 TLS 终止、token 生命周期和防火墙方案。

## 停止与验证

`Ctrl-C`、SIGTERM、runner task cancellation 或注入的 shutdown event 都进入同一清理路径：停止监听、取消连接持有的工作并等待 server 完整关闭。

真实装配测试使用 localhost 临时端口，将 16 kHz raw Opus 送入 `serve-terminal` 完整装配，并验证返回的 24 kHz raw Opus 可解码：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m unittest tests.test_terminal_service -v
```

测试不访问云端 API、不加载模型，也不使用麦克风或扬声器。
