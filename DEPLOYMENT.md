# Deployment

First install on Ubuntu:

```bash
curl -fsSL https://raw.githubusercontent.com/huyanyong2026/foxbrain-v4/main/install.sh -o install.sh
chmod +x install.sh
sudo APP_DIR=/opt/foxbrain REPO_URL=https://github.com/huyanyong2026/foxbrain-v4.git ./install.sh
```

Update:

```bash
cd /opt/foxbrain
bash deploy.sh
```

Other deployment modes:

```bash
bash deploy.sh --pull
bash deploy.sh --build
bash deploy.sh --rollback
```

Health check:

```bash
bash healthcheck.sh
docker compose ps
```

