#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/foxbrain}"
STAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/foxbrain_pre_upgrade_$STAMP}"

sudo mkdir -p "$BACKUP_DIR"

echo "Creating FoxBrain pre-upgrade backup at $BACKUP_DIR"

copy_if_exists() {
  local src="$1"
  local name="$2"
  if [ -e "$src" ]; then
    sudo cp -a "$src" "$BACKUP_DIR/$name"
    echo "Backed up $src"
  else
    echo "Skipped missing $src"
  fi
}

copy_if_exists "$APP_DIR" "foxbrain"
copy_if_exists /opt/firefox-portal "firefox-portal"
copy_if_exists /opt/firefox-sap-sync "firefox-sap-sync"
copy_if_exists /etc/nginx "nginx"
copy_if_exists /etc/letsencrypt "letsencrypt"
copy_if_exists /etc/cron.d/foxbrain-sap-sync "cron-foxbrain-sap-sync"
copy_if_exists /etc/cron.d/foxbrain-backup "cron-foxbrain-backup"

df -h | sudo tee "$BACKUP_DIR/df-h.txt" >/dev/null
free -h | sudo tee "$BACKUP_DIR/free-h.txt" >/dev/null
lsblk | sudo tee "$BACKUP_DIR/lsblk.txt" >/dev/null || true
systemctl list-units --type=service --state=running | sudo tee "$BACKUP_DIR/running-services.txt" >/dev/null || true
sudo crontab -l | sudo tee "$BACKUP_DIR/root-crontab.txt" >/dev/null 2>&1 || true

if command -v docker >/dev/null 2>&1; then
  docker ps -a | sudo tee "$BACKUP_DIR/docker-ps-a.txt" >/dev/null 2>&1 || true
  docker images | sudo tee "$BACKUP_DIR/docker-images.txt" >/dev/null 2>&1 || true
  if [ -d "$APP_DIR" ] && [ -f "$APP_DIR/docker-compose.yml" ]; then
    (cd "$APP_DIR" && docker compose ps) | sudo tee "$BACKUP_DIR/docker-compose-ps.txt" >/dev/null 2>&1 || true
  fi
fi

sudo chmod -R go-rwx "$BACKUP_DIR" || true
echo "Pre-upgrade backup complete: $BACKUP_DIR"
