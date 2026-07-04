# 29 Reporting Engine / AI Report Center

## Goal

The Reporting Engine turns business data, knowledge, memory, graph context and tasks into reviewable report drafts.

AI generated reports are not official until a human reviewer approves them.

## Route

- Page: `/reports`

## Models

`reports`

- `report_id`
- `title`
- `report_type`
- `date_range_start`
- `date_range_end`
- `object_type`
- `object_id`
- `status`
- `summary`
- `key_findings`
- `risks`
- `opportunities`
- `recommended_actions`
- `data_sources`
- `cited_documents`
- `cited_research`
- `cited_memory`
- `cited_sap_records`
- `generated_by`
- `reviewed_by`
- `reviewed_at`
- `created_at`
- `updated_at`

`report_templates`

- `template_id`
- `template_name`
- `report_type`
- `description`
- `sections`
- `required_sources`
- `default_date_range`
- `visibility`
- `created_at`
- `updated_at`

`report_schedules`

- `schedule_id`
- `report_template_id`
- `frequency`
- `recipients`
- `enabled`
- `last_run_at`
- `next_run_at`
- `created_by`
- `created_at`

## Default Templates

- CEO Daily Report
- Weekly Business Report
- Monthly Business Report
- Store Report
- Brand Report
- Inventory Risk Report
- Research Report
- Osprey Pricing Risk Report
- Task Execution Report

## Review Flow

Generate -> Edit -> Approve / Reject -> Archive -> Export

Supported export placeholders:

- Markdown
- HTML

PDF and Word export are reserved for later versions.

## Task014 Store Review Reports

Store growth plans and activities can feed store review report drafts.

Recommended sections:

- Goal
- Result
- What worked
- What failed
- Customer feedback
- Staff execution
- Inventory impact
- Next actions

## Safety

- No fake SAP, finance, inventory, customer or market facts.
- Drafts must cite available sources.
- Official reports require human review.
- Scheduled reports are prepared for n8n execution after the daily 2:00 SAP sync.
