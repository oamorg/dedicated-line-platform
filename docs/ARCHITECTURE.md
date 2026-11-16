# 系统架构与功能边界

本说明对应当前社区源码，不包含任何部署现场地址、业务数量、账号、配置或证书。

## 请求链路

```text
浏览器 HTML / CSS / JavaScript
       | HTTPS
Nginx: TLS / 登录入口限流 / 覆盖代理头
       | 回环 TCP，仅信任指定代理来源
Uvicorn 多 worker -> FastAPI
       | SQLAlchemy / PyMySQL
MySQL: 业务台账 / 用户权限 / 会话 / 登录预算 / 审计

CLI 或管理员导入 -> 单机共享文件锁 -> Excel 模板验证 -> 批次 / 台账 / 错误
定时备份 -> mysqldump -> SQL 与配置归档校验 -> manifest / latest / 本地告警
恢复演练 -> 独立无网络 MySQL 实例 -> 行数、数据与表结构比较
```

## 代码入口

| 路径 | 职责 |
| --- | --- |
| app/main.py | 路由、查询、详情、统计、导出、后台管理与审计事务 |
| app/auth.py | PBKDF2 密码、随机会话令牌、权限检查和认证版本 |
| app/security.py | 共享账号/IP 登录预算、配置规则、来源地址规范化 |
| app/import_lock.py | 单机跨进程导入锁和子进程锁继承 |
| scripts/import_excel.py | 工作表及表头识别、规范化、哈希去重、批量写入 |
| scripts/init_db.py、sql/ | 幂等初始化与升级迁移，不创建默认用户 |
| scripts/manage_users.py | 交互式账号维护、会话撤销和过期预算清理 |
| scripts/backup.py、scripts/restore_verify.py | 不自动删旧备份的备份校验和隔离恢复验证 |
| web/ | 原生前端，无 Node 构建依赖，运行时同源 API |
| tests/、.github/workflows/ci.yml | 合成数据回归、MySQL 矩阵、依赖及发布审查 |

## 数据模型

| 分类 | 表 |
| --- | --- |
| 台账 | customer_line_records、onu_inventory |
| 导入 | import_batches、import_errors |
| 账号权限 | auth_users、auth_roles、auth_permissions、auth_user_roles、auth_role_permissions |
| 会话安全 | auth_sessions、auth_login_limits、auth_login_rules、auth_ip_blocks |
| 后台审计 | admin_operation_logs |

共 14 张表；空库只初始化角色、权限及其关联，不含账号、会话或业务记录。业务规范化列用于筛选，`raw_data` 保存原始字段，用于完整详情。字段说明与导入约定见 [数据说明](DATA.md)。

## 权限与登录

- `viewer` 对应 `data.query`，`exporter` 再增加 `data.export`，`admin` 再增加 `user.manage`。
- 密码存储 PBKDF2 摘要，数据库只存会话令牌摘要；前端使用 localStorage 保存实际令牌，必须防范 XSS、共用设备和浏览器插件风险。
- 服务端每次验证会话、账号启停、过期时间及认证版本。改密/全量下线提升版本，阻断旧认证结果签发有效会话。
- 登录限流使用 MySQL 共享状态，不依赖单个 worker 内存。IP 封禁只阻止新登录，不等同于撤销已有会话或整站防火墙。
- 管理变更与审计在同一事务提交；审计失败时回滚对应业务修改。
- 前端初始隐藏业务区域，退出/失效时清理已加载数据，并拒绝旧请求回填；显示层保护不能替代 API 鉴权。
- 查询权限目前覆盖全库及完整原始数据，包括 ONU 密码。没有按区域/客户隔离或敏感字段脱敏，没有 MFA/SSO、MAC 可信认证。

## 导入与并发

API 多 worker 与 CLI 必须使用同一个绝对本地锁路径。导入先检查文件、工作表和必需表头；多个候选或重复列名不继续猜测。dry-run 不写台账，但仍记录批次/错误并占用导入锁。

去重按内容哈希，不按产品号码执行更新。同一业务字段发生变化可能成为新记录；没有自动删除旧业务或通用主键 upsert。异常终止留下的 RUNNING 批次在下一次取得独占锁后恢复为失败状态。

支持单机多 worker，不支持多机同时导入同一数据库、NFS 锁或跨主机任务队列。性能需要以目标服务器、实际数据量和查询条件测量，CI 不代表并发容量承诺。

## 部署及数据流出

仅公开 HTTPS；应用、数据库、备份和 Excel 不直接对公网开放。维护用户负责安装与 DDL，Web 运行账号使用最小权限，源码尽量只读，日志/导入目录单独可写。证书与数据库密码属于部署方私有资料。

社区构建仅采集允许的文本源码、测试、模板和文档。备份归档含完整数据库、密码摘要及配置凭据，绝不是可公开的 Release 附件。运维与迁移边界见 [运维指南](OPERATIONS.md) 和 [公网验收清单](PUBLIC_READINESS.md)。
