# GitHub Actions 自动部署说明

主部署文件位于：

```text
.github/workflows/deploy.yml
```

需要在 GitHub 仓库 Settings -> Secrets and variables -> Actions 中配置：

```text
SERVER_HOST
SERVER_USER
SERVER_SSH_KEY
SERVER_PORT
```

每次推送到 `main` 分支后，GitHub Actions 会通过 SSH 登录腾讯云服务器，并执行：

```bash
/opt/foxbrain/deploy.sh
```
