#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/foxbrain}"
LOG_FILE="/var/log/foxbrain-deploy.log"

log() {
  echo "$(date '+%F %T') $*" | sudo tee -a "$LOG_FILE"
}

cd "$APP_DIR"

log "Starting FoxBrain deployment."

if [ -x "$APP_DIR/backup.sh" ]; then
  log "Running pre-deploy backup."
  bash "$APP_DIR/backup.sh" || log "Backup failed; continuing with deployment because backup may be unavailable on first install."
fi

PREVIOUS_COMMIT="$(git rev-parse HEAD || true)"

log "Pulling latest code."
git pull --ff-only

log "Pulling Docker images."
docker compose pull || true

log "Building Docker images."
docker compose build

log "Starting services."
if ! docker compose up -d; then
  log "Deployment failed. To rollback manually: git checkout $PREVIOUS_COMMIT && docker compose up -d --build"
  exit 1
fi

docker compose ps | sudo tee -a "$LOG_FILE"

log "Pruning old Docker objects."
docker system prune -f | sudo tee -a "$LOG_FILE"

log "Deployment complete."
