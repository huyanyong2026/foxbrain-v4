# 52 SAP Nightly Sync

## Goal

SAP B1 data should sync every night at 22:00 server local time.

## Environment

```text
APP_TIMEZONE=Asia/Shanghai
SAP_SYNC_ENABLED=true
SAP_SYNC_TIME=22:00
SAP_SYNC_LOCK_TIMEOUT_MINUTES=120
SAP_SYNC_LOG_DIR=logs
SAP_SYNC_NOTIFY_ON_SUCCESS=false
SAP_SYNC_NOTIFY_ON_FAILURE=true
```

SAP credentials must stay in `.env` or server environment variables. Never commit real passwords.

## Manual Trigger

API:

```text
POST /api/sap/sync/run
```

The V1 app records sync history, respects a job lock and returns safe JSON. If SAP credentials are missing, it records a skipped run instead of pretending success.

## Schedule Option A: Cron

```cron
0 22 * * * cd /path/to/foxbrain-v4 && /usr/bin/python3 sync_sap_b1.py --trigger scheduled_22_00 >> logs/sap_sync.log 2>&1
```

## Schedule Option B: Systemd Timer

Use a timer that runs daily at 22:00 and calls the same sync command. Keep credentials in the service environment file.

## Schedule Option C: App Scheduler

APScheduler can be added later, but cron or systemd is safer for production because it avoids duplicate background threads.

## Lock

The `job_locks` table prevents duplicate sync jobs. If a job is already running and not expired, API returns:

```text
SAP sync is already running.
```

## Status

- `/sap-sync`
- `/data-pipeline`
- `GET /api/sap/sync/status`
- `GET /api/sap/sync/history`
- `GET /api/sap/sync/health`
- `GET /api/system/data-freshness`

## Rollback

Disable scheduled sync by setting:

```text
SAP_SYNC_ENABLED=false
```

Then stop the cron or systemd timer. Existing history records can remain for audit.
