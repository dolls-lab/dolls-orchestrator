# 三月七离线评测采集基线

> 测试日期：2026-09-07
> 角色包：`march-7th` `0.1.0`
> 评测集：`march-7th-v0.1`，9 个案例
> LLM profile：`offline`
> DeepSeek 实际请求：0 次

## 本阶段验证范围

本基线验证角色评测 fixture 可以在不导入 `dolls-character` 代码、不访问远程数据库、不读取音频且不调用 TTS 的情况下，由编排服务独立加载并执行。

运行命令：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m dolls_orchestrator evaluate-character \
  --profile offline \
  --character-package ../dolls-character/packages/march-7th/0.1.0 \
  --evaluations ../dolls-character/evaluations/march-7th-v0.1.json \
  --output .artifacts/march-7th-offline-evaluation.json
```

## 实测结果

- 报告契约版本：1；
- fixture 版本：`0.1.0`；
- 案例总数：9；
- 成功采集：9；
- 执行失败：0；
- 未评分：9；
- 每个案例的 LLM 输入消息数：12，一个 system、五组角色示例和一个当前评测问题；
- 案例按 fixture 顺序输出，且后一案例不包含前一案例的问题或回复；
- DeepSeek API 请求：0 次。

报告保留评测问题、rubric、模型回复、provider/model、usage、耗时和规范化错误类型，方便之后人工或 judge 工作流审阅。报告不保留角色 system prompt、角色示例、角色包路径、数据库连接或 API key。

## 结果解释

本次 `offline` adapter 对所有案例返回相同的固定回复，所以它只证明评测 fixture 校验、角色消息装配、逐案隔离、流式结果收集、失败语义和报告生成已经跑通。它不能证明三月七角色一致性，也不能据此决定角色包是否达到发布门槛。

现有 `multi-turn-reference` 案例的 fixture 没有携带上一轮消息。本阶段忠实地将其作为单独问题采集，并保持未评分；后续应在 `dolls-character` 中扩展 fixture 契约，显式携带该案例需要的历史消息。

## 后续真实模型路径

用户在本机设置 `DEEPSEEK_API_KEY` 并显式启用网络后，可以用相同角色包和 fixture 将 profile 改为 `local-voice`。在默认网络关闭状态下，该 profile 会为每个案例记录 `ProviderConfigurationError`、生成完整诊断报告并以非零状态退出，不会发送请求。

真实回复采集完成后，应由下一阶段定义独立评分协议，包括 rubric 逐项结果、人工复核、聚合指标和角色包晋级阈值。评分不应回写或泄漏到角色 package prompt 与 examples。
