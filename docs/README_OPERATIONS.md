# FoxBrain 日常运维说明

## 查看系统状态

```bash
cd /opt/foxbrain
docker compose ps
bash healthcheck.sh
```

## 查看日志

```bash
cd /opt/foxbrain
docker compose logs -f
```

## 重启系统

```bash
cd /opt/foxbrain
docker compose restart
```

## 启动系统

```bash
cd /opt/foxbrain
docker compose up -d
```

## 手机访问

```text
https://huyan.vafox.com
```

员工账号由管理员审核后才能使用。
