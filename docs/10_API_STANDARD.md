# 10 API Standard / API 规范

## 通用原则

- 所有 API 返回 JSON。
- 未登录返回 `401`。
- 无权限或找不到返回安全错误，不泄露敏感信息。
- 不在代码或响应中暴露密码、API Key、数据库连接串。
- 不编造 AI 业务答案、SAP 数据或外部新闻。
- 写操作需要登录并记录必要日志。

## 推荐返回结构

```json
{
  "ok": true,
  "data": {},
  "message": ""
}
```

## Dashboard / SAP API

- `GET /api/dashboard/summary`
- `GET /api/sap/business-analysis`
- `GET /api/sap/profit-analysis`
- `GET /api/sap/inventory-analysis`
- `GET /api/sap/sales-trend`
- `GET /api/sap/ai-analysis`

## Task003 Knowledge API

- `GET /api/knowledge`
- `POST /api/knowledge`
- `GET /api/knowledge/{id}`
- `GET /api/knowledge/search?q=关键词`
- `POST /api/knowledge/from-document`
- `GET /api/knowledge/chunks?knowledge_id=1`
- `POST /api/knowledge/query`
- `GET /api/knowledge/query-history`

## Task005 Production Cockpit API

- `GET /api/ai-ceo/daily-briefing`
- `GET /api/business/cockpit`
- `GET /api/stores/operations`
- `GET /api/brands/operations`
- `GET /api/inventory/risk`
- `GET /api/brands/osprey-risk`
- `POST /api/brands/osprey-risk/calculate`
- `GET /api/tasks`
- `POST /api/tasks`
- `PUT /api/tasks/{id}`
- `POST /api/tasks/{id}/complete`
- `GET /api/health`

## Task006 Automation API

- `GET /api/automation`
- `POST /api/automation`
- `GET /api/workflows`
- `POST /api/workflows`
- `GET /api/notifications`

Automation APIs return safe placeholders when n8n, Dify, Enterprise WeChat, SMS, or SAP event triggers are not configured.

## Task007 Memory API

- `GET /api/memory`
- `POST /api/memory`
- `GET /api/memory/{id}`
- `POST /api/memory/{id}/approve`
- `POST /api/memory/{id}/reject`
- `POST /api/memory/{id}/archive`
- `GET /api/preferences`
- `POST /api/preferences`
- `GET /api/decisions`
- `POST /api/decisions`

New memories default to `pending_review`. AI must not create approved permanent memory without human review.

## Task008 Knowledge Graph API

- `GET /api/graph`
- `GET /api/graph/entities`
- `POST /api/graph/entities`
- `GET /api/graph/entities/{id}`
- `GET /api/graph/relationships`
- `POST /api/graph/relationships`
- `GET /api/graph/search`
- `GET /api/graph/entity-network`
- `GET /api/graph/risk-map`
- `GET /api/graph/osprey-risk`
- `POST /api/graph/extract`

Graph APIs must not invent relationships, risk values or financial facts.

## Task009 Multi-Agent API

- `GET /api/agents/collaboration`
- `GET /api/agents/roles`
- `POST /api/agents/roles`
- `GET /api/agents/tasks`
- `POST /api/agents/tasks`
- `POST /api/agents/tasks/{id}/approve`
- `POST /api/agents/tasks/{id}/reject`
- `GET /api/agents/discussions`
- `POST /api/agents/discussions`
- `GET /api/agents/tools`
- `POST /api/agents/tools`
- `POST /api/agents/scenarios/osprey-pricing`

Agent APIs must not fake conclusions. Business-changing actions require human review.

## Task010 FoxBrain Jarvis API

- `GET /api/jarvis/status`
- `GET /api/jarvis/suggestions`
- `GET /api/jarvis/conversations`
- `POST /api/jarvis/conversations`
- `GET /api/jarvis/conversations/{id}`
- `POST /api/jarvis/message`
- `POST /api/jarvis/route-intent`
- `POST /api/jarvis/action/confirm`
- `POST /api/jarvis/report`

Jarvis APIs return citation-ready payloads with `intent`, `answer`, `confidence`, `tool_calls`, `cited_sources`, `related_objects`, `limitations`, and `next_actions`.

Jarvis must not invent SAP data, finance results, customer facts, market news, or official reports. Important actions require human confirmation.

## Future API

- `POST /api/files/parse`
- `POST /api/knowledge/embed`
- `POST /api/knowledge/sync-to-dify`
- `POST /api/sap/knowledge-snapshot`
- `POST /api/agents/run`
