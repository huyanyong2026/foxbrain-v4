# Task061 V6 Server Upgrade

## Source

Uploaded package: `FoxBrain_V6_Server_Upgrade_Codex_Package.zip`

## Status

In progress.

## Completed In Repository

- Added safe pre-upgrade backup flow to `install.sh`.
- Set install cron backup time to `02:30`.
- Kept SAP sync cron time at `22:00`.
- Added `deploy/pre_upgrade_backup.sh`.
- Added `deploy/server_health_check.sh`.
- Added `docs/130_V6_SERVER_UPGRADE_RUNBOOK.md`.
- Updated `.env.example` backup time to `02:30`.

## Server Execution Rules

- Back up before upgrade.
- Check before changing runtime mode.
- Do not delete existing production directories.
- Do not expose database or vector store ports publicly.
- Keep secrets in server `.env`, not GitHub.

## Next Server Steps

1. Run host-level backup on Tencent Cloud.
2. Run server health check.
3. Pull latest GitHub version.
4. Decide whether to keep current host-service portal or switch to Docker Compose.
5. If switching to Docker, run rollback rehearsal first.

## Acceptance

- `https://huyan.vafox.com` remains available.
- Login still works.
- SAP sync schedule remains `22:00`.
- Backup schedule is `02:30`.
- Server health report is saved after upgrade.
