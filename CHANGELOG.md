# Changelog

## 2026-07-05

- Added V6 autonomous cloud worker schedule for SAP sync, knowledge indexing, backup, daily report, web research, weekly report and monthly report.
- Added worker visibility to `healthcheck.sh`.
- Updated `/api/health` to expose V6 worker job schedule and app version.
- Preserved existing login, V5 pages, SAP sync and cloud deployment behavior.
- Imported FoxBrain OS Enterprise Pack 01 as the foundation engineering standard and aligned roadmap/docs.
- Integrated Pack 02 SAP and AI framework contracts for CEO dashboard, SAP connector and agent registry.
- Integrated Pack 03 enterprise knowledge platform framework with governance fields, ingestion status, retrieval contract and knowledge graph contract APIs.
- Added Task041 and Task042 documentation plus smoke-test coverage for the new enterprise pack framework.
- Integrated Pack 04 unified multi-agent framework with runtime, permission, tool interface, memory, approval and audit contracts.
- Marked pricing, contract and finance agent tools as high-risk actions that require human approval before execution.
- Integrated Pack 05 unified dashboard framework with KPI service, alert service, recommendation service and role-based cockpit contracts.
- Dashboard AI recommendations now include basis and review notes, and remain separated from raw business KPI data.
- Integrated Pack 06 unified automation framework with scheduler, retry policy, approval policy, notification and audit contracts.
- High-risk automations now default to pending approval and are blocked from automatic execution before review.
- Integrated Pack 07 Enterprise Brain framework with enterprise memory, decision engine, forecast, simulation and AI Council contracts.
- AI recommendation contracts now require data or knowledge basis and preserve human approval for high-risk decisions.
- Integrated Pack 08 unified enterprise portal with SSO contract, role navigation, shared components, message center and task center.
- Added `/portal` as the unified mobile-first portal entry for phone, tablet and desktop.
