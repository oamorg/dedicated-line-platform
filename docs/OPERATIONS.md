# 运维、备份与迁移指南

适用于按 [部署指南](DEPLOYMENT.md) 安装的 Linux 单机服务。本文件只有通用路径和虚构占位符，不包含现场备份、账号或凭据。所有变更先在隔离环境验证；不将本指南当作对任意现有服务器执行删除或恢复的授权。

## 巡检

```bash
sudo systemctl is-active dedicated-line mysql nginx
curl --fail http://127.0.0.1:8000/health
sudo nginx -t
df -h /
df -i /
sudo systemctl list-timers dedicated-line-backup.timer dedicated-line-backup-check.timer --no-pager
sudo journalctl -u dedicated-line -u dedicated-line-backup -u dedicated-line-backup-check -n 100 --no-pager
```

健康接口会访问数据库，但 200 不能替代登录、角色拒绝、业务筛选、导出和浏览器验收。日志可能含业务标识/IP，故障工单应脱敏；不要上传 `.env`、数据库转储或会话令牌。磁盘、inode、数据库、备份失败和证书有效期均应监测。

## 备份工具与限制

`scripts/backup.py` 提供 `backup`、`verify`、`check`、`alert` 子命令。默认配置为 `/etc/dedicated-line-backup.json`，可用 `--config` 指定其他文件。脚本只接受配置匹配的本机 MySQL 数据库，不适用于未经适配的远程托管数据库。

- 使用单事务流式 mysqldump；检查子进程退出码、诊断输出、完整 gzip、结束标记、表清单、逐表行数/数据摘要和归档哈希。
- 只支持有主键的 InnoDB 基表；发现视图、例程、事件、触发器或不满足条件的表会拒绝，不静默遗漏。
- 成功后原子发布目录和 `latest`，失败不替换上次成功备份、不删历史备份；失败目录保留排障。
- 密码通过临时 600 权限客户端配置传入，不放在命令行。目录默认 700，使用共享备份锁防止重复任务。
- 本地状态记录在 `state_dir`，易失告警副本放在 `runtime_dir`，同时写 syslog。不会自动发送邮件、短信或聊天通知。
- `check` 校验磁盘余量、最新成功时间、最新文件哈希及备份定时器的启用/活动状态；它不是实际恢复测试。
- `--single-transaction` 不能保证与并发 DDL 的一致性。备份期间不要执行结构迁移，切换服务器前应冻结业务写入并制作最终快照。相关选项见 [MySQL 官方 mysqldump 文档](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html)。

配置归档按 `config_paths` 收集，可含 `.env`，因此整份备份均为私有资料。示例不包括 Excel、TLS 私钥、系统软件和虚拟环境；需要迁移时应另行安全备份、核对许可和权限。压缩不是加密，远程传输使用 SSH/SFTP 等可信加密渠道，离机介质按组织策略加密。哈希校验不能证明来源可信，不执行来路不明的 SQL，也不将归档直接覆盖到系统根目录。

## 安装备份配置

先确认目录只属于本系统，再执行。不要递归修改其他业务目录的权限。

```bash
cd /opt/dedicated-line
sudo install -o root -g root -m 0644 config/backup.example.json /etc/dedicated-line-backup.json
sudo install -d -o dedicated-line -g dedicated-line -m 0700 \
  /var/backups/dedicated-line /var/lib/dedicated-line-backup /run/dedicated-line-backup
sudoedit /etc/dedicated-line-backup.json
```

配置中的 `app_dir`、数据库名及 `config_paths` 必须与实际路径一致；列表中任何缺失或不可读文件会使备份失败，不应为通过检查而开放其他服务的私有目录。凭据从 `app_dir/.env` 读取，确保运行身份可读，且 MySQL 账号满足本备份条件下的读取权限。

`/run` 重启会清空，下面 systemd 单元使用 `RuntimeDirectory` 重建；手动运行前也要确认目录存在。第一次手动生成并完整验证：

