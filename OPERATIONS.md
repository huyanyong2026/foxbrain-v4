# Operations

## Daily Checks

```bash
cd /opt/foxbrain
bash healthcheck.sh
docker compose ps
docker compose logs --tail=100 foxbrain-worker
```

## Worker Schedule

- SAP sync: `SAP_SYNC_TIME`, default `22:00`
- Knowledge index: `KNOWLEDGE_INDEX_TIME`, default `02:00`
- Backup: `BACKUP_TIME`, default `02:30`
- Daily report: `DAILY_REPORT_TIME`, default `08:00`
- Web research: `WEB_RESEARCH_TIME`, default `10:00`
- Weekly report: `WEEKLY_REPORT_TIME`, default `MON 09:00`
- Monthly report: `MONTHLY_REPORT_DAY` and `MONTHLY_REPORT_TIME`

Placeholder jobs write logs and do not invent business data.
