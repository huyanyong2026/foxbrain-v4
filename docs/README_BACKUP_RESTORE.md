# FoxBrain 备份与恢复说明

## 自动备份

安装脚本会创建每日 02:30 备份：

```cron
30 2 * * * /opt/foxbrain/backup.sh
```

备份目录：

```text
/opt/foxbrain/backups/YYYY-MM-DD_HH-mm-ss/
```

默认保留最近 14 天。

## 手动备份

```bash
cd /opt/foxbrain
bash backup.sh
```

## 恢复

```bash
cd /opt/foxbrain
bash restore.sh /opt/foxbrain/backups/YYYY-MM-DD_HH-mm-ss
```

恢复前建议先确认备份目录存在，并保留当前服务器快照。