```bash
sudo -u dedicated-line /opt/dedicated-line/.venv/bin/python /opt/dedicated-line/scripts/backup.py backup
RUN=$(readlink -f /var/backups/dedicated-line/latest)
sudo -u dedicated-line /opt/dedicated-line/.venv/bin/python /opt/dedicated-line/scripts/backup.py verify --run "$RUN"
```

检查退出码为 0，再检查私有目录中的 `manifest.json`、`status.json` 和 `last_success.json`。首个备份完成后才有成功状态可供巡检。

## 每日备份与本地告警

以下是需要自行安装的示例，不会随源码下载自动生效。使用 `sudoedit` 分别建立四个定时/服务单元和一个失败告警单元。

`/etc/systemd/system/dedicated-line-backup.service`：

```ini
[Unit]
Description=Validated dedicated-line backup
After=mysql.service
OnFailure=dedicated-line-backup-alert.service

[Service]
Type=oneshot
User=dedicated-line
Group=dedicated-line
WorkingDirectory=/opt/dedicated-line
ExecStart=/opt/dedicated-line/.venv/bin/python /opt/dedicated-line/scripts/backup.py backup
StateDirectory=dedicated-line-backup
StateDirectoryMode=0700
RuntimeDirectory=dedicated-line-backup
RuntimeDirectoryMode=0700
RuntimeDirectoryPreserve=yes
UMask=0077
NoNewPrivileges=true
Nice=10
```

`/etc/systemd/system/dedicated-line-backup.timer`：

```ini
[Unit]
Description=Daily dedicated-line backup
[Timer]
OnCalendar=*-*-* 02:30:00 Asia/Shanghai
Persistent=true
Unit=dedicated-line-backup.service
[Install]
WantedBy=timers.target
```

`/etc/systemd/system/dedicated-line-backup-check.service`：

```ini
[Unit]
Description=Check dedicated-line backup freshness
OnFailure=dedicated-line-backup-alert.service
[Service]
Type=oneshot
User=dedicated-line
Group=dedicated-line
WorkingDirectory=/opt/dedicated-line
ExecStart=/opt/dedicated-line/.venv/bin/python /opt/dedicated-line/scripts/backup.py check
StateDirectory=dedicated-line-backup
StateDirectoryMode=0700
RuntimeDirectory=dedicated-line-backup
RuntimeDirectoryMode=0700
RuntimeDirectoryPreserve=yes
UMask=0077
NoNewPrivileges=true
```

`/etc/systemd/system/dedicated-line-backup-check.timer`：

```ini
[Unit]
Description=Hourly dedicated-line backup check
[Timer]
OnCalendar=hourly
Persistent=true
Unit=dedicated-line-backup-check.service
[Install]
WantedBy=timers.target
```

`/etc/systemd/system/dedicated-line-backup-alert.service`：

```ini
[Unit]
Description=Local dedicated-line backup failure alert
[Service]
Type=oneshot
ExecStart=/usr/bin/logger -p daemon.err -t dedicated-line-backup "BACKUP ALERT: backup or watchdog job failed; inspect the service journal"
```

Python 能启动时脚本会写 JSON 告警；Python/环境损坏时，`OnFailure` 的独立 logger 仍记录本地日志。没有人巡检本地状态时不会自动通知到人，关键生产环境应另接外部监控。不要用故意破坏业务库或填满系统盘来测试告警。

```bash
sudo systemd-analyze verify /etc/systemd/system/dedicated-line-backup*.service /etc/systemd/system/dedicated-line-backup*.timer
sudo systemctl daemon-reload
sudo systemctl enable --now dedicated-line-backup.timer dedicated-line-backup-check.timer
sudo systemctl start dedicated-line-backup.service
sudo systemctl start dedicated-line-backup-check.service
sudo systemctl show dedicated-line-backup dedicated-line-backup-check -p Result -p ExecMainStatus
sudo systemctl list-timers dedicated-line-backup.timer dedicated-line-backup-check.timer --no-pager
sudo journalctl -t dedicated-line-backup -n 30 --no-pager
```

