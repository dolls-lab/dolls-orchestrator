# 连续对话可靠性与延迟基线

> 状态：可复现的顺序多轮采集工具
> 默认 profile：`offline`
> 产品阈值：尚未设定

## 测量范围

`benchmark-turns` 使用同一个 WAV、同一个 `TurnOrchestrator` 和同一个 session 顺序执行指定轮数。它用于验证：

- 多轮执行成功率；
- 从 turn 输入就绪到第一个有效 TTS PCM chunk 的端到端 `first_audio_ms`；
- 完整 turn 的 `total_ms`；
- 单轮失败后，紧接着的一轮能否成功恢复；
- conversation context 在连续运行中仍受既有 turn 上限约束。

`first_audio_ms` 的终点是编排器收到首个合成音频块，不是终端扬声器实际出声。WebSocket 排队、网络、固件解码和播放延迟需要之后通过实机时间点单独测量。

## 离线运行

准备一个有效的单声道 PCM WAV 后运行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m dolls_orchestrator benchmark-turns \
  --profile offline \
  --turns 20 \
  --input /path/to/input.wav \
  --output .artifacts/offline-reliability.json
```

`offline` 不访问网络、不加载模型、不打开麦克风或扬声器，也不保留生成音频。后续可以用相同命令选择 `local-no-api` 或 `local-voice`，但不同 profile 的数字不能直接混合作为同一性能结论。

## 报告契约

JSON 的 `report_contract_version` 当前为 1。`summary` 包含：

- `total`、`completed`、`failed`、`success_rate`；
- `first_audio_ms` 与 `total_ms` 的 sample 数、P50、P95；
- `recovery_opportunities` 与 `recoveries`。

百分位使用 nearest-rank：排序后取 `ceil(p × n) - 1` 的零基索引，只统计成功轮且实际存在的测量值。失败不会被伪造为零延迟；没有样本时 P50/P95 为 `null`。

每轮只记录顺序号、状态、首音/总耗时、各阶段 provider/model 和耗时，以及规范化的错误 stage/type。报告不写入：

- transcript、reply 或 PCM/Opus；
- 输入/角色包路径；
- session、turn 或 generation ID；
- prompt、examples、source claims；
- key、token、异常消息或环境变量原值。

文件先写入同目录临时文件，flush/fsync 后通过原子替换发布。普通单轮失败会被记录并继续；外部取消会传播，不会声称已经生成完整报告。

## 结果解释

当前工具只采集证据，不自动标记延迟“通过/失败”。目标值、可接受区间和失败区间依赖最终 ASR/LLM/TTS、家庭电脑、网络和 Atom VoiceS3R 实机数据，应在这些条件确定后形成独立 OpenSpec change。离线结果只能证明管线、聚合和恢复记录可工作。
