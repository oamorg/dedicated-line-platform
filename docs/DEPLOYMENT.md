# 社区版部署指南

**版本提示:** 本指南对应 v0.1.1，包含 v0.1.0 之后的安全修复、登录安全页和备份验证工具。旧 v0.1.0 附件不包含这些更新。发布包和 CI 通过不等同于目标服务器已验收。

## 源码修订与发布附件

推荐直接使用下面的 v0.1.1 发布附件；需要 Git 源码时，在维护电脑检出同一标签并记录提交号：

```bash
git clone --branch v0.1.1 https://github.com/oamorg/dedicated-line-platform.git
cd dedicated-line-platform
git log -1 --format='%H %s'
python3 scripts/check_release.py --tracked
```

若从仓库页面下载源码压缩包，应核对对应提交；`sql/01_schema.sql` 是空库结构与权限种子。不要混用旧附件的 SQL 和新源码。已有数据库应执行全部迁移，不能直接导入空库覆盖。

在 [v0.1.1 发布页](https://github.com/oamorg/dedicated-line-platform/releases/tag/v0.1.1) 下载 `dedicated-line-community-release-0.1.1.tar.gz` 和 `SHA256SUMS.txt`，放到同一目录。GitHub 自动生成的 Source code 下载项仅含源码，不包含额外的空库 SQL 和整包文档目录；首次部署建议使用社区整包附件。独立的 `DEPLOYMENT.md` 和 `OPERATIONS.md` 分别为部署和运维指南。

```bash
# 只下载整包时，选择清单中的对应条目校验。
grep '  dedicated-line-community-release-0.1.1.tar.gz$' SHA256SUMS.txt | sha256sum -c -
mkdir dedicated-line-release-0.1.1
tar -xzf dedicated-line-community-release-0.1.1.tar.gz -C dedicated-line-release-0.1.1
cd dedicated-line-release-0.1.1
sha256sum -c SHA256SUMS.txt
```

macOS 将 `sha256sum` 替换为 `shasum -a 256`。若下载了全部独立附件，可在解压前直接校验整份外部清单。解压后目录包含源码包、`db/dedicated_line_empty.sql`、`docs/`、LICENSE 和包内校验清单。下面 `/path/to/` 请替换为附件或解压文件的实际目录。

## 环境

目标环境为 Python 3.11–3.14、MySQL 8.0 或 8.4，验证状态见 [测试说明](TESTING.md)。示例生产环境为 Ubuntu 24.04，起步资源 2 核 / 4GB，磁盘按数据及备份量规划。macOS 可运行 Python 服务，但以下 systemd 部分仅适用于 Linux。开发测试另需 Node.js 24，运行服务不需要。

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip mysql-server mysql-client nginx git
id dedicated-line >/dev/null 2>&1 || sudo useradd --system --user-group --home /opt/dedicated-line --shell /usr/sbin/nologin dedicated-line
# 以下为首次空环境部署，让当前维护用户先拥有源码安装目录。
sudo install -d -o "$(id -un)" -g "$(id -gn)" /opt/dedicated-line
# 替换为已校验整包内的源码附件路径；仅用于首次空目录安装。
tar -xzf /path/to/dedicated-line-community-source-0.1.1.tar.gz --strip-components=1 -C /opt/dedicated-line
```

若选择 Git 标签源码而非附件，用 `git -C /path/to/checked-source archive v0.1.1 | tar -x -C /opt/dedicated-line` 替代最后一行，并在 Bash 中先设置 `set -o pipefail`。两种方式二选一，不能覆盖已有业务安装目录。

## 数据库与配置

先运行 `sudo mysql` 进入本机管理员会话（已有 MySQL 认证配置时用自己的管理员登录方式），替换以下示例密码后执行，最后输入 `exit` 退出。此账号用于初始化和迁移，运行账号可另行限制为业务库的 SELECT/INSERT/UPDATE/DELETE；后台初始化结构 API 因而需要由维护人员通过 CLI 代替。

```sql
CREATE DATABASE dedicated_line CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'dedicated_line'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_UNIQUE_DB_PASSWORD';
GRANT ALL PRIVILEGES ON dedicated_line.* TO 'dedicated_line'@'127.0.0.1';
```

```bash
cd /opt/dedicated-line
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

编辑 `.env`，将 `CHANGE_ME` 替换成数据库密码；密码中的 `@ / : # %` 等字符应做 URL 编码。生产 `IMPORT_DATA_DIR` 建议写成 `/opt/dedicated-line/data/excel`。`.env` 按 dotenv 数据解析，不应包含 shell 命令。`API_HOST` / `API_PORT` 不会自动改变 Uvicorn 的监听地址，以启动命令中的 `--host` / `--port` 为准。

```bash
.venv/bin/python scripts/init_db.py
.venv/bin/python scripts/manage_users.py create-user --username admin --display-name Administrator --role admin
mkdir -p data/excel logs/imports
sudo chown -R dedicated-line:dedicated-line /opt/dedicated-line
```

没有默认管理员。密码通过隐藏输入设置，至少 12 位。也可将发布包的 `db/dedicated_line_empty.sql` 导入你新建的空数据库，再创建管理员；空库文件只有结构、角色和权限，无账户或业务记录。

```bash
mysql -h127.0.0.1 -udedicated_line -p dedicated_line < /path/to/dedicated_line_empty.sql
```

已有库升级前先备份。初始化脚本可重复运行，但 MySQL DDL 不保证事务整体回滚；失败时应先查看实际结构再重试。不要将旧内部备份用于社区演示。

## systemd

使用 `sudoedit /etc/systemd/system/dedicated-line.service` 写入以下配置：

```ini
[Unit]
Description=Dedicated Line Data Center
After=network.target mysql.service

[Service]
Type=simple
User=dedicated-line
Group=dedicated-line
WorkingDirectory=/opt/dedicated-line
ExecStart=/opt/dedicated-line/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.2
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

应用自行读取项目 `.env`，避免 systemd 与 dotenv 的转义规则不同。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dedicated-line
sudo systemctl status dedicated-line --no-pager
curl --fail http://127.0.0.1:8000/health
```

## Nginx 与 HTTPS

以下示例仅监听回环，供 SSH 隧道验证。公网发布前应为实际域名配置可信 TLS 证书并使用 HTTPS；不要通过明文 HTTP 发送账号密码或业务数据。证书与私钥不得放入 Git 仓库。

使用 `sudoedit /etc/nginx/conf.d/dedicated-line.conf` 写入以下配置（文件由 Nginx 的 `http` 范围加载）。把 `example.com` 替换为自己的域名；按 IP 访问时也要将服务器 IP 加入 `server_name`，避免命中 Ubuntu 默认站点。

```nginx
limit_req_zone $binary_remote_addr zone=dl_login:10m rate=5r/m;
server {
    listen 127.0.0.1:18000;
    server_name example.com;
    client_max_body_size 1m;
    proxy_bind 127.0.0.2;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Forwarded "";
    proxy_set_header CF-Connecting-IP "";
    location = /api/auth/login {
        limit_req zone=dl_login burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

转发头统一在 server 层设置，location 不重复覆盖。Nginx 使用专用回环源地址 `127.0.0.2`，Uvicorn 只信任该地址，不能使用 `*`。这是 Linux 单机示例，不防御已有本机执行权限的攻击者。多级代理/CDN 需另行配置可信链。配置语义见 [Nginx 官方说明](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)。

维护电脑可运行 `ssh -N -L 127.0.0.1:18000:127.0.0.1:18000 deployuser@example.com`，再访问本机 `http://127.0.0.1:18000/`。公网真实 IP 验收需要另外配置 HTTPS，并由真实外部网络访问。

应用使用数据库共享登录预算，默认每账号每 15 分钟最多 10 次尝试，每来源 IP 每 15 分钟最多 60 次尝试，管理员可在“登录安全”调整。成功和失败都计数，到期自动恢复。超限返回 429 和 Retry-After；重启 worker 不清零。Nginx 限流仍应保留，应用端口只监听回环。来源 IP 使用 Uvicorn 校验可信代理后的 request.client，不直接相信客户端 X-Forwarded-For。若再接负载均衡器，需要配置并实测可信代理链。

### 登录界面与访问限制

- 未登录时只显示独立登录页。业务框架和详情容器在 HTML 中默认 `hidden`、`inert`，会话恢复校验期间也不显示；认证成功后才开放。退出、401 和跨标签页失效立即隐藏并清空业务数据。JavaScript 未加载时保持关闭。这是显示与交互隔离，后端接口鉴权仍是数据安全边界。
- 默认阈值定义在 `app/security.py`，管理员设置存于 `auth_login_rules`；空表使用默认值。规则更新使用版本号防止并发覆盖，下一次登录读取新阈值，不重置已有计数或窗口到期时间。时长 60–3600 秒、账号上限 3–100、IP 上限 10–1000，IP 上限不得小于账号上限。
- 计数存于 `auth_login_limits`，跨 worker 共用。窗口从该维度首次计数开始；默认每账号第 11 次或同 IP 第 61 次尝试被拒绝，剩余等待时间由 `Retry-After` 返回。成功登录不清零；暂时限流不等于注销现有会话或禁止访问整个网站。
- “登录安全”仅允许 `user.manage` 管理员访问，支持拒绝记录的 IP/账号/事件/时间过滤与分页、临时封禁和解封单个 IPv4/IPv6。封禁最长 7 天，到期自动失效，只限制新登录，不追溯已经开始的登录请求或现有会话。没有永久黑名单、网段封禁或 MAC 封锁。
- 不允许封禁回环、未指定、组播、链路本地或当前操作来源 IP，避免误锁管理员。IPv6 统一压缩，IPv4-mapped IPv6 按 IPv4 处理。解封采用记录修订号，拒绝旧页面解除后来重设的封禁；解封同时清除该 IP 预算，但保留账号限流。
- 封禁存于 `auth_ip_blocks`。规则、封禁、解封与操作审计同事务提交，审计写入失败则回滚。“数据管理 → 后台操作日志”可查看 `security.rules_updated`、`security.ip_blocked`、`security.ip_released` 及登录事件；“用户管理”仍可禁用账号或强制下线。
- NAT 后共用出口的用户共用 IP 预算。仅经 SSH 隧道且不接可信反向代理的测试服务会把来源识别为回环 IP，不能据此声称公网真实来源识别已验收。不要信任浏览器自行提交的来源 IP 请求头。
- 普通公网 Web 应用不能依靠终端 MAC 做访问控制。若需限制设备，应在受管理的网络/VPN、设备证书或身份接入层设计，不应将前端上报的设备标识当作可信身份。

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo journalctl -u dedicated-line -n 100 --no-pager
```

## 运维

- 转移目录所有权后，使用 `cd /opt/dedicated-line`，再运行 `sudo -u dedicated-line .venv/bin/python scripts/manage_users.py reset-password --username admin` 隐藏输入改密，同时撤销该用户旧会话；导入命令也以该系统用户运行。
- Excel 仅放入 `IMPORT_DATA_DIR`，不要放进 `web/`；先演练再导入。
- 导入仅支持单机部署，API 多 worker 和 CLI 通过同一个本地文件锁互斥，dry-run 也占锁。设置所有入口的 `IMPORT_LOCK_FILE=/opt/dedicated-line/logs/imports/.import.lock`；锁文件不可删除或在运行期间更换。不要使用 NFS、不同锁路径或多主机共同写入同一业务库。子进程继承锁，父进程提交启动审计后才放行；进程退出自动释放，下一次独占导入将遗留 RUNNING 批次标为 FAILED。多主机任务队列不在当前支持范围。
- 升级该管理页前先备份，执行 `.venv/bin/python scripts/init_db.py sql/06_login_security_admin.sql`，再启动新代码；升级旧版 v0.1.0 还需依次应用先前迁移。06 只新增两张表，不插入默认账号、封禁或配置；重复运行不覆盖已有规则。运行数据库账号需具备两表的 SELECT/INSERT/UPDATE/DELETE，DDL 仅给维护账号。回退旧代码可保留两张新增表，不要删除业务表。
- 每日以服务账号执行 `.venv/bin/python scripts/manage_users.py prune-login-limits`，清理超过一天的过期登录预算和封禁条目；自动到期不依赖清理任务。认证及管理日志保留/归档按内部策略安排，不记录密码或 token。
- 备份与恢复验证脚本已包含，但不会自动安装定时任务；按 [运维与备份恢复](OPERATIONS.md) 配置本地告警、每日备份和每小时巡检。证书续期、日志保留、外部通知仍需部署者安排。
- 查询、详情可返回账号获准查看的 ONU 密码及原始数据；按实际工作范围分配用户。

## 从 v0.1.0 升级

仅在已备份并完成恢复演练的维护窗口操作目标环境。本次修复不会自动执行以下命令。停掉旧 Web 服务和所有旧 CLI 导入进程，再更新源码，确保新旧导入器不会同时运行。

```bash
sudo systemctl stop dedicated-line
cd /opt/dedicated-line
# 使用维护账号的 DATABASE_URL，执行全部幂等迁移；不要把维护凭据给 Web 进程。
.venv/bin/python scripts/init_db.py
# 迁移完成后换回最小权限运行凭据，再启动新服务。
sudo systemctl start dedicated-line
curl --fail http://127.0.0.1:8000/health
```

`sql/05_upgrade_security.sql` 添加用户/会话版本及登录预算表，可重复运行。业务修改和审计记录现在同事务提交；改密和全量下线会提升会话版本，防止旧验证请求签发有效会话。保留当前会话的全量下线会同步更新该会话版本。

迁移本身不删除账号和业务记录，也不自动清空既有会话。公网切换前建议管理员全量下线其他用户，并核对新版本退出行为。回滚不要直接删除新列，应先停止服务、使用经过验证的备份恢复方案；旧程序不执行新版会话和限流保护。

更多公网门槛及测试边界见 [公网验收清单](PUBLIC_READINESS.md)。
