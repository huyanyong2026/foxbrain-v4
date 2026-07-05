#!/usr/bin/env bash
set -euo pipefail

APP_NAME="FoxBrain Cloud Edition"
APP_DIR="${APP_DIR:-/opt/foxbrain}"
REPO_URL="${REPO_URL:-https://github.com/huyanyong2026/foxbrain-v4.git}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_docker() {
  if need_cmd docker && docker compose version >/dev/null 2>&1; then
    return
  fi
  sudo apt-get update
  sudo apt-get upgrade -y
  sudo apt-get install -y ca-certificates curl git ufw nginx
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable docker
  sudo systemctl start docker
}

prepare_app() {
  sudo mkdir -p "$APP_DIR"
  if [ -d "$APP_DIR/.git" ]; then
    sudo git -C "$APP_DIR" pull --ff-only
  else
    sudo git clone "$REPO_URL" "$APP_DIR"
  fi
  sudo mkdir -p "$APP_DIR/logs" "$APP_DIR/backups" "$APP_DIR/data/certbot/www" "$APP_DIR/data/certbot/conf"
  if [ ! -f "$APP_DIR/.env" ]; then
    sudo cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo "Created $APP_DIR/.env. Please edit it before production use."
  fi
}

deploy_app() {
  cd "$APP_DIR"
  sudo docker compose up -d --build
  sudo docker compose ps
}

install_nginx_config() {
  if [ -f "$APP_DIR/infra/nginx/huyan.vafox.com.conf" ]; then
    sudo cp "$APP_DIR/infra/nginx/huyan.vafox.com.conf" /etc/nginx/sites-available/foxbrain
    sudo systemctl disable --now nginx || true
    echo "Host nginx is installed but stopped. Docker nginx publishes ports 80/443."
  fi
}

install_cron() {
  CRON_FILE="/etc/cron.d/foxbrain-sap-sync"
  CRON_CMD="0 22 * * * root cd $APP_DIR && docker compose exec -T foxbrain-worker python sync_sap_b1.py --trigger scheduled_22_00 >> $APP_DIR/logs/sap_sync.log 2>&1"
  echo "$CRON_CMD" | sudo tee "$CRON_FILE" >/dev/null
  sudo chmod 0644 "$CRON_FILE"
  echo "0 3 * * * root $APP_DIR/backup.sh >> $APP_DIR/logs/backup.log 2>&1" | sudo tee /etc/cron.d/foxbrain-backup >/dev/null
  sudo chmod 0644 /etc/cron.d/foxbrain-backup
}

install_docker
prepare_app
deploy_app
install_nginx_config
install_cron

echo ""
echo "$APP_NAME Cloud Edition is running."
echo "Local health: curl http://127.0.0.1/api/health"
echo "Edit environment: sudo nano $APP_DIR/.env"
echo "View logs: cd $APP_DIR && sudo docker compose logs -f"
echo "Open: https://huyan.vafox.com after DNS and HTTPS are configured."
