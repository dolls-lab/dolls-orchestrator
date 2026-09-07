# 服务就绪预检

`health` 用于在完整对话或后续局域网服务启动前检查结构性前置条件。它是无副作用的 readiness 检查，不是模型、音频设备或远端服务的主动探测。

## 输出契约

JSON 报告固定按以下顺序列出组件：

1. `character`：内置角色，或显式角色包的完整性与兼容性；
2. `asr`：当前 profile 的语音识别 adapter；
3. `llm`：当前 profile 的语言模型 adapter；
4. `tts`：当前 profile 的语音合成 adapter。

每项包含 `stage`、`provider`、`model`、`status` 和 `reason`。`status` 只有 `ready` 或 `blocked`。当前有限 reason code：

| Reason | 含义 |
|---|---|
| `package_invalid` | 显式角色包缺失、损坏或不兼容 |
| `dependency_missing_mlx_whisper` | 当前 Python 环境找不到 MLX Whisper |
| `dependency_missing_numpy` | 当前 Python 环境找不到 NumPy |
| `command_missing_say` | 找不到 macOS `say` |
| `command_missing_afconvert` | 找不到 macOS `afconvert` |
| `network_disabled` | DeepSeek 显式网络开关关闭 |
| `credential_missing` | 网络已允许但未提供 DeepSeek key |

报告不会包含角色包路径、system prompt、角色示例、来源主张、环境变量原值、API key 或异常正文。

## Profile 解释

- `offline`：所有 adapter 都是确定性本地实现，应在干净源码环境中结构就绪；
- `offline-macos`：另外要求 `say` 和 `afconvert` 可发现；
- `local-no-api`：另外要求当前 Python 环境可发现 `mlx_whisper`、`numpy` 和 macOS TTS 命令；
- `local-voice`：在 `local-no-api` 的基础上要求 DeepSeek 网络开关和 key 已配置，但不会验证 key 有效性或访问 provider。

## 命令与退出码

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m dolls_orchestrator health --profile offline
```

可以通过 `--character-package` 覆盖环境中的角色包选择。退出码：

- `0`：所有组件在本预检范围内 ready；
- `1`：至少一个组件 blocked，完整 JSON 仍会输出；
- `2`：普通配置值无法解析。

## 不包含的验证

health 不会执行以下行为：

- 下载、载入或运行 Whisper 权重；
- 打开麦克风或检查 macOS 麦克风权限；
- 调用 `say`、`afconvert` 或 `afplay`；
- 向 DeepSeek 或任何远端地址发送请求；
- 判断角色回复质量、TTS 声音质量或性能。

这些主动探测保留为独立命令或人工/硬件测试，避免例行 readiness 检查产生费用、隐私传输或设备副作用。
