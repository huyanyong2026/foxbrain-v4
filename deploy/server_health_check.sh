#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/foxbrain}"
PORTAL_SERVICE="${PORTAL_SERVICE:-firefox-portal.service}"
PORTAL_URL="${PORTAL_URL:-https://huyan.vafox.com}"

section() {
  printf '\n===== %s =====\n' "$1"
}

warn() {
  printf 'WARN: %s\n' "$1"
}

section "System"
date
uname -a
lsb_release -a 2>/dev/null || cat /etc/os-release
timedatectl status 2>/dev/null || true

section "CPU / Memory / Disk"
printf 'CPU cores: '
nproc
free -h
df -h
lsblk

section "Network Ports"
ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true

section "Firewall"
sudo ufw status verbose 2>/dev/null || warn "ufw is not available or needs sudo."

section "Fail2ban"
sudo fail2ban-client status 2>/dev/null || warn "fail2ban is not available or not running."

section "Docker"
if command -v docker >/dev/null 2>&1; then
  docker --version
  docker compose version 2>/dev/null || true
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' || true
else
  warn "Docker is not installed."
fi

section "Host Services"
systemctl is-active nginx 2>/dev/null || true
systemctl is-active "$PORTAL_SERVICE" 2>/dev/null || true
systemctl status "$PORTAL_SERVICE" --no-pager -l 2>/dev/null | tail -n 20 || true

section "FoxBrain App"
if [ -d "$APP_DIR" ]; then
  cd "$APP_DIR"
  if [ -f docker-compose.yml ] && command -v docker >/dev/null 2>&1; then
    docker compose ps || true
  fi
  [ -f .env ] && echo ".env exists with restricted secrets expected." || warn ".env is missing."
  [ -f healthcheck.sh ] && bash healthcheck.sh || true
else
  warn "$APP_DIR does not exist."
fi

section "SAP Schedule"
if [ -f /etc/cron.d/foxbrain-sap-sync ]; then
  cat /etc/cron.d/foxbrain-sap-sync
else
  crontab -l 2>/dev/null | grep -i sap || warn "SAP cron not found."
fi

section "Backup Schedule"
if [ -f /etc/cron.d/foxbrain-backup ]; then
  cat /etc/cron.d/foxbrain-backup
else
  crontab -l 2>/dev/null | grep -i backup || warn "Backup cron not found."
fi

section "HTTPS"
curl -I -L "$PORTAL_URL" --max-time 15 || warn "Portal HTTPS check failed."

section "Summary"
echo "Server health check finished."
