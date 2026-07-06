# FoxBrain Cloud Edition 云端部署说明

这份说明给非技术老板也能看懂：FoxBrain 部署到腾讯云后，系统运行在云服务器上，不依赖你的个人电脑。

## 1. 什么是云端运行

```text
用户手机/电脑
  -> https://huyan.vafox.com
  -> Nginx / HTTPS
  -> FoxBrain Web
  -> FoxBrain API
  -> PostgreSQL / Redis / MinIO / Qdrant
  -> AI Agent / Knowledge Engine / SAP Sync / n8n / Dify / Wiki.js
```

你的电脑关机后，腾讯云服务器仍然 24 小时运行。

## 2. Codex、GitHub、腾讯云的关系

```text
老板提出需求
  -> Codex 开发
  -> 提交 GitHub
  -> GitHub Actions 自动通知服务器
  -> 腾讯云服务器自动 pull
  -> Docker 自动重建
  -> FoxBrain 自动升级
```

## 3. 首次部署

在全新 Ubuntu 服务器执行：

```bash
curl -fsSL https://raw.githubusercontent.com/huyanyong2026/foxbrain-v4/main/install.sh -o install.sh
chmod +x install.sh
sudo APP_DIR=/opt/foxbrain REPO_URL=https://github.com/huyanyong2026/foxbrain-v4.git ./install.sh
```

编辑服务器环境变量：

```bash
sudo nano /opt/foxbrain/.env
```

真实密码只放服务器 `.env`，不要放 GitHub。

## 4. 日常升级

```bash
cd /opt/foxbrain
bash deploy.sh
```

配置 GitHub Actions 后，推送 `main` 分支会自动部署。

## 5. 查看系统是否正常

```bash
cd /opt/foxbrain
docker compose ps
bash healthcheck.sh
```

## 6. 重启系统

```bash
cd /opt/foxbrain
docker compose restart
```

## 7. 备份

```bash
cd /opt/foxbrain
bash backup.sh
```

自动备份时间：每天 02:30。

## 8. 恢复

```bash
cd /opt/foxbrain
bash restore.sh /opt/foxbrain/backups/备份目录名
```

## 9. Nginx 与域名

配置文件：

```text
infra/nginx/huyan.vafox.com.conf
```

安装脚本会复制到：

```text
/etc/nginx/sites-available/foxbrain
```

默认由 Docker Compose 里的 `nginx` 服务发布 80/443 端口。宿主机 Nginx 会保留配置文件，但默认停止，避免端口冲突。

如果要启用 HTTPS：

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d huyan.vafox.com
```

## 10. 手机如何访问

手机浏览器打开：

```text
https://huyan.vafox.com
```

## 11. 员工如何使用

员工注册账号后，需要管理员审核通过，才能登录使用。

## 12. 未来接入 SAP / Dify / n8n / Wiki.js

- SAP：通过 `.env` 配置 `SAP_HOST`、`SAP_USER`、`SAP_PASSWORD`
- n8n：Docker Compose 已预留 optional profile
- Dify：先预留占位，后续按官方部署拆分服务
- Wiki.js：Docker Compose 已预留 optional profile

优先保证 FoxBrain 云端稳定运行，再逐步接入这些系统。

## 13. 常见故障

查看日志：

```bash
cd /opt/foxbrain
docker compose logs -f
```

重新部署：

```bash
cd /opt/foxbrain
bash deploy.sh
```

检查健康：

```bash
cd /opt/foxbrain
bash healthcheck.sh
```
