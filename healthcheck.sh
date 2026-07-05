#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/foxbrain}"
cd "$APP_DIR"

fail() {
  echo "ERROR: $*"
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed. Run bash install.sh."
docker info >/dev/null 2>&1 || fail "Docker is not running. Try: sudo systemctl restart docker"

docker compose ps || fail "docker compose ps failed."

curl -fsS http://127.0.0.1/api/health >/dev/null || curl -fsS http://127.0.0.1:3000/api/health >/dev/null || fail "FoxBrain health API is not reachable. Check: docker compose logs foxbrain-web"

docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-foxbrain}" -d "${POSTGRES_DB:-foxbrain}" >/dev/null || fail "PostgreSQL is not ready."
docker compose exec -T redis redis-cli ping >/dev/null || fail "Redis is not ready."
curl -fsS http://127.0.0.1/minio/health/live >/dev/null || echo "WARN: MinIO public health path is not exposed through nginx. Check docker compose ps minio."

docker compose ps foxbrain-worker | grep -E "running|Up" >/dev/null || fail "FoxBrain worker is not running."
if [ -f "$APP_DIR/logs/worker.log" ]; then
  echo "Recent worker logs:"
  tail -n 20 "$APP_DIR/logs/worker.log"
else
  echo "WARN: worker.log not found yet. It should appear after the worker starts."
fi

DISK_USE="$(df / | awk 'NR==2 {print $5}' | tr -d '%')"
if [ "$DISK_USE" -ge 85 ]; then
  fail "Disk usage is ${DISK_USE}%. Clean logs or expand disk."
fi

FREE_MEM_MB="$(free -m | awk '/Mem:/ {print $7}')"
if [ "$FREE_MEM_MB" -lt 300 ]; then
  fail "Available memory is below 300MB. Consider increasing server memory."
fi

echo "FoxBrain healthcheck OK."
