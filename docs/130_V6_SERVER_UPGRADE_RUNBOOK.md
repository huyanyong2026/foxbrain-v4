# FoxBrain V6 Server Upgrade Runbook

This runbook turns the uploaded V6 server upgrade package into a safe operating procedure for `https://huyan.vafox.com`.

## Goal

- Keep the current FoxBrain portal stable.
- Back up before every server upgrade.
- Standardize Docker Compose, PostgreSQL, Redis, MinIO, Qdrant, n8n placeholders and Wiki.js placeholders.
- Keep SAP B1 sync scheduled at `22:00`.
- Keep daily backup scheduled at `02:30`.
- Verify security, HTTPS, firewall, health checks and rollback readiness.

## Safety Rules

- Do not delete `/opt/foxbrain`, `/opt/firefox-portal`, `/opt/firefox-sap-sync`, `/etc/nginx` or `/etc/letsencrypt` before a backup is complete.
- Do not expose PostgreSQL, Redis, Qdrant or MinIO data ports to the public internet.
- Keep real passwords and API keys only in the server `.env`.
- High-risk automation must keep a manual approval step.

## Current Repository Coverage

- `docker-compose.yml`: FoxBrain Web, API, worker, PostgreSQL, Redis, MinIO, Qdrant, Nginx and optional n8n / Dify / Wiki.js placeholders.
- `install.sh`: one-command installation with pre-upgrade backup and cron setup.
- `backup.sh`: Docker data backup.
- `healthcheck.sh`: Docker application health check.
- `deploy/pre_upgrade_backup.sh`: host-level backup before migration or upgrade.
- `deploy/server_health_check.sh`: host-level validation after upgrade.
- `.env.example`: production environment variable template.

## Recommended Server Procedure

1. Confirm the Tencent Cloud snapshot is available.
2. Run host backup:

```bash
cd /opt/foxbrain
bash deploy/pre_upgrade_backup.sh
```

3. Pull latest GitHub version:

```bash
cd /opt/foxbrain
git pull --ff-only
```

4. Rebuild Docker version only when ready:

```bash
cd /opt/foxbrain
docker compose up -d --build
```

5. Verify:

```bash
cd /opt/foxbrain
bash healthcheck.sh
bash deploy/server_health_check.sh
```

## Scheduled Jobs

SAP B1 sync:

```text
0 22 * * * root cd /opt/foxbrain && docker compose exec -T foxbrain-worker python sync_sap_b1.py --trigger scheduled_22_00 >> /opt/foxbrain/logs/sap_sync.log 2>&1
```

Daily backup:

```text
30 2 * * * root /opt/foxbrain/backup.sh >> /opt/foxbrain/logs/backup.log 2>&1
```

## Acceptance Checklist

- CPU, memory and disk are recorded.
- Timezone is `Asia/Shanghai`.
- Docker and Docker Compose are installed.
- FoxBrain portal can be opened and logged into.
- HTTPS is valid.
- UFW allows only required public ports.
- Fail2ban is running.
- PostgreSQL is healthy.
- Redis is healthy.
- MinIO is healthy or explicitly kept internal.
- Qdrant is running or explicitly kept internal.
- SAP sync schedule shows `22:00`.
- Backup schedule shows `02:30`.
- A rollback backup exists under `/opt/backups`.

## Notes

The existing production portal may still run as a host service during transition. Do not force-switch to Docker until backup, health check and rollback verification are complete.
