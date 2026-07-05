# FoxBrain V4 / 火狐狸企业 AI 操作系统

FoxBrain V4 is the FireFox Enterprise AI Operating System. It is built as a unified company entrance for AI, ERP data, CRM archives, documents, knowledge, workflow, and business analysis.

This repository upgrades the existing FoxBrain project without rewriting it. Existing login, roles, SAP B1 sync, APIs, and deployment assumptions are preserved.

## Cloud Edition

FoxBrain supports long-running deployment on an Ubuntu Tencent Cloud server.

- `Dockerfile`: container image definition
- `docker-compose.yml`: Cloud Edition service with `restart: always`
- `install.sh`: one-command Ubuntu installer
- `README_CLOUD_DEPLOY.md`: cloud deployment guide
- `deploy/nginx/foxbrain.conf.example`: Nginx reverse proxy example
- `.github/workflows/deploy-cloud.yml`: GitHub Actions deployment workflow

After deployment, FoxBrain runs on the cloud server. Your personal computer can be turned off.

## Enterprise Packs

- Pack 01: foundation engineering standard, cloud operating rules, environment safety, testing and documentation baseline.
- Pack 02: SAP B1 connector abstraction, CEO dashboard contract and shared AI agent registry.
- Pack 03: enterprise knowledge platform framework for ingestion, governance, retrieval, citations and knowledge graph contracts.
- Pack 04: unified multi-agent framework with role permissions, versioned tools, audit logs and approval gates.
- Pack 05: unified dashboard framework with KPI service, alert service and evidence-based AI recommendations.

The Pack 02, Pack 03, Pack 04 and Pack 05 implementation is additive. Existing login, mobile pages, cloud deployment, SAP sync status, knowledge pages, agent center pages and dashboard pages are preserved.

## Enterprise Knowledge Platform APIs

- `/api/knowledge/platform`
- `/api/knowledge/ingestion/status`
- `/api/knowledge/governance`
- `/api/knowledge/retrieval-contract`
- `/api/knowledge/graph-contract`
- `/api/sap/sync/connector`
- `/api/agents/registry`
- `/api/agents/framework`
- `/api/agents/tool-interface`
- `/api/agents/approval-policy`
- `/api/agents/audit-contract`
- `/api/dashboard/service`
- `/api/dashboard/kpis`
- `/api/dashboard/alerts`
- `/api/dashboard/recommendations`
- `/api/dashboard/finance`
- `/api/dashboard/store`

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

## V4 Task006 Completed

- AI Automation Center
- Workflow template framework
- Trigger manager placeholders
- AI action framework
- Execution history
- Notification Center
- Daily automation placeholders
- Automation APIs
- Health check now reports automation engine status

## V4 Task007 Completed

- AI Memory Center
- Memory review flow
- User preference system
- Decision Memory page
- Memory search
- Memory APIs
- AI CEO memory context placeholder
- Health check now reports memory engine status

## V4 Task008 Completed

- Enterprise Knowledge Graph Center
- Generic entity model
- Relationship model upgrade
- Rule-based graph extraction placeholder
- Entity network API
- Graph search
- Risk Map framework
- Osprey Risk Graph placeholder
- Health check now reports knowledge graph status

## V4 Task009 Completed

- Multi-Agent Collaboration Center
- Agent Role model
- Agent Task model
- Agent Discussion model
- Tool Registry
- Human Approval Gate
- Agent Output Standard
- Osprey multi-agent scenario template
- Health check now reports multi-agent engine status

## V4 Task010 Completed

- FoxBrain Jarvis unified AI assistant entrance
- Chat-style mobile-first interface
- Conversation and message persistence
- Keyword intent router
- Safe tool adapter layer for business, SAP, knowledge, memory, graph, agents, tasks and reports
- Citation-ready answer payload
- Human confirmation flow for important actions
- Report generation placeholder
- Voice input placeholder
- Health check now reports Jarvis status

## V4 Task011 Completed

- Reporting Engine and Report Center
- Report, report template and report schedule models
- Default report templates
- Draft generation framework
- Human review flow for approve, reject and archive
- Markdown and HTML export payloads
- n8n-ready scheduled report model
- Health check now reports Reporting Engine status

## V4 Task012 Completed

- Content Publishing Engine
- Content drafts, platform versions, campaigns and publish queue models
- AI content generator placeholder
- Review flow for public content
- Content calendar API
- Osprey communication template
- VAFOX brand content template
- Markdown, text and HTML export framework
- Jarvis content-generation integration
- Health check now reports Content Engine status

## V4 Task013 Completed

