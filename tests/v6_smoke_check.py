import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_compose_core_services():
    text = read("docker-compose.yml")
    for service in ["foxbrain-web", "foxbrain-api", "foxbrain-worker", "postgres", "redis", "minio", "qdrant", "nginx"]:
        assert service in text
    assert text.count("restart: always") >= 8


def test_v6_worker_schedule_envs():
    env = read(".env.example")
    for key in ["SAP_SYNC_TIME", "KNOWLEDGE_INDEX_TIME", "BACKUP_TIME", "DAILY_REPORT_TIME", "WEB_RESEARCH_TIME", "WEEKLY_REPORT_TIME", "MONTHLY_REPORT_DAY"]:
        assert key in env


def test_v6_routes_present():
    portal = read("portal_v2.py")
    for route in ["/action/today", "/operating-loop", "/digital-twin", "/ai-memory", "/data-fabric", "/operations"]:
        assert route in portal


def test_enterprise_pack_routes_present():
    portal = read("portal_v2.py")
    for route in [
        "/api/dashboard/ceo",
        "/api/sap/sync/connector",
        "/api/agents/registry",
        "/api/knowledge/platform",
        "/api/knowledge/ingestion/status",
        "/api/knowledge/governance",
        "/api/knowledge/retrieval-contract",
        "/api/knowledge/graph-contract",
        "/api/agents/framework",
        "/api/agents/runtime-contract",
        "/api/agents/permissions",
        "/api/agents/tool-interface",
        "/api/agents/memory-contract",
        "/api/agents/approval-policy",
        "/api/agents/audit-contract",
        "/api/dashboard/service",
        "/api/dashboard/kpis",
        "/api/dashboard/alerts",
        "/api/dashboard/recommendations",
        "/api/dashboard/finance",
        "/api/dashboard/store",
    ]:
        assert route in portal


def test_pack_knowledge_governance_schema_present():
    portal = read("portal_v2.py")
    for field in ["owner", "department", "version", "retention_policy", "deleted_at"]:
        assert f'"knowledge_items", "{field}"' in portal


def test_pack_agent_tool_governance_schema_present():
    portal = read("portal_v2.py")
    for field in ["tool_category", "tool_version", "risk_level", "approval_required", "audit_event"]:
        assert f'"agent_tools", "{field}"' in portal
    for phrase in ["Price Decision Draft", "Contract Review Draft", "Finance Action Draft", "high_risk_actions_blocked_until_approved"]:
        assert phrase in portal


def test_pack_dashboard_framework_present():
    portal = read("portal_v2.py")
    for phrase in [
        "dashboard_kpi_service_payload",
        "dashboard_alert_service_payload",
        "dashboard_recommendation_service_payload",
        "unified_dashboard_data_service",
        "business_recommendations_must_show_basis_for_manager_review",
        "ai_recommendations_and_alerts_are_independent_components_not_mixed_into_raw_business_data",
    ]:
        assert phrase in portal


def test_enterprise_pack_docs_present():
    for doc in [
        "docs/110_ENTERPRISE_PACK_01.md",
        "docs/111_ENTERPRISE_PACK_02_SAP_AI.md",
        "docs/112_ENTERPRISE_PACK_03_KNOWLEDGE.md",
        "docs/113_ENTERPRISE_PACK_04_AI_AGENTS.md",
        "docs/114_ENTERPRISE_PACK_05_DASHBOARD.md",
        "docs/CODEX_TASKS/Task041_Pack02_SAP_AI_Connector.md",
        "docs/CODEX_TASKS/Task042_Pack03_Knowledge_Platform.md",
        "docs/CODEX_TASKS/Task043_Pack04_AI_Agent_Framework.md",
        "docs/CODEX_TASKS/Task044_Pack05_Dashboard_Framework.md",
    ]:
        assert (ROOT / doc).exists()
