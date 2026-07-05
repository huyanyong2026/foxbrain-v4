# Enterprise Pack 04 - Enterprise AI Agent Platform

## Purpose

Pack 04 defines the unified multi-agent framework for FoxBrain.

All agents must follow the same runtime, permission checks, tool interface, memory model, approval rules, and audit mechanism.

## Initial Agent Catalog

- CEO Agent
- Finance Agent
- Store Agent
- Inventory Agent
- Product Agent
- Customer Agent
- Supplier Agent
- HR Agent
- Training Agent
- Content Agent
- Meeting Agent
- Analytics Agent

## Runtime

Standard runtime:

1. Agent request
2. Permission check
3. Retrieve knowledge
4. Query SAP if authorized
5. Reason
6. Generate recommendation
7. Request approval if needed
8. Execute approved workflow
9. Log result

## Unified Tool Interface

Tool categories:

- SAP
- Knowledge
- Workflow
- Reporting
- Notifications
- Files

All tools expose versioned interfaces and declare:

- Tool ID
- Tool name
- Category
- Version
- Input schema
- Output schema
- Required permission
- Risk level
- Approval requirement

## High-Risk Approval

The following operations must keep human approval:

- Price changes
- Discount policy
- Contract decisions
- Finance payments
- SAP write-back
- External publishing
- Mass notifications

Default policy:

- High-risk actions are created as drafts.
- Execution is blocked before approval.
- Review roles are boss, admin, and finance.
- All decisions are written to the audit log.

## Memory Model

- Short-term session memory
- Long-term enterprise memory
- Knowledge retrieval
- Conversation context
- Audit trail

Important memory writes require human review.

## Implemented Contracts

- `/api/agents/framework`
- `/api/agents/registry`
- `/api/agents/runtime-contract`
- `/api/agents/permissions`
- `/api/agents/tool-interface`
- `/api/agents/memory-contract`
- `/api/agents/approval-policy`
- `/api/agents/audit-contract`

## Acceptance

- Multiple agents can be registered.
- Permissions are described by one contract.
- Tools use a unified versioned interface.
- High-risk actions require approval.
- Audit mechanism is documented and exposed.
- Pack 01 to Pack 04 are linked in docs and tests.
