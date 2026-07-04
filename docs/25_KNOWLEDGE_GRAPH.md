# 25 Knowledge Graph / 企业知识图谱

## 目标

Knowledge Graph 让 FoxBrain 从“模块独立”走向“关系智能”。它把门店、员工、品牌、产品、供应商、客户、文档、知识、研究、记忆、任务、工作流、SAP 记录和决策连接起来。

## 页面与 API

- `/graph`
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

## Entity Model

- `entity_id`
- `entity_type`
- `entity_key`
- `entity_name`
- `description`
- `source_type`
- `source_id`
- `status`
- `created_by`
- `created_at`
- `updated_at`

## Extraction Rules

Task008 only creates relationships from existing explicit fields or user selection.

Examples:

- Product belongs_to Brand
- Employee works_at Store
- Knowledge documented_by related object
- Approved Memory affects related object
- Task related_to object

No relationship should be invented without evidence.

## AI Query Integration

AI Query can later retrieve related entities, relationships, evidence, risk records, memories and knowledge citations. Current version prepares the structure and safe placeholder.
