#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/foxbrain}"
LOG_FILE="/var/log/foxbrain-deploy.log"
MODE="${1:-}"

log() {
  echo "$(date '+%F %T') $*" | sudo tee -a "$LOG_FILE"
}

cd "$APP_DIR"

log "Starting FoxBrain deployment."

if [ "$MODE" = "--rollback" ]; then
  PREVIOUS_COMMIT="$(git rev-parse HEAD~1)"
  log "Rolling back to $PREVIOUS_COMMIT."
  git checkout "$PREVIOUS_COMMIT"
  docker compose up -d --build
  bash "$APP_DIR/healthcheck.sh" || true
  log "Rollback command finished. Please verify business pages before continuing."
  exit 0
fi

if [ -x "$APP_DIR/backup.sh" ]; then
  log "Running pre-deploy backup."
  bash "$APP_DIR/backup.sh" || log "Backup failed; continuing with deployment because backup may be unavailable on first install."
fi

PREVIOUS_COMMIT="$(git rev-parse HEAD || true)"

if [ "$MODE" = "--pull" ] || [ -z "$MODE" ] || [ "$MODE" = "--build" ]; then
  log "Pulling latest code."
  git pull --ff-only
fi

if [ "$MODE" = "--pull" ] || [ -z "$MODE" ]; then
  log "Pulling Docker images."
  docker compose pull || true
fi

if [ "$MODE" = "--build" ] || [ -z "$MODE" ]; then
  log "Building Docker images."
  docker compose build
fi

log "Starting services."
if ! docker compose up -d; then
  log "Deployment failed. To rollback manually: git checkout $PREVIOUS_COMMIT && docker compose up -d --build"
  exit 1
fi

docker compose ps | sudo tee -a "$LOG_FILE"

if [ -x "$APP_DIR/healthcheck.sh" ]; then
  log "Running healthcheck."
  bash "$APP_DIR/healthcheck.sh" || log "Healthcheck reported warnings. Check logs before confirming the release."
fi

log "Pruning old Docker objects."
docker system prune -f | sudo tee -a "$LOG_FILE"

log "Deployment complete."
