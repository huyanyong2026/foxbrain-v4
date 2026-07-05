# 19 Business Cockpit / 经营驾驶舱

## 目标

经营驾驶舱是老板级经营看板，聚合销售、毛利、库存、门店、品牌、员工、异常提醒和 AI 建议。

## 页面

- `/business-overview`
- `/overview`
- `GET /api/business/cockpit`

## V1 卡片

- 今日销售
- 本月销售
- 毛利情况
- 库存金额
- 门店排名
- 品牌排名
- 异常提醒
- AI 建议

## 设计原则

- 手机优先
- 卡片式信息
- 不做密集 ERP 表格
- 没有数据时显示清晰空状态
- 每个卡片可继续进入详情页

## 后续升级

- 门店排名真实数据
- 品牌排名真实数据
- 员工表现
- 现金流风险
- AI 自动诊断

## Task011 Reporting Engine

The Business Cockpit is one of the main structured inputs for report drafts.

Report output must keep the same data principle as the cockpit: show waiting/empty state when real SAP B1 or reviewed internal data is not available.
## Task021 SAP Freshness Integration

Business Cockpit should show SAP sync freshness, last sync status and a link to `/sap-sync`.

If SAP data is stale or failed, the cockpit must not pretend business data is current.
