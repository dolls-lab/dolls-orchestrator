# 桌面交互与 DeepSeek 协议基线

> 测试日期：2026-09-07  
> DeepSeek 实际请求：0 次  
> 结果：代码与本地硬件边界通过

## 已验证能力

- DeepSeek 双重保护：网络开关关闭或 key 缺失时，transport 调用次数为零；
- 请求形状：`deepseek-v4-flash`、完整有界消息、`stream=true`、非思考模式、token 上限和 usage；
- SSE：文本增量、完成原因、实际模型和 token 用量归一化；
- 错误：认证、限流、服务失败、超时、畸形事件和取消均转换为项目错误；
- 桌面交互：空闲、录音、识别、生成、合成、播放、完成和可恢复错误状态；
- 临时录音及回复在每轮结束后删除；
- CoreAudio 设备枚举发现 `MacBook Air麦克风` 和 `MacBook Air扬声器`；
- 1 秒麦克风冒烟结果：16005 帧、16 kHz、单声道、16-bit PCM、RMS 346；
- 无 API 的 MLX Whisper 与系统 TTS 链路继续通过。

## 尚待用户 key 的验证

- DeepSeek 真实鉴权；
- 流式首 token 和完整回复延迟；
- 实际 token 用量与单轮成本；
- 固定角色问题集的内容质量。

这些项目不会通过假数据判定为通过。首次真实 API 测试应保持 `deepseek-v4-flash` 和非思考模式，并记录响应返回的实际模型版本。
