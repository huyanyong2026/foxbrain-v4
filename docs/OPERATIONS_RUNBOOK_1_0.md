# FoxBrain OS 1.0 Operations Runbook

## Startup

Use the Cloud Edition deployment flow documented in `README_CLOUD_DEPLOY.md`.

Required production files:

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `install.sh`
- `healthcheck.sh`
- `.github/workflows/deploy-cloud.yml`

## Monitoring

Primary endpoints:

- `/api/health`
- `/api/operations`
- `/api/product/release-1-0`
- `/api/product/architecture-review`

## Backup

Use `backup.sh` and keep backup files outside the application container lifecycle.

## Restore

Use `restore.sh`, then restart services and verify `/api/health`.

## Incident Response

1. Capture current health payload.
2. Check recent deployment or configuration changes.
3. Stop high-risk automations if needed.
4. Restore from backup if data integrity is affected.
5. Record the incident in the audit or timeline system.

## Upgrade Process

1. Pull latest `main`.
2. Run syntax checks and smoke tests.
3. Run deployment.
4. Verify login and `/api/health`.
5. Verify `/api/product/release-1-0`.
6. Keep rollback backup until the release is stable.

