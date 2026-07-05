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
        "/api/memory/framework",
        "/api/memory/repository",
        "/api/memory/governance",
        "/api/memory/timeline",
        "/api/memory/retrieval",
        "/api/memory/decision-history",
        "/api/memory/ai-contract",
        "/api/product/release-readiness",
        "/api/product/deployment-standard",
        "/api/product/observability",
        "/api/product/rollback",
        "/api/product/security-review",
        "/api/product/production-checklist",
        "/api/security/framework",
        "/api/security/identity-access",
        "/api/security/rbac",
        "/api/security/audit",
        "/api/security/audit-export",
        "/api/security/data-governance",
        "/api/security/backup-recovery",
        "/api/security/approval-governance",
        "/api/sdk/framework",
        "/api/sdk/manifest-schema",
        "/api/sdk/extension-points",
        "/api/sdk/versioning",
        "/api/sdk/backward-compatibility",
        "/api/extensions/contracts",
        "/api/extensions/registry",
        "/api/marketplace/apps",
        "/api/data-intelligence/framework",
        "/api/kpi/catalog",
        "/api/kpi/metrics",
        "/api/data-intelligence/model",
        "/api/data-quality/monitor",
        "/api/insights/engine",
        "/api/trends",
        "/api/digital-twin/framework",
        "/api/digital-twin/entities",
        "/api/digital-twin/relationships",
        "/api/digital-twin/state-history",
        "/api/digital-twin/simulation",
        "/api/digital-twin/visualization",
        "/api/decision-engine/framework",
        "/api/decision-engine/risk-scoring",
        "/api/decision-engine/opportunities",
        "/api/decision-engine/recommendations",
        "/api/decision-engine/approval-gate",
        "/api/strategy-center/framework",
        "/api/strategy-center/okr",
        "/api/strategy-center/models",
        "/api/strategy-center/scenario-comparison",
        "/api/strategy-center/expansion-analysis",
        "/api/strategy-center/brand-product-strategy",
        "/api/strategy-center/dashboard",
        "/api/university/framework",
        "/api/university/catalog",
        "/api/university/learning-paths",
        "/api/university/ai-tutor",
        "/api/university/certification",
        "/api/university/progress",
        "/api/university/knowledge-feedback",
        "/api/growth-engine/framework",
        "/api/growth-engine/scorecard",
        "/api/growth-engine/store-growth",
        "/api/growth-engine/brand-product",
        "/api/growth-engine/customer-growth",
        "/api/growth-engine/executive-scorecard",
        "/api/executive-command-center/framework",
        "/api/executive-command-center/dashboard",
        "/api/executive-command-center/risks",
        "/api/executive-command-center/ai-command",
        "/api/executive-command-center/system-health",
        "/api/executive-command-center/modules",
        "/api/executive-command-center/monitoring",
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


def test_pack_enterprise_memory_present():
    portal = read("portal_v2.py")
    for field in ["owner", "tags", "access_level", "retention_policy", "version"]:
        assert f'"memories", "{field}"' in portal
    for phrase in [
        "enterprise_memory_repository_payload",
        "enterprise_memory_governance_payload",
        "enterprise_memory_timeline_payload",
        "enterprise_memory_retrieval_payload",
        "enterprise_decision_history_payload",
        "enterprise_memory_ai_contract_payload",
        "permission_filter_before_agent_context",
        "agent_answers_must_cite_memory_id_or_source",
    ]:
        assert phrase in portal


def test_pack_release_production_present():
    portal = read("portal_v2.py")
    for phrase in [
        "release_readiness_payload",
        "release_deployment_standard_payload",
        "release_observability_payload",
        "release_backup_restore_payload",
        "release_security_review_payload",
        "release_checklist_payload",
        "release_candidate_ready",
        "deployment_repeatability_status",
        "rollback_status",
    ]:
        assert phrase in portal


def test_pack_security_governance_present():
    portal = read("portal_v2.py")
    for phrase in [
        "security_governance_payload",
        "security_identity_access_payload",
        "security_rbac_payload",
        "security_audit_payload",
        "security_audit_export_payload",
        "security_data_governance_payload",
        "security_backup_recovery_payload",
        "security_approval_governance_payload",
        "all_ai_workflow_approval_and_system_config_changes_must_be_traceable",
        "high_risk_default",
    ]:
        assert phrase in portal


def test_pack_sdk_marketplace_present():
    portal = read("portal_v2.py")
    for phrase in [
        "sdk_platform_payload",
        "sdk_manifest_schema_payload",
        "sdk_extension_points_payload",
        "sdk_versioning_payload",
        "sdk_backward_compatibility_payload",
        "sdk_marketplace_payload",
        "sdk_plugin_registry_payload",
        "plugin_manifest",
        "extension_points",
        "semantic_versioning_required",
        "new_capabilities_prefer_plugins_before_core_changes",
        "existing_plugin_contracts_must_continue_to_work_across_minor_and_patch_releases",
        "manual_review_required_before_extension_can_modify_price_contract_finance_or_external_publish_data",
    ]:
        assert phrase in portal


