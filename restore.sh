#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/foxbrain}"
BACKUP_DIR="${1:-}"

if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
  echo "Usage: bash restore.sh /opt/foxbrain/backups/YYYY-MM-DD_HH-mm-ss"
  exit 1
fi

cd "$APP_DIR"

echo "Restoring from $BACKUP_DIR"
docker compose down

if [ -f "$BACKUP_DIR/env.backup" ]; then
  cp "$BACKUP_DIR/env.backup" "$APP_DIR/.env"
fi

docker compose up -d postgres
sleep 10
if [ -f "$BACKUP_DIR/postgres.sql" ]; then
  cat "$BACKUP_DIR/postgres.sql" | docker compose exec -T postgres psql -U "${POSTGRES_USER:-foxbrain}" "${POSTGRES_DB:-foxbrain}" || echo "PostgreSQL restore failed."
fi

if [ -f "$BACKUP_DIR/minio.tar.gz" ]; then
  docker run --rm -v foxbrain_foxbrain_minio:/data -v "$BACKUP_DIR":/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/minio.tar.gz -C /data"
fi
if [ -f "$BACKUP_DIR/portal.tar.gz" ]; then
  docker run --rm -v foxbrain_foxbrain_portal:/data -v "$BACKUP_DIR":/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/portal.tar.gz -C /data"
fi
if [ -f "$BACKUP_DIR/qdrant.tar.gz" ]; then
  docker run --rm -v foxbrain_foxbrain_qdrant:/data -v "$BACKUP_DIR":/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/qdrant.tar.gz -C /data"
fi

docker compose up -d
docker compose ps
echo "Restore complete."
