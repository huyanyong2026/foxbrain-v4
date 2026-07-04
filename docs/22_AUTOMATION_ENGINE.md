# 22 Automation Engine / AI 自动化引擎

## 目标

Automation Engine 把 FoxBrain 的 AI 建议、SAP B1 数据、知识库、研究引擎、任务中心和通知中心连接成可执行流程。

当前版本提供安全框架、数据模型、页面和 API，占位等待后续接入 n8n、Dify、企业微信和 SAP 事件。

## 页面与 API

- `/automation`
- `GET /api/automation`
- `POST /api/automation`
- `GET /api/workflows`
- `POST /api/workflows`
- `GET /api/notifications`

## 模块

- Automation Dashboard
- Workflow Templates
- Trigger Manager
- Scheduled Jobs
- AI Actions
- Execution History
- Failed Jobs
- Notification Center

## 预置工作流模板

- Purchase Approval / 采购审批
- Payment Approval / 付款审批
- Recruitment / 招聘
- Employee Onboarding / 员工入职
- Employee Offboarding / 员工离职
- Contract Review / 合同审核
- Store Inspection / 门店巡检
- Inventory Check / 库存盘点
- Marketing Campaign / 营销活动
- Brand Launch / 品牌上新

## 触发器

- `manual`
- `scheduled`
- `sap_data_change`
- `document_uploaded`
- `knowledge_approved`
- `research_approved`
- `inventory_threshold`
- `sales_threshold`

## AI 动作

- `generate_summary`
- `create_task`
- `notify_manager`
- `generate_report`
- `suggest_purchasing`
- `suggest_markdown`
- `suggest_transfer`
- `create_meeting_note`

## 每日自动任务

- CEO Daily Briefing
- Inventory Risk Scan
- Sales Trend Scan
- Research Digest
- Knowledge Digest

## 安全原则

- 所有自动化创建需要登录。
- 管理类角色才能管理自动化。
- API 不返回任何密码、API Key 或数据库连接。
- 不假装 SAP、企业微信、短信、Dify 或 n8n 已完成集成。
