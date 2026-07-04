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

Task005 APIs return safe empty structures when real SAP B1 data is unavailable.

## AI Query Response

```json
{
  "answer": "安全回答或等待接入提示",
  "confidence": "retrieval_ready",
  "cited_documents": [],
  "cited_chunks": [],
  "cited_sap_records": [],
  "related_objects": [],
  "generated_at": 0,
  "model_name": "not_connected",
  "limitations": []
}
```

## Future API

- `POST /api/files/parse`
- `POST /api/knowledge/embed`
- `POST /api/knowledge/sync-to-dify`
- `POST /api/sap/knowledge-snapshot`
- `POST /api/agents/run`
