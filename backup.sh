#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/foxbrain}"
BACKUP_ROOT="$APP_DIR/backups"
STAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

echo "Creating backup in $BACKUP_DIR"

if [ -f .env ]; then
  cp .env "$BACKUP_DIR/env.backup"
fi

docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-foxbrain}" "${POSTGRES_DB:-foxbrain}" > "$BACKUP_DIR/postgres.sql" || echo "PostgreSQL backup skipped or failed."

docker run --rm -v foxbrain_foxbrain_minio:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/minio.tar.gz -C /data . || echo "MinIO backup skipped or failed."
docker run --rm -v foxbrain_foxbrain_portal:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/portal.tar.gz -C /data . || echo "Portal data backup skipped or failed."
docker run --rm -v foxbrain_foxbrain_qdrant:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/qdrant.tar.gz -C /data . || echo "Qdrant backup skipped or failed."

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} \;

echo "Backup complete: $BACKUP_DIR"