- Mobile Field Operation Center
- Field submission model
- Photo upload flow for mobile
- Store notes, product photos, customer feedback, inventory issues and competitor observations
- Mobile task view and completion
- Mobile review center
- Convert mobile submissions to tasks or knowledge drafts
- Enterprise WeChat placeholder
- Health check now reports Mobile Field Engine status

## V4 Task014 Completed

- Store Growth Engine
- Store diagnosis model
- Store growth plan model
- Store activity model
- Product and brand focus framework
- Growth-plan-to-task generation
- Store content and review report placeholders
- Jarvis store growth handoff
- Health check now reports Store Growth Engine status

## V4 Task015 Completed

- Brand Growth and Product Portfolio Engine
- Brand role classification framework
- Brand diagnosis model
- Brand strategy model
- Product portfolio model
- Pricing strategy model
- Supplier and rebate risk framework
- Osprey discount simulation handoff
- Inventory portfolio matrix placeholder
- Brand task generation framework
- Health check now reports Brand Growth Engine status

## V4 Task016 Completed

- Inventory and Purchasing Decision Engine
- Inventory risk model
- Replenishment suggestion model
- Transfer suggestion model
- Markdown and clearance suggestion model
- Future order tracking model
- Purchasing plan model
- Osprey inventory decision entry
- Cash occupation placeholder
- Inventory task generation framework
- Health check now reports Inventory Decision Engine status

## V4 Task017 Completed

- Finance and Profit Decision Engine
- Finance center upgrade
- Store profit analysis page
- Brand profit analysis page
- Profit record model
- Expense model
- Rebate model
- Cashflow watch placeholder
- Discount impact calculator
- Break-even calculator
- Finance task generation endpoint
- Health check now reports Finance Profit Engine status

## V4 Task018 Completed

- HR Performance and Incentive Engine
- HR center route
- Employee performance model
- Incentive plan model
- Store break-even incentive template
- Training and growth record models
- Recruitment candidate model
- AI employee evaluation placeholder
- HR task generation endpoint
- Health check now reports HR Performance Engine status

## V4 Task019 Completed

- Customer Membership and Private Domain Growth Engine
- Customer growth center route
- Customer segment model
- Customer tag model
- Private domain group model
- Customer follow-up model
- Customer event invitation model
- Customer value analysis placeholder
- Enterprise WeChat private-domain placeholder
- Customer growth task generation endpoint
- Health check now reports Customer Growth Engine status

## V4 Task020 Completed

- Unified Platform Kernel
- Module Registry
- Object Registry
- Global Search V2 placeholder
- Notification Center
- User Workspace
- Boss Workspace
- Employee Workspace
- System Settings
- Module Health dashboard
- Data Readiness dashboard
- AI Context Packet
- Risk Center
- Global Timeline
- Health check now reports Platform Kernel status

## V4 Task021 Completed

- Deep System Integration
- Data Pipeline Center
- SAP nightly sync schedule prepared for 22:00
- SAP sync history model
- SAP sync job lock model
- SAP sync status page upgrade
- Manual SAP sync trigger API
- SAP sync retry and health APIs
- Data freshness indicator
- Notification integration for sync result
- Production scheduler docs
- `.env.example` schedule variables
- Health check now reports Task021 sync status

## V4 Task022 Completed

- Operating System Layer
- App Launcher
- Role-based Desktop
- Unified Command Center
- AI Command Palette
- System-wide Object Actions
- Cross-module Context Bar
- Work Queue
- Approval Inbox
- Data Freshness OS Indicator
- System Upgrade Center
- AI OS Context
- Health check now reports Operating System Layer status

## V5 Cloud + Enterprise AI OS Upgrade

This repository now includes the first V5 cloud-safe framework. The priority is stable cloud running, data safety, SAP sync, knowledge, digital twin, AI memory, decision center, agent runtime, workflow center and mobile action consoles.

Cloud commands:

```bash
bash install.sh
bash deploy.sh
bash deploy.sh --pull
bash deploy.sh --build
bash deploy.sh --rollback
bash backup.sh
bash restore.sh /opt/foxbrain/backups/BACKUP_DIR
bash healthcheck.sh
docker compose up -d
docker compose ps
```

V5 routes:

- `/action/today`
- `/action/boss`
- `/action/store-manager`
- `/action/employee`
- `/operating-loop`
- `/decision-center`
- `/digital-twin`
- `/ai-memory`
- `/web-research-center`
- `/strategy`
- `/agents/marketplace`
- `/agents/workflows`
- `/agents/runtime`
- `/data-fabric`
- `/integrations`
- `/security`
- `/operations`
- `/product`
- `/help`

V5 safety rule: AI and agents can draft, summarize, plan and request approval. They must not change prices, approve purchasing, approve finance/HR actions, export sensitive data or publish externally without human approval.