def test_pack_data_intelligence_present():
    portal = read("portal_v2.py")
    for phrase in [
        "unified_kpi_catalog_payload",
        "unified_data_model_payload",
        "unified_metrics_service_payload",
        "data_quality_monitor_payload",
        "trend_api_payload",
        "insight_engine_payload",
        "data_intelligence_framework_payload",
        "all_dashboards_agents_and_decision_engines_must_use_this_kpi_catalog_to_avoid_duplicate_calculation",
        "dashboard_agent_and_decision_engine_kpis_must_come_from_unified_metrics_service",
        "all_ai_insights_must_reference_explicit_data_evidence",
        "quality_warnings_must_be_visible_before_ai_insights_are_trusted",
        "canonical_entities",
    ]:
        assert phrase in portal


def test_pack_digital_twin_present():
    portal = read("portal_v2.py")
    for phrase in [
        "digital_twin_entity_registry_payload",
        "digital_twin_relationship_service_payload",
        "digital_twin_state_engine_payload",
        "digital_twin_simulation_payload",
        "digital_twin_visualization_payload",
        "digital_twin_framework_payload",
        "digital_twin_get",
        "simulation_must_not_modify_production_data",
        "read_only_twin_and_sandboxed_simulations_never_modify_production_data",
        "relationships_should_be_queryable_versioned_and_traceable_to_source",
        "snapshots_are_append_only_and_never_overwrite_production_data",
        "brain_simulation_uses_digital_twin_sandbox_and_never_modifies_production_data",
    ]:
        assert phrase in portal


def test_pack_decision_engine_present():
    portal = read("portal_v2.py")
    for phrase in [
        "enterprise_decision_engine_payload",
        "decision_risk_scoring_payload",
        "decision_opportunity_engine_payload",
        "explainable_recommendations_payload",
        "decision_approval_gate_payload",
        "decision_engine_get",
        "all_business_recommendations_must_show_basis_risk_score_and_confidence",
        "each_decision_risk_score_must_include_rationale_and_evidence",
        "high_risk_decision_actions_must_enter_human_approval_and_must_not_auto_execute",
        "decision_engine_can_recommend_and_request_approval_but_must_not_auto_execute_high_risk_actions",
        "must_use_unified_data_model",
        "must_use_unified_kpi_catalog",
        "must_use_enterprise_knowledge",
    ]:
        assert phrase in portal


def test_pack_ai_strategy_center_present():
    portal = read("portal_v2.py")
    for phrase in [
        "ai_strategy_center_payload",
        "strategy_okr_service_payload",
        "strategy_model_payload",
        "strategy_scenario_comparison_payload",
        "strategy_expansion_analysis_payload",
        "strategy_brand_product_payload",
        "strategy_dashboard_payload",
        "strategy_center_get",
        "strategy_okrs_must_link_to_unified_kpi_catalog_and_metrics_service",
        "strategy_models_must_use_unified_data_model_enterprise_knowledge_operating_metrics_and_history",
        "strategy_scenarios_are_compared_in_digital_twin_sandbox_and_do_not_modify_production_data",
        "strategy_analysis_must_remain_consistent_with_enterprise_decision_engine_digital_twin_and_data_intelligence",
    ]:
        assert phrase in portal


def test_pack_foxbrain_university_present():
    portal = read("portal_v2.py")
    for phrase in [
        "foxbrain_university_payload",
        "university_learning_catalog_payload",
        "university_learning_paths_payload",
        "university_ai_tutor_payload",
        "university_certification_payload",
        "university_progress_payload",
        "university_knowledge_feedback_payload",
        "university_get",
        "enterprise_knowledge_platform_and_learning_center_are_bidirectionally_connected",
        "learning_paths_are_recommendations_and_do_not_change_business_permissions_automatically",
        "certification_results_can_support_employee_growth_but_must_not_automatically_change_business_permissions",
        "learning_results_never_auto_grant_business_permissions_manager_rules_decide",
        "learning_questions_improve_knowledge_base_after_review_not_direct_publish",
    ]:
        assert phrase in portal


def test_pack_growth_engine_present():
    portal = read("portal_v2.py")
    for phrase in [
        "enterprise_growth_engine_payload",
        "growth_scorecard_payload",
        "store_growth_analytics_payload",
        "brand_product_growth_payload",
        "customer_growth_models_payload",
        "executive_growth_scorecard_payload",
        "growth_engine_get",
        "growth_scores_must_be_traceable_to_unified_data_model_kpi_and_decision_engine",
        "all_growth_recommendations_must_be_explainable_and_traceable_to_data_sources",
        "store_growth_recommendations_must_trace_to_metrics_tasks_and_knowledge",
        "brand_and_product_growth_scores_must_reference_category_brand_product_and_promotion_sources",
        "customer_growth_recommendations_must_trace_to_member_segments_loyalty_and_campaign_sources",
    ]:
        assert phrase in portal


