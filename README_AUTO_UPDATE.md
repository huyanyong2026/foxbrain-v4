# FoxBrain Auto Update

FoxBrain uses GitHub Actions plus `deploy.sh` for cloud updates.

Supported commands on the Ubuntu server:

```bash
bash deploy.sh
bash deploy.sh --pull
bash deploy.sh --build
bash deploy.sh --rollback
```

Secrets must stay in `.env` on the server or in GitHub Actions secrets.

