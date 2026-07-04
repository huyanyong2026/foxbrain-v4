# 28 FoxBrain Jarvis / Enterprise AI Assistant

## Goal

FoxBrain Jarvis is the unified AI assistant entrance for the company. It connects the existing FoxBrain modules without rewriting them:

- Business cockpit and SAP B1 summary
- Knowledge Center
- Memory Engine
- Knowledge Graph
- Task Center
- Automation Engine
- Multi-Agent Collaboration
- Document Center placeholders

Jarvis V1 uses a safe keyword intent router. It does not invent business facts when no source exists.

## Route

- Page: `/jarvis`
- Status API: `GET /api/jarvis/status`

## Conversation Model

`jarvis_conversations`

- `conversation_id`
- `user_id`
- `title`
- `status`
- `created_at`
- `updated_at`

`jarvis_messages`

- `message_id`
- `conversation_id`
- `role`
- `content`
- `intent`
- `tool_calls`
- `cited_sources`
- `related_objects`
- `confidence`
- `created_at`

## Supported Intents

- `general_question`
- `business_query`
- `sap_query`
- `knowledge_query`
- `research_query`
- `memory_query`
- `graph_query`
- `agent_collaboration`
- `task_creation`
- `report_generation`
- `content_generation`
- `system_help`

## Tool Adapter Standard

Every adapter returns:

```json
{
  "success": true,
  "data": {},
  "sources": [],
  "limitations": [],
  "next_actions": []
}
```

## Human Confirmation

Jarvis may suggest actions, but important actions require human confirmation:

- Create task
- Approve knowledge
- Change memory
- Trigger automation
- Send notification
- Generate official report
- Update archive
- Modify pricing rule

Jarvis V1 stores suggested actions in `jarvis_action_confirmations`.

## Mobile UX

The Jarvis page is mobile-first:

- Large chat input
- Suggested question chips
- Message cards
- Source-ready answer panel
- Pending action card
- Voice input placeholder

## Safety Rules

- No secrets in messages.
- No fake SAP, finance, customer or market facts.
- Restricted data must follow role permissions.
- Reports generated in V1 are drafts/placeholders until reviewed.