def test_pack_executive_command_center_present():
    portal = read("portal_v2.py")
    for phrase in [
        "executive_command_center_payload",
        "executive_command_dashboard_payload",
        "executive_risk_center_payload",
        "executive_ai_command_payload",
        "executive_system_health_payload",
        "executive_module_monitoring_payload",
        "executive_command_center_get",
        "unified_enterprise_management_entry",
        "all_command_center_modules_follow_rbac_and_default_deny",
        "all_command_center_data_uses_unified_data_model_and_metrics_service",
        "system_health_rolls_up_all_modules_into_unified_monitoring",
        "ai_command_can_draft_route_and_request_approval_but_must_not_bypass_permissions",
        "executive_risk_center_uses_unified_risk_inputs_and_traceable_evidence",
    ]:
        assert phrase in portal


def test_production_deployment_files_present():
    for file_name in [
        "Dockerfile",
        "docker-compose.yml",
        ".env.example",
        "install.sh",
        "healthcheck.sh",
        "backup.sh",
        "restore.sh",
        "README_CLOUD_DEPLOY.md",
        "README_BACKUP_RESTORE.md",
        ".github/workflows/deploy-cloud.yml",
    ]:
        assert (ROOT / file_name).exists()


def test_production_compose_health_and_restart():
    compose = read("docker-compose.yml")
    for phrase in ["restart: always", "healthcheck:", "foxbrain-web", "foxbrain-worker", "nginx"]:
        assert phrase in compose


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
        "docs/118_ENTERPRISE_PACK_09_ENTERPRISE_MEMORY.md",
        "docs/119_ENTERPRISE_PACK_10_RELEASE_PRODUCTION.md",
        "docs/120_ENTERPRISE_PACK_11_SECURITY_GOVERNANCE.md",
        "docs/121_ENTERPRISE_PACK_12_SDK_MARKETPLACE.md",
        "docs/122_ENTERPRISE_PACK_13_DATA_INTELLIGENCE.md",
        "docs/123_ENTERPRISE_PACK_14_DIGITAL_TWIN.md",
        "docs/124_ENTERPRISE_PACK_15_DECISION_ENGINE.md",
        "docs/125_ENTERPRISE_PACK_16_AI_STRATEGY_CENTER.md",
        "docs/126_ENTERPRISE_PACK_17_FOXBRAIN_UNIVERSITY.md",
        "docs/127_ENTERPRISE_PACK_18_GROWTH_ENGINE.md",
        "docs/128_ENTERPRISE_PACK_19_COMMAND_CENTER.md",
        "docs/SDK_EXTENSION_STANDARD.md",
        "docs/RELEASE_1_0_PRODUCTION_CHECKLIST.md",
        "docs/CODEX_TASKS/Task041_Pack02_SAP_AI_Connector.md",
        "docs/CODEX_TASKS/Task042_Pack03_Knowledge_Platform.md",
        "docs/CODEX_TASKS/Task043_Pack04_AI_Agent_Framework.md",
        "docs/CODEX_TASKS/Task044_Pack05_Dashboard_Framework.md",
        "docs/CODEX_TASKS/Task045_Pack06_Automation_Framework.md",
        "docs/CODEX_TASKS/Task046_Pack07_Enterprise_Brain.md",
        "docs/CODEX_TASKS/Task047_Pack08_Mobile_Portal.md",
        "docs/CODEX_TASKS/Task048_Pack09_Enterprise_Memory.md",
        "docs/CODEX_TASKS/Task049_Pack10_Release_Production.md",
        "docs/CODEX_TASKS/Task050_Pack11_Security_Governance.md",
        "docs/CODEX_TASKS/Task051_Pack12_SDK_Marketplace.md",
        "docs/CODEX_TASKS/Task052_Pack13_Data_Intelligence.md",
        "docs/CODEX_TASKS/Task053_Pack14_Digital_Twin.md",
        "docs/CODEX_TASKS/Task054_Pack15_Decision_Engine.md",
        "docs/CODEX_TASKS/Task055_Pack16_AI_Strategy_Center.md",
        "docs/CODEX_TASKS/Task056_Pack17_FoxBrain_University.md",
        "docs/CODEX_TASKS/Task057_Pack18_Growth_Engine.md",
        "docs/CODEX_TASKS/Task058_Pack19_Command_Center.md",
    ]:
        assert (ROOT / doc).exists()
