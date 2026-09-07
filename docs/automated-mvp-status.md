# 自动化 MVP 状态

> 审计日期：2026-09-07
> 范围：无需云端 API 凭据、无需用户音频操作、无需 Atom VoiceS3R 实机
> 结论：当前自动化实施计划已完成；产品/实机 MVP 尚未验收

## 已完成并有自动证据

| 能力 | 当前证据 | 状态 |
|---|---|---|
| 适配器契约与离线 WAV-to-WAV | [README 离线闭环](../README.md#离线闭环) | 完成 |
| MLX Whisper + macOS TTS 无 API 链路 | [本地无 API 基线](./local-no-api-baseline.md) | 完成 |
| DeepSeek SSE 边界与默认网络保护 | [桌面交互基线](./desktop-interactive-baseline.md) | 契约完成，真实请求待外部验证 |
| 三月七 contract-v1 角色包消费、检查与完整性 | [角色包基线](./character-package-baseline.md) | 完成 |
| 三月七文本评测 fixture 与隔离报告 | [角色评测基线](./character-evaluation-baseline.md) | 采集管线完成，语义评分待外部验证 |
| 无副作用服务 readiness | [服务就绪预检](./service-readiness.md) | 完成 |
| 桌面 push-to-talk 状态、取消和恢复 | [桌面交互基线](./desktop-interactive-baseline.md) | 自动边界完成 |
| 小智 draft-v0 协议与连接状态机 | [终端协议草案](./terminal-protocol-v0.md) | 自动契约完成，固件兼容待实机 |
| 真实 localhost WebSocket transport | [WebSocket loopback](./terminal-websocket-loopback.md) | 完成 |
| WebSocket 音频到 ASR/LLM/TTS 编排 | [终端音频桥接](./terminal-audio-bridge.md) | 完成 |
| 16/24 kHz raw Opus 与 60 ms 分帧 | [原生 Opus codec](./native-opus-codec.md) | 完成 |
| readiness-gated 可启动终端服务 | [终端服务 runner](./terminal-service-runner.md) | 离线/localhost 完成 |
| 连续轮次成功率、P50/P95 与恢复记录 | [可靠性 benchmark](./reliability-benchmark.md) | 采集工具完成 |

最新全仓自动回归为 119 项测试，覆盖标准库离线核心、真实 `libopus 1.6.1`、真实 localhost TCP/WebSocket、取消/旧 generation 清理、角色包、评测、readiness、服务 runner 和 benchmark。测试不访问模型 API，不使用麦克风或扬声器。

## 必须等待外部证据

以下项目不能由 fixture、mock 或合成音频替代，因此不标记为完成：

1. **DeepSeek 真实请求**：需要用户提供临时 API key 并显式打开网络开关，验证认证、实际模型版本、SSE、限流、超时和费用边界。
2. **Atom VoiceS3R 实机**：需要确认目标板/固件身份、握手 headers、16 kHz 上行、24 kHz/60 ms 下行解码播放、按钮半双工、abort 与断线恢复。
3. **真实家庭 LAN 与播放时间点**：需要确定可信网络、TLS/防火墙/token 生命周期，并采集从录音结束到扬声器首音的真实延迟。
4. **角色质量与声音**：需要对三月七真实模型回复做 rubric/人工复核，并等待 `dolls-voice` 的版本化 TTS 服务契约与目标声线证据。
5. **产品阈值**：成功率、P50/P95 首音、单轮长度及目标/可接受/失败区间需要用户结合最终电脑、API、网络和实机数据确认。
6. **代表性长期运行**：需要真实普通话样本集和较长连续会话，检查内存、任务、连接与主观体验，而不是用重复静音/合成音调宣称通过。

## 恢复工作入口

外部条件具备后，每一项仍应单独走 OpenSpec 探索、提案、实现/验证、规格同步和归档，并单独 commit/push。建议顺序为：

1. DeepSeek 真实 smoke 与诊断记录；
2. Atom VoiceS3R localhost/LAN 兼容测试；
3. 真实端到端 benchmark 与阈值提案；
4. 三月七语义评分及 `dolls-voice` 声线验收。

在这些证据出现前，项目可以准确表述为“离线自动化链路完成”，不能表述为“实体角色语音设备 MVP 已验收”。
