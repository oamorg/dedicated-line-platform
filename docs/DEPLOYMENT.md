# 社区版部署指南

## 环境

目标环境为 Python 3.11–3.14、MySQL 8.0 或 8.4，验证状态见 [测试说明](TESTING.md)。示例生产环境为 Ubuntu 24.04，起步资源 2 核 / 4GB，磁盘按数据及备份量规划。macOS 可运行 Python 服务，但以下 systemd 部分仅适用于 Linux。开发测试另需 Node.js 24，运行服务不需要。

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip mysql-server nginx
id dedicated-line >/dev/null 2>&1 || sudo useradd --system --user-group --home /opt/dedicated-line --shell /usr/sbin/nologin dedicated-line
# 以下为首次空环境部署，让当前维护用户先拥有源码安装目录。
sudo install -d -o "$(id -un)" -g "$(id -gn)" /opt/dedicated-line
tar -xzf /path/to/dedicated-line-community-source-20261115-r2.tar.gz --strip-components=1 -C /opt/dedicated-line
```

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
ExecStart=/opt/dedicated-line/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
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

以下示例仅用于内网 HTTP 验证。公网发布前应为实际域名配置可信 TLS 证书并使用 HTTPS；不要通过明文 HTTP 发送账号密码或业务数据。证书与私钥不得放入 Git 仓库。

使用 `sudoedit /etc/nginx/conf.d/dedicated-line.conf` 写入以下配置（文件由 Nginx 的 `http` 范围加载）。把 `example.com` 替换为自己的域名；按 IP 访问时也要将服务器 IP 加入 `server_name`，避免命中 Ubuntu 默认站点。

```nginx
limit_req_zone $binary_remote_addr zone=dl_login:10m rate=5r/m;
server {
    listen 80;
    server_name example.com;
    client_max_body_size 1m;
    location = /api/auth/login {
        limit_req zone=dl_login burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

应用尚无内置登录限流，上面给出了代理层限制；应用端口应只监听回环地址。若再接负载均衡器，需要单独配置可信代理 IP，避免客户端伪造来源。

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo journalctl -u dedicated-line -n 100 --no-pager
```

## 运维

- 转移目录所有权后，使用 `cd /opt/dedicated-line`，再运行 `sudo -u dedicated-line .venv/bin/python scripts/manage_users.py reset-password --username admin` 隐藏输入改密，同时撤销该用户旧会话；导入命令也以该系统用户运行。
- Excel 仅放入 `IMPORT_DATA_DIR`，不要放进 `web/`；先演练再导入。
- 当前导入任务运行于子进程；避免并行触发，异常中断后应核查批次及进程再重试。
- 备份、恢复演练、HTTPS 续期和日志保留需要由部署环境安排，社区包没有配置自动任务。
- 查询、详情可返回账号获准查看的 ONU 密码及原始数据；按实际工作范围分配用户。
