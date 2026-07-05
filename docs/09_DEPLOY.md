# 09 Deploy / 生产部署规范

## 目标

保证 `https://huyan.vafox.com` 上的 FoxBrain 可以稳定、安全、可回滚地升级。

## 环境变量

真实配置必须放在服务器 `.env` 或 `portal.env`，不要提交到 GitHub。

建议变量：

- `APP_ENV=production`
- `PORTAL_ADMIN_EMAIL`
- `PORTAL_INITIAL_ADMIN_PASSWORD`
- `AI_MODEL_NAME`
- `DIFY_BASE_URL`
- `N8N_BASE_URL`
- `WIKI_BASE_URL`
- `SAP_SYNC_ENABLED`

## 反向代理

生产建议使用 Nginx 或 Caddy：

- 强制 HTTPS
- 反向代理到本地应用端口
- 保留真实 IP 头
- 配置请求体大小，支持文件上传

## 健康检查

- 页面：`/system/health`
- API：`/api/health`

健康检查返回应用版本、数据库状态、SAP 同步状态、文档引擎、知识引擎和研究引擎状态，不暴露密码或数据库连接。

## 数据库升级

当前项目使用启动时自动创建表和补字段的方式迁移 SQLite。上线前应备份：

- `portal.db`
- `uploads/`
- `portal.env`
- `secret.key`

## 回滚计划

1. 停止服务
2. 切回上一版本代码
3. 恢复数据库备份
4. 重启服务
5. 检查 `/api/health`

## 禁止事项

- 不把密码提交到 GitHub
- 不在 README 或 docs 中写真实服务器密码
- 不删除生产数据库
- 不覆盖上传文件目录
## Task021 SAP Nightly Sync

Production should schedule SAP B1 sync every day at 22:00 server local time.

Use `.env` for all credentials and schedule settings. Recommended production scheduler is cron or systemd timer. See `docs/52_SAP_NIGHTLY_SYNC.md`.
