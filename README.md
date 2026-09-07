# dolls-orchestrator

`dolls-orchestrator` 是角色语音设备的家庭局域网对话编排服务。

它负责接收桌面客户端或 Atom VoiceS3R 终端的语音请求，依次协调 ASR、角色对话和角色 TTS，并把可播放的流式音频返回终端。

## 当前范围

- 单用户、家庭局域网部署；
- 普通话、按键触发、半双工对话；
- 服务运行在开发电脑或家庭电脑；
- 支持可替换的 ASR、LLM、角色包和 TTS 服务；
- 暂不提供公网多用户服务和长期记忆。

详细需求见 [docs/requirements.md](./docs/requirements.md)。总体项目资料位于 [dolls](https://github.com/mengmengjiang1999/dolls)。

## OpenSpec

仓库已使用以下命令初始化 OpenSpec：

```sh
openspec init --tools codex --profile core
```

后续功能先通过 OpenSpec proposal 明确范围，再进入实现。

## 当前可运行基线

当前实现提供不依赖网络、API key 或模型下载的 WAV-to-WAV 桌面闭环：

```text
输入 WAV
  -> 固定文本 ASR
  -> 分块生成的固定角色回复
  -> 中文自然分句
  -> 确定性 PCM 提示音 TTS
  -> 输出 WAV + 结构化耗时
```

这条链路用于验证编排、接口、取消、超时、恢复和音频装配，不代表真实识别效果或目标角色声线。

真实 MLX Whisper 路径直接读取并规范化 PCM WAV，不依赖 FFmpeg。

编排服务支持独立加载 `dolls-character` 发布的 contract-v1 角色包。未配置角色包时继续使用具名内置回退；显式配置的包如果损坏或不兼容，启动会直接失败，不会悄悄回退。

项目推荐 Python 3.12；标准库离线核心也兼容开发机自带的 Python 3.9。推荐后续使用 `uv` 创建 Python 3.12 环境：

```sh
uv venv --python 3.12
uv pip install -e .
```

未安装 `uv` 时可以直接从源码运行离线基线：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m dolls_orchestrator run-turn \
  --profile offline \
  --input /path/to/input.wav \
  --output .artifacts/reply.wav
```

命令输出识别文本、回复文本、阶段耗时和生成文件位置。输入必须是有效 WAV；输出为单声道 16-bit PCM WAV。

## Adapter profiles

| Profile | ASR | LLM | TTS | 当前用途 |
|---|---|---|---|---|
| `offline` | 固定文本 | 固定流式回复 | PCM tone | 默认离线测试，可完整运行 |
| `offline-macos` | 固定文本 | 固定流式回复 | macOS `say` | 验证真实本地中文语音输出 |
| `local-no-api` | MLX Whisper | 固定流式回复 | macOS `say` | 不使用 API 验证完整本地语音链路 |
| `local-voice` | MLX Whisper | DeepSeek V4 Flash | macOS `say` | 真实云端对话，默认禁止联网 |

`local-voice` 只有在同时提供 API key 并显式打开网络开关时才会发送请求。默认配置以及全部自动化测试均不会访问 DeepSeek。

## 配置

所有配置集中从环境变量加载，不读取或生成 `.env` 文件：

```sh
export DOLLS_PROFILE=offline
export DOLLS_CONTEXT_TURNS=6
export DOLLS_SENTENCE_MAX_CHARS=80
export DOLLS_ASR_TIMEOUT_SECONDS=60
export DOLLS_LLM_TIMEOUT_SECONDS=30
export DOLLS_TTS_TIMEOUT_SECONDS=30
export DOLLS_OUTPUT_SAMPLE_RATE=24000
export DOLLS_CHARACTER_PACKAGE_PATH=/path/to/character-package
```

角色包路径不是必填项，也可以通过 `run-turn` 或 `chat` 的 `--character-package` 临时覆盖。命令行参数优先于环境变量。

检查包与当前角色：

```sh
PYTHONPATH=src python3 -m dolls_orchestrator validate-character \
  ../dolls-character/packages/march-7th/0.1.0
PYTHONPATH=src python3 -m dolls_orchestrator character-info \
  --character-package ../dolls-character/packages/march-7th/0.1.0
```

输出只包含角色 ID、显示名、包版本、语言、示例数量、来源类型和主张数量，不输出提示词、示例或来源正文。

DeepSeek 流式适配器配置：

```sh
export DEEPSEEK_API_KEY='由用户本地填写'
export DOLLS_LLM_BASE_URL=https://api.deepseek.com
export DOLLS_LLM_MODEL=deepseek-v4-flash
export DOLLS_LLM_MAX_OUTPUT_TOKENS=256
export DOLLS_DEEPSEEK_NETWORK_ENABLED=false
```

不要将真实 key 写入仓库、命令输出、测试 fixture 或普通日志。只有准备执行真实请求时才将最后一个开关改为 `true`。适配器使用 Chat Completions SSE、`deepseek-v4-flash` 和非思考模式。

MLX Whisper 的预留配置：

```sh
export DOLLS_MLX_WHISPER_MODEL=mlx-community/whisper-small-mlx
```

首次运行真实 ASR 时会从模型仓库下载权重；本地缓存目录不进入 Git。当前已验证基线固定为 `mlx-whisper 0.4.3`、`mlx 0.29.3`、`mlx-community/whisper-small-mlx` revision `45f3915923c7a79a5a5b5a7d909d39aeb0e5630e`。

安装 `mlx-whisper` 并取得模型后，可以在不接入 API 的情况下运行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m dolls_orchestrator run-turn \
  --profile local-no-api \
  --input /path/to/chinese-speech.wav \
  --output .artifacts/local-reply.wav
```

## macOS 临时 TTS

开发机可通过系统自带的 `say` 和 `afconvert` 输出普通中文声音：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m dolls_orchestrator run-turn \
  --profile offline-macos \
  --input /path/to/input.wav \
  --output .artifacts/macos-reply.wav
```

默认声音为 `Tingting`，可以通过 `DOLLS_MACOS_VOICE` 修改。它只用于链路验证，后续由 `dolls-voice` 提供的角色 TTS 替换。

## 交互式桌面对话

安装完整本地依赖：

```sh
uv pip install -e '.[full]'
```

查看 CoreAudio 设备：

```sh
PYTHONPATH=src .venv/bin/python -m dolls_orchestrator devices
```

不使用任何 API 的按键对话：

```sh
HF_HOME="$PWD/.cache/huggingface" \
PYTHONPATH=src \
.venv/bin/python -m dolls_orchestrator chat \
  --profile local-no-api \
  --character-package ../dolls-character/packages/march-7th/0.1.0 \
  --device 0
```

空闲时按 Enter 开始录音，再按 Enter 停止。系统完成本地识别、回复生成和 TTS 后自动使用 `afplay` 播放；输入 `q` 退出。使用 `--no-playback` 可以只生成并验证音频，使用 `--max-turns 1` 可以在一轮成功后退出。

将来启用 DeepSeek 时，把 profile 改为 `local-voice`，并在同一终端临时设置 key 和网络开关：

```sh
export DEEPSEEK_API_KEY='你的 key'
export DOLLS_DEEPSEEK_NETWORK_ENABLED=true
HF_HOME="$PWD/.cache/huggingface" PYTHONPATH=src \
  .venv/bin/python -m dolls_orchestrator chat --profile local-voice
```

首次使用麦克风时，macOS 可能要求为当前终端或 Codex 授予“麦克风”权限。如果设备列表为空或出现权限错误，请在“系统设置 → 隐私与安全性 → 麦克风”中授权后重新运行。也可以执行以下一次性检查；音频仅存在于自动删除的临时目录：

```sh
PYTHONPATH=src .venv/bin/python scripts/mic_smoke.py --seconds 1 --device 0
```

## 隐私与数据边界

- ASR 音频只作为本地文件读取，不进入遥测；
- 短期对话上下文只保存在当前进程内，进程退出即清除；
- 失败或取消的轮次不会写入上下文；
- 遥测包含随机会话/轮次/生成 ID、provider、模型名、耗时、token 用量和错误类型；
- 遥测包含非敏感的角色 ID 与角色包版本，但不包含角色包路径、提示词、示例或来源主张；
- 遥测不包含 API key、原始音频或完整对话正文；
- DeepSeek 默认禁止联网；只有环境 key 和显式网络开关同时存在时才允许请求；
- 交互录音和回复 WAV 使用逐轮临时目录，播放或失败后自动删除。

## 验证

完整离线测试不需要额外依赖：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m unittest discover -s tests -v
```

测试覆盖配置校验、角色包契约/完整性/路径边界、消息顺序、角色 telemetry、适配器契约、MLX 注入边界、DeepSeek 网络保护、请求结构、SSE 解析、HTTP 错误、macOS 命令边界、麦克风录音、播放取消、交互状态、中文分句、上下文上限、超时、旧 generation 清理、失败恢复和 WAV-to-WAV 端到端输出。

## 后续启用顺序

1. 安装并固定 Python 3.12、`mlx-whisper` 和 Whisper 模型 revision；
2. 用真实中文 WAV 建立本地 ASR 准确率与耗时基线；
3. 使用三月七 `0.1.0` 角色包运行本地交互基线；
4. 用户在本机设置 `DEEPSEEK_API_KEY` 并显式开启网络开关；
5. 用固定问题集记录 DeepSeek 首 token、端到端延迟、用量和角色一致性基线；
6. 用 `dolls-voice` 流式 TTS 替换 macOS 系统声音。

首次实测结果见 [本地无 API 基线](./docs/local-no-api-baseline.md)。
角色包接入结果见 [三月七角色包消费基线](./docs/character-package-baseline.md)。