## V6 Autonomous Cloud Execution

V6 adds a cloud worker that keeps the system moving even when the desktop is off.

Scheduled jobs:

- SAP sync: 22:00
- Knowledge index: 02:00
- Backup: 03:00
- Daily business report: 08:00
- Web research: 10:00
- Weekly report: Monday 09:00
- Monthly report: day 1 at 09:00

Implemented jobs run real scripts when available. Missing integrations are logged as placeholders and do not generate fake business conclusions.

Top-level documents:

- `CHANGELOG.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `DEPLOYMENT.md`
- `OPERATIONS.md`
- `BACKUP_RESTORE.md`

## Enterprise Pack 01

`FoxBrain_OS_Enterprise_Pack_01.zip` has been reviewed and aligned into the repository documentation. It confirms the foundation principles: SAP is the system of record, FoxBrain provides AI/knowledge/orchestration, and every change should preserve existing functionality while improving modularity, tests, deployment and documentation.

## V4 Routes

- `/`
- `/jarvis`
- `/reports`
- `/mobile`
- `/mobile/tasks`
- `/mobile/review`
- `/store-growth`
- `/brand-growth`
- `/inventory-decision`
- `/brands/osprey-inventory-decision`
- `/finance`
- `/finance/store-profit`
- `/finance/brand-profit`
- `/hr`
- `/customer-growth`
- `/workspace`
- `/boss`
- `/employee-workspace`
- `/settings`
- `/system/modules`
- `/system/data-readiness`
- `/data-pipeline`
- `/apps`
- `/desktop`
- `/command-center`
- `/work-queue`
- `/approvals`
- `/system/upgrade`
- `/notifications`
- `/risks`
- `/timeline`
- `/content`
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
- `/automation`
- `/memory`
- `/decisions`
- `/graph`
- `/agents/collaboration`
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
- `GET /api/automation`
- `GET /api/workflows`
- `GET /api/notifications`
- `GET /api/memory`
- `GET /api/preferences`
- `GET /api/decisions`
- `GET /api/graph`
- `GET /api/graph/entities`
- `GET /api/graph/relationships`
- `GET /api/graph/risk-map`
- `GET /api/agents/collaboration`
- `GET /api/agents/roles`
- `GET /api/agents/tasks`
- `GET /api/agents/tools`
- `GET /api/jarvis/status`
- `GET /api/jarvis/suggestions`
- `GET /api/jarvis/conversations`
- `GET /api/jarvis/conversations/{id}`
- `POST /api/jarvis/conversations`
- `POST /api/jarvis/message`
- `POST /api/jarvis/route-intent`
- `POST /api/jarvis/action/confirm`
- `POST /api/jarvis/report`
- `GET /api/reports`
- `POST /api/reports`
- `GET /api/reports/{id}`
- `PUT /api/reports/{id}`
- `POST /api/reports/{id}/generate`
- `POST /api/reports/{id}/approve`
- `POST /api/reports/{id}/reject`
- `POST /api/reports/{id}/archive`
- `POST /api/reports/{id}/export`
- `GET /api/report-templates`
- `POST /api/report-templates`
- `GET /api/report-schedules`
- `POST /api/report-schedules`
- `GET /api/content`
- `POST /api/content`
- `GET /api/content/{id}`
- `PUT /api/content/{id}`
- `POST /api/content/{id}/generate`
- `POST /api/content/{id}/submit-review`
- `POST /api/content/{id}/approve`
- `POST /api/content/{id}/reject`
- `GET /api/content/calendar`
- `GET /api/content/campaigns`
- `POST /api/content/campaigns`
- `GET /api/content/platform-versions`
- `POST /api/content/platform-versions`
- `GET /api/content/publish-queue`
- `POST /api/content/export`
- `GET /api/mobile`
- `GET /api/mobile/tasks`
- `POST /api/mobile/submissions`
- `GET /api/mobile/submissions`
- `GET /api/mobile/submissions/{id}`
- `PUT /api/mobile/submissions/{id}`
- `POST /api/mobile/submissions/{id}/approve`
- `POST /api/mobile/submissions/{id}/reject`
- `POST /api/mobile/submissions/{id}/convert-to-task`
- `POST /api/mobile/submissions/{id}/convert-to-knowledge`
- `GET /api/mobile/notifications`
- `GET /api/wecom/status`
- `GET /api/store-growth`
- `GET /api/store-growth/diagnosis`
- `POST /api/store-growth/diagnosis`
- `GET /api/store-growth/plans`
- `POST /api/store-growth/plans`
- `GET /api/store-growth/plans/{id}`
- `PUT /api/store-growth/plans/{id}`
- `POST /api/store-growth/plans/{id}/create-tasks`
- `GET /api/store-growth/activities`
- `POST /api/store-growth/activities`
- `GET /api/store-growth/focus`
- `POST /api/store-growth/focus`
- `GET /api/store-growth/reports`
- `POST /api/store-growth/reports`
- `GET /api/brand-growth`
- `GET /api/brand-growth/diagnosis`
- `POST /api/brand-growth/diagnosis`
- `GET /api/brand-growth/strategies`
- `POST /api/brand-growth/strategies`
- `GET /api/brand-growth/portfolio`
- `POST /api/brand-growth/portfolio`
- `GET /api/brand-growth/pricing`
- `POST /api/brand-growth/pricing`
- `POST /api/brand-growth/pricing/calculate`
- `GET /api/brand-growth/inventory-matrix`
- `GET /api/brand-growth/supplier-risk`
- `POST /api/brand-growth/create-tasks`
- `GET /api/inventory-decision`
- `GET /api/inventory-decision/risks`
- `POST /api/inventory-decision/risks`
- `GET /api/inventory-decision/replenishment`
- `POST /api/inventory-decision/replenishment`
- `GET /api/inventory-decision/transfers`
- `POST /api/inventory-decision/transfers`
- `GET /api/inventory-decision/markdowns`
- `POST /api/inventory-decision/markdowns`
- `GET /api/inventory-decision/future-orders`
- `POST /api/inventory-decision/future-orders`
- `GET /api/inventory-decision/purchasing-plans`
- `POST /api/inventory-decision/purchasing-plans`
- `GET /api/inventory-decision/cash-occupation`
- `GET /api/inventory-decision/osprey`
- `POST /api/inventory-decision/create-task`
- `GET /api/finance`
- `GET /api/finance/profit`
- `POST /api/finance/profit`
- `GET /api/finance/store-profit`
- `GET /api/finance/brand-profit`
- `GET /api/finance/expenses`
- `POST /api/finance/expenses`
- `GET /api/finance/cashflow`
- `GET /api/finance/rebates`
- `POST /api/finance/rebates`
- `POST /api/finance/discount-calculate`
- `POST /api/finance/break-even-calculate`
- `POST /api/finance/create-task`
- `GET /api/hr`
- `GET /api/hr/performance`
- `POST /api/hr/performance`
- `GET /api/hr/incentive-plans`
- `POST /api/hr/incentive-plans`
- `PUT /api/hr/incentive-plans/{id}`
- `POST /api/hr/incentive-plans/{id}/calculate`
- `GET /api/hr/training`
- `POST /api/hr/training`
- `GET /api/hr/growth-records`
- `POST /api/hr/growth-records`
- `GET /api/hr/candidates`
- `POST /api/hr/candidates`
- `GET /api/hr/ai-evaluation`
- `POST /api/hr/create-task`
- `GET /api/customer-growth`
- `GET /api/customer-growth/segments`
- `POST /api/customer-growth/segments`
- `GET /api/customer-growth/tags`
- `POST /api/customer-growth/tags`
- `GET /api/customer-growth/groups`
- `POST /api/customer-growth/groups`
- `GET /api/customer-growth/followups`
- `POST /api/customer-growth/followups`
- `GET /api/customer-growth/events`
- `POST /api/customer-growth/events`
- `GET /api/customer-growth/value-analysis`
- `POST /api/customer-growth/create-task`
- `GET /api/system/modules`
- `GET /api/system/objects`
- `GET /api/system/health`
- `GET /api/system/data-readiness`
- `GET /api/search/global`
- `GET /api/workspace`
- `GET /api/boss`
- `GET /api/employee-workspace`
- `GET /api/settings`
- `PUT /api/settings`
- `GET /api/ai/context-packet`
- `GET /api/risks`
- `POST /api/risks`
- `GET /api/timeline/global`
- `GET /api/sap/sync/status`
- `GET /api/sap/sync/history`
- `POST /api/sap/sync/run`
- `POST /api/sap/sync/retry/{sync_id}`
- `GET /api/sap/sync/logs/{sync_id}`
- `GET /api/sap/sync/health`
- `GET /api/data-pipeline`
- `GET /api/system/data-freshness`
- `GET /api/apps`
- `GET /api/desktop`
- `GET /api/command-center`
- `GET /api/command-palette`
- `POST /api/command-palette/execute`
- `GET /api/object-actions`
- `GET /api/context-bar`
- `GET /api/work-queue`
- `GET /api/approvals`
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject`
- `GET /api/os/data-freshness`
- `GET /api/system/upgrade`
- `GET /api/os/context`

## Security

Never commit real passwords, database credentials, API keys, tokens, server IP allowlists, or private customer data.

Copy `.env.example` to `.env` on the server and fill real values there.
