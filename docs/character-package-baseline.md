# 三月七角色包消费基线

> 测试日期：2026-09-07
> 角色包：`march-7th` `0.1.0`
> DeepSeek 实际请求：0 次

## 契约边界

编排服务独立实现 `dolls-character` contract version 1 的消费校验，不导入生产方源码。加载时检查：

- manifest contract、语言和 orchestrator 兼容版本；
- 固定的四个内容入口以及路径边界；
- system prompt、behavior、examples 和 sources 的完整 SHA-256；
- 行为字段、示例对和紧凑来源主张的 JSON 形状；
- 来源中不存在 PostgreSQL DSN 或批量原文。

运行时只读取发布包目录中的五个文件，不访问 `dolls-character` 源码、评测集或 `hksr_database`。

## 跨仓库验证

验证对象：

```text
../dolls-character/packages/march-7th/0.1.0
```

消费结果：

- 角色 ID：`march-7th`；
- 显示名：三月七；
- 语言：`zh-CN`；
- 包版本：`0.1.0`；
- 示例对：5；
- 派生来源主张：4；
- 来源类型：`hksr-postgres`。

使用 offline profile 完成一轮 WAV-to-WAV 回归，LLM 输入消息数为 12：一个 system、五组角色示例以及一个当前用户消息。状态完整到达 `completed`，输出为 24 kHz、单声道、16-bit PCM WAV，telemetry 正确记录 `character_id=march-7th` 与 `character_version=0.1.0`。

## 回退与错误

- 未设置角色包路径时使用 `builtin-march-7th-style` / `builtin-v1`；
- 环境变量和 CLI 同时存在时，CLI 路径优先；
- 显式路径缺失、格式错误、版本不兼容或哈希变化时启动失败；
- 显式坏包不会回退到内置角色，以免掩盖部署错误。

当前 offline LLM 仍返回固定文本，因此这次验证只证明角色包加载、消息装配和 telemetry 正确，不代表真实模型已经表现出角色风格。角色一致性需要等用户启用 DeepSeek 后通过独立评测集测量。
