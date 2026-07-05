# FoxBrain Backup And Restore

Use:

```bash
bash backup.sh
bash restore.sh /opt/foxbrain/backups/BACKUP_DIR
```

Backups cover PostgreSQL, MinIO files, Qdrant data, portal data and `.env`.
Do not commit backup files to GitHub.

