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
        "/api/automation/framework",
        "/api/automation/scheduler",
        "/api/automation/retry-policy",
        "/api/automation/approval-policy",
        "/api/automation/notifications",
        "/api/automation/audit",
        "/api/automation/workflow-library",
        "/api/brain/framework",
        "/api/brain/memory",
        "/api/brain/decision-engine",
        "/api/brain/forecast",
        "/api/brain/simulation",
        "/api/brain/ai-council",
        "/api/brain/recommendation-contract",
        "/api/portal/framework",
        "/api/portal/sso",
        "/api/portal/navigation",
        "/api/portal/components",
        "/api/portal/messages",
        "/api/portal/tasks",
        "/api/portal/responsive",
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


def test_pack_automation_framework_present():
    portal = read("portal_v2.py")
    for field in ["risk_level", "approval_required", "approval_status", "retry_policy", "max_retries", "audit_status"]:
        assert f'"automations", "{field}"' in portal
    for field in ["attempt_no", "next_retry_at", "approval_id", "audit_event_id"]:
        assert f'"automation_runs", "{field}"' in portal
    for phrase in [
        "automation_framework_payload",
        "automation_scheduler_payload",
        "automation_retry_policy_payload",
        "automation_approval_policy_payload",
        "automation_is_high_risk",
        "high_risk_operations_are_never_auto_executed",
        "every_automation_run_and_retry_must_be_audited",
    ]:
        assert phrase in portal


def test_pack_enterprise_brain_present():
    portal = read("portal_v2.py")
    for field in ["evidence_json", "lineage_json", "permission_scope", "reviewed_by", "reviewed_at", "expansion_status"]:
        assert f'"memories", "{field}"' in portal
    for phrase in [
        "enterprise_brain_payload",
        "brain_memory_service_payload",
        "brain_decision_engine_payload",
        "brain_forecast_payload",
        "brain_simulation_payload",
        "brain_ai_council_payload",
        "all_ai_recommendations_must_cite_data_or_knowledge_basis",
        "no_basis_rule",
    ]:
        assert phrase in portal


def test_pack_mobile_portal_present():
    portal = read("portal_v2.py")
    for phrase in [
        "enterprise_portal",
        "portal_framework_payload",
        "portal_sso_payload",
        "portal_navigation_payload",
        "portal_message_center_payload",
        "portal_task_center_payload",
        "portal_component_contract_payload",
        "mobile_bottom_nav",
        "single_login_for_modules",
    ]:
        assert phrase in portal
    assert '"/portal"' in portal


def test_enterprise_pack_docs_present():
    for doc in [
        "docs/110_ENTERPRISE_PACK_01.md",
        "docs/111_ENTERPRISE_PACK_02_SAP_AI.md",
        "docs/112_ENTERPRISE_PACK_03_KNOWLEDGE.md",
        "docs/113_ENTERPRISE_PACK_04_AI_AGENTS.md",
        "docs/114_ENTERPRISE_PACK_05_DASHBOARD.md",
        "docs/115_ENTERPRISE_PACK_06_AUTOMATION.md",
        "docs/116_ENTERPRISE_PACK_07_ENTERPRISE_BRAIN.md",
        "docs/117_ENTERPRISE_PACK_08_MOBILE_PORTAL.md",
        "docs/CODEX_TASKS/Task041_Pack02_SAP_AI_Connector.md",
        "docs/CODEX_TASKS/Task042_Pack03_Knowledge_Platform.md",
        "docs/CODEX_TASKS/Task043_Pack04_AI_Agent_Framework.md",
        "docs/CODEX_TASKS/Task044_Pack05_Dashboard_Framework.md",
        "docs/CODEX_TASKS/Task045_Pack06_Automation_Framework.md",
        "docs/CODEX_TASKS/Task046_Pack07_Enterprise_Brain.md",
        "docs/CODEX_TASKS/Task047_Pack08_Mobile_Portal.md",
    ]:
        assert (ROOT / doc).exists()
