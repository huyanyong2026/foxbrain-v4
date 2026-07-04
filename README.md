# FoxBrain V4 / 火狐狸企业 AI 操作系统

FoxBrain V4 is the FireFox Enterprise AI Operating System. It is built as a unified company entrance for AI, ERP data, CRM archives, documents, knowledge, workflow, and business analysis.

This repository upgrades the existing FoxBrain project without rewriting it. Existing login, roles, SAP B1 sync, APIs, and deployment assumptions are preserved.

## Core Modules

- AI 总经理
- 经营总览
- 门店中心
- 员工中心
- 品牌中心
- 产品中心
- 供应商中心
- 顾客/会员中心
- 库存采购
- 财务中心
- 内容中心
- 知识中心
- AI 智能体中心
- 工作流中心
- 系统管理

## Main Files

- `portal_v2.py`: portal, login, roles, dashboard, archive framework, knowledge center, document center, AI query, and admin pages.
- `sync_sap_b1.py`: SAP B1 sync script. Task001 does not break or rewrite this logic.
- `sap_b1_sync_page.md`: SAP B1 sync notes without secrets.
- `.env.example`: environment variable template. Real secrets must stay outside Git.
- `docs/`: V4 architecture and Codex task documentation.

## Run Locally

```bash
python3 portal_v2.py
```

Default local address:

```text
127.0.0.1:8088
```

Production should use Nginx or Caddy as an HTTPS reverse proxy.

## V4 Task001 Completed

- Minimal enterprise dashboard
- Unified archive framework
- Six archive modules: stores, employees, brands, products, suppliers, members
- Document center skeleton
- Knowledge center skeleton
- AI agent center skeleton
- Workflow center skeleton
- Content center route
- SAP B1 analysis API placeholders
- Mobile-first responsive UI preserved
- Documentation updated

## V4 Task003 Completed

- Knowledge Item model expanded for AI-ready enterprise memory
- Document-to-Knowledge pipeline foundation
- Document chunk model for future vector search
- Summary, keyword, tag, visibility, and embedding placeholders
- AI Query Center V1 with citation-ready answer structure
- Knowledge dashboard, search, detail pages, and JSON APIs
- Permission-safe knowledge visibility
- Existing login, role system, SAP B1 sync, and archive engine preserved

## V4 Task005 Completed

- AI CEO Daily Briefing page
- Business Cockpit V1
- Store Operations page
- Brand Operations page
- Inventory Risk page
- Osprey Pricing Risk analysis template and calculator API
- Task Center V1
- Health check endpoint
- Production deployment documentation
- Mobile-first card experience preserved

## V4 Routes

- `/`
- `/business-overview`
- `/stores`
- `/employees`
- `/brands`
- `/products`
- `/suppliers`
- `/members`
- `/documents`
- `/knowledge`
- `/knowledge/query`
- `/stores/operations`
- `/brands/operations`
- `/inventory/risk`
- `/brands/osprey-risk`
- `/tasks`
- `/system/health`
- `/agents`
- `/workflow`
- `/sap-sync`

## SAP Placeholder APIs

- `GET /api/sap/business-analysis`
- `GET /api/sap/profit-analysis`
- `GET /api/sap/inventory-analysis`
- `GET /api/sap/sales-trend`
- `GET /api/sap/ai-analysis`
- `GET /api/health`
- `GET /api/ai-ceo/daily-briefing`
- `GET /api/business/cockpit`
- `GET /api/tasks`

## Security

Never commit real passwords, database credentials, API keys, tokens, server IP allowlists, or private customer data.

Copy `.env.example` to `.env` on the server and fill real values there.
