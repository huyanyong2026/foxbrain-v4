# 15 Deployment / 部署

## Local Start

```bash
python3 portal_v2.py
```

Default address:

```text
127.0.0.1:8088
```

## Production Recommendation

- Ubuntu server
- systemd service management
- Nginx or Caddy HTTPS reverse proxy
- `.env` / `portal.env` for real configuration
- Scheduled SAP B1 sync, normally once per day at 2:00

## Task005 Health Check

- UI: `/system/health`
- API: `/api/health`

The health check reports:

- app version
- environment
- database status
- SAP sync status
- document engine status
- knowledge engine status
- research engine status
- timestamp

It must not expose passwords, database credentials, API keys, tokens, or server secrets.

## Backup Before Upgrade

- `portal.db`
- `uploads/`
- `portal.env`
- `secret.key`

## Rollback Plan

1. Stop service.
2. Switch code back to the previous commit.
3. Restore database and uploads backup if needed.
4. Restart service.
5. Check `/api/health`.

## Security

- Do not commit passwords or API keys.
- Do not delete production database during deployment.
- Run syntax checks before restart.
- Keep rollback-ready backups before each upgrade.
