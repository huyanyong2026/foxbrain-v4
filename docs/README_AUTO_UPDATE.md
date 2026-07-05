# FoxBrain 自动更新说明

## 自动更新流程

```text
老板提出需求 -> Codex 开发 -> 提交 GitHub -> GitHub Actions
-> 腾讯云服务器执行 /opt/foxbrain/deploy.sh
-> Docker 自动重建 -> FoxBrain 自动升级
```

## 手动更新

```bash
cd /opt/foxbrain
bash deploy.sh
```

部署日志：

```text
/var/log/foxbrain-deploy.log
```

## GitHub Secrets

```text
SERVER_HOST
SERVER_USER
SERVER_SSH_KEY
SERVER_PORT
```

不要把服务器密码写入仓库。