每天北京时间 02:30 备份，每小时巡检；时间设置与状态以目标机实际解析为准，可用 `systemd-analyze calendar '*-*-* 02:30:00 Asia/Shanghai'` 验证，语法见 [systemd 官方时间说明](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html)。首次成功后，可直接启动 `dedicated-line-backup-alert.service` 验证本地告警链路，注明这是演练，不能把告警演练当作备份恢复成功。

## 恢复验证

`scripts/restore_verify.py` 不是生产覆盖恢复命令，也不自动创建/启动 MySQL 沙箱。先由维护人员在隔离环境建立一次性 MySQL 实例，必须满足：

- 沙箱根目录为 `/var/lib/dedicated-line-restore-<唯一标识>`，其中包含 `data`、`run`、`logs`。
- MySQL 数据目录属于该沙箱，`auto.cnf` 的 UUID 与目标实例一致；使用独立 Unix socket `run/mysqld.sock`，实例启用 `skip_networking`，MySQL X 端口也不得公开。
- 只允许本地私有目录中的临时 root 无密码 socket 访问，目录限制访问；不是修改正式 MySQL 的认证。
- 使用受控私有 mount namespace 适配 AppArmor 时，脚本额外核对三处挂载、PID 与 UUID。不要关闭主机安全策略来绕过隔离。
- 不挂载生产数据库目录，不复用生产 socket，不抢占业务端口。给恢复进程设置 CPU/内存/磁盘上限。

确认环境后执行，两个占位路径必须替换为隔离沙箱与已验证备份：

```bash
sudo /opt/dedicated-line/.venv/bin/python /opt/dedicated-line/scripts/restore_verify.py \
  --run /var/backups/dedicated-line/REPLACE_WITH_VERIFIED_RUN \
  --sandbox /var/lib/dedicated-line-restore-REPLACE_WITH_UNIQUE_ID \
  --database dl_restore_validation
```

脚本拒绝已有同名恢复库；SQL 客户端诊断会保存在私有 `restore.stderr`。失败不删除沙箱，供排障；重试应先检查状态，不盲目删除已有数据。成功输出逐表行数和摘要比较，保存在 `restore-report.json`。只有冗余 `CHARACTER SET utf8mb4` 声明被有限规范化；列类型、排序规则、默认值、索引或数据差异仍失败，原始结构文本不同会明确记录。

随后应使用独立应用配置连接恢复库，验证登录、查询、详情和分权。停止临时应用/MySQL 后，再按明确清单删除本轮沙箱及临时账号；检查没有进程/挂载占用，不能以宽泛通配符删除 `/var/lib`。摘要一致不证明应用所有流程都正常。

## 迁移、回退与历史清理

1. 核对源/目标系统、架构、MySQL 版本、空间、域名、证书和可接受停写窗口。虚拟环境不能跨平台直接复制，应在目标机重建。
2. 分别保存源码提交号、依赖锁、完整 SQL、原始 Excel、服务/代理配置和私有凭据。社区空库用于新建空环境，不用于替代完整数据备份。
3. 校验备份、完成隔离恢复与应用验证，再准备新机；不得对旧机执行覆盖恢复。迁移新库时撤销旧会话，重新生成数据库密码，避免误连接源库。
4. 正式切换前冻结导入和管理写入，制作最终快照并对账；不能把几天前的备份当成当前完整数据。新机验收后再切换 HTTPS 入口，旧机保留可回退状态。
5. 回退前判断新机是否已有新写入，不能只切流量而丢弃数据。先保存新机变化，再按维护方案恢复。
6. 只有新备份完整、独立恢复通过、异机副本核验完成且范围获批后，才按清单删除本系统旧备份。保留至少一个已验证恢复点，不删除其他系统资料；脚本本身不自动清理历史。

建议制定明确保留期与容量预算，但本工具不会替部署者决定删除日期。系统日志压缩、数据库 binlog 保留和文件系统扩容属于独立变更，不应夹带在备份清理中。
