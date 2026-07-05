# Enterprise Pack 02 - SAP and AI Framework

## Purpose

Pack 02 adds the enterprise connector layer for SAP B1 and the shared framework used by FoxBrain AI agents.

The current implementation is intentionally additive. Existing login, dashboard, knowledge center, SAP sync status, cloud deployment, and worker scheduling remain unchanged.

## SAP Position

SAP B1 remains the system of record for business data.

Initial sync domains:

- Products
- Inventory
- Members
- Sales
- Purchasing

Rules:

- Prefer incremental sync.
- Record every sync attempt.
- Retry failed jobs safely.
- Do not write back to SAP until explicit business rules are approved.
- Keep real credentials in `.env`; never commit secrets.

## AI Agent Framework

Initial agents:

- AI CEO
- AI CFO
- AI Store Manager
- AI Inventory Manager
- AI Product Manager
- AI Customer Service
- AI HR

Shared agent capabilities:

- Tool interface
- Role-based permissions
- Memory abstraction
- Knowledge center access
- Audit logging
- Human approval gate for important actions

## Implemented Contracts

- `/api/dashboard/ceo`
- `/api/sap/sync/connector`
- `/api/agents/registry`
- `/api/health`

## Next Work

- Connect real SAP incremental queries through the existing nightly sync job.
- Add conflict detection for SAP records.
- Add agent tool execution logs.
- Keep all sensitive settings in `.env`.
