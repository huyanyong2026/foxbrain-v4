# 05 AI Agent Spec / AI 智能体规范

## 第一批智能体

- AI CEO / AI 总经理
- AI CFO / AI 财务总监
- AI COO / AI 运营总监
- AI Purchasing Manager / AI 采购经理
- AI Inventory Manager / AI 库存经理
- AI Brand Manager / AI 品牌经理
- AI Store Manager / AI 门店经理
- AI Marketing Manager / AI 营销经理
- AI Training Manager / AI 培训经理
- AI Customer Service / AI 客服
- AI Secretary / AI 秘书

## 每个智能体包含

- 名称
- 角色说明
- 可查询数据范围
- Prompt 模板
- 常用问题
- 输出格式
- API 占位

## 输出要求

- 结论
- 证据来源
- 风险提醒
- 下一步动作

## Task005 AI CEO Daily Briefing

AI 总经理承担每日经营入口职责：

- 今日经营摘要
- 今日风险提醒
- 今日重点任务
- 门店异常
- 品牌异常
- 库存异常
- 外部研究提醒
- AI 建议转任务

如果 SAP B1 或 Research Engine 没有真实数据，AI 总经理必须显示等待接入状态，不能编造经营事实。

## Task007 Memory Context

AI 智能体后续回答问题时，应优先参考已审核记忆：

- 公司经营原则
- 老板偏好
- 风险偏好
- 品牌策略
- 定价规则
- 重要决策
- 已采纳或已拒绝的 AI 建议

未经审核的记忆不能作为正式结论使用。

## Task009 Multi-Agent Collaboration

AI agents now have structured enterprise roles and can collaborate through:

- Agent tasks
- Agent discussions
- Tool registry
- Knowledge context
- Memory context
- Knowledge graph context
- Human review gates

No agent may execute a business-changing action without human approval.

## Task010 FoxBrain Jarvis

Jarvis is the single AI assistant entrance above the agent matrix.

Jarvis responsibilities:

- Receive the user's natural-language question.
- Route the question to a safe intent.
- Call existing engines through adapters.
- Return answer, confidence, sources, related objects, limitations and next actions.
- Suggest actions without executing important changes directly.
- Hand off complex questions to Multi-Agent Collaboration when needed.

Jarvis V1 uses keyword routing. Later versions can replace routing and response generation with Dify, DeepSeek, OpenAI or another approved model while keeping the same safety and citation payload.
