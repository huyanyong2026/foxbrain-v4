# FoxBrain 环境变量说明

服务器配置文件：

```text
/opt/foxbrain/.env
```

模板文件：

```text
.env.example
```

真实密码只允许放在服务器 `.env` 中，不要提交到 GitHub。

重点配置：

- `APP_URL`
- `DOMAIN`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- `DEEPSEEK_API_KEY`
- `SAP_HOST`
- `SAP_USER`
- `SAP_PASSWORD`
- `SAP_SYNC_ENABLED`
- `SAP_SYNC_TIME`
