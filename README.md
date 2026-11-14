# 政企集客业务数据中心

[![Community checks](https://github.com/oamorg/dedicated-line-platform/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/oamorg/dedicated-line-platform/actions/workflows/ci.yml)

面向政企专线和 ONU 资源台账的 Excel 导入、条件查询、导出及后台管理系统。

- 专线业务全量库：按来源切换字段，查询客户、产品号码、区域和开通时间。
- ONU 资源设备台账：查询业务、客户、区县、产品号码与 SN 码。
- 统计分析：集中展示 KPI 和区域规模排行。
- 数据管理：演练/正式导入、批次追踪、错误与操作日志。
- 用户管理：角色、启停、改密、删除、会话查询和强制下线。

后端为 FastAPI / SQLAlchemy / MySQL，前端使用原生 HTML、CSS 和 JavaScript。

## 社区版边界

社区版包含 MIT 授权源码、结构与权限初始化 SQL、虚构预览样例、测试和部署文档。不含业务数据库、实际账户、会话、Excel、备份或现场部署配置。

**没有默认管理员和默认密码。** 初始化后通过命令行创建自己的管理员。已有内部版本用户不会被初始化脚本删除或改密。

## 快速部署

社区版目标环境为 Python 3.11–3.14、MySQL 8.0/8.4；Linux 生产部署流程见 [部署指南](docs/DEPLOYMENT.md)。首次公开发布已通过四个 Python 版本的回归测试和两种 MySQL 版本的集成测试，实际验证范围见 [审查记录](docs/REVIEW.md)。后续版本请查看上方 CI 状态。

```bash
git clone https://github.com/oamorg/dedicated-line-platform.git
cd dedicated-line-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

先创建数据库与专用账号，配置 `.env` 的 `DATABASE_URL`。初始化后再启动：

```bash
python scripts/init_db.py
python scripts/manage_users.py create-user --username admin --display-name Administrator --role admin
# 按提示输入并确认至少 12 位密码，输入不回显。
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

网页 `http://127.0.0.1:8000/`；API 文档 `/docs`；健康检查 `/health` 会执行数据库查询。

也可在配置 `.env` 后运行 `./deploy.sh`。脚本准备环境并初始化数据库，不自动创建管理员、配置系统服务或启动监听。

## 导入和导出

在 `config/source_files.json` 设置文件名、来源类型和工作表。默认 ONU 文件为 `ONU台账.xlsx`。原始表字段、去重规则和导入限制见 [数据说明](docs/DATA.md)。

```bash
mkdir -p data/excel
python scripts/import_excel.py --data-dir ./data/excel --dry-run
python scripts/import_excel.py --data-dir ./data/excel --batch-name initial_import
```

演练不写业务台账，但会记录批次和错误，因此也需要数据库。增量导入按行内容哈希去重；同一业务内容变化会形成新记录，不会按业务主键覆盖或自动删除旧数据。网页导出为 CSV，前端当前上限为 5000 条，接口最多 20000 条。

## 权限与预览

| 角色 | 能力 |
| --- | --- |
| viewer | 查询及查看完整原始数据 |
| exporter | 查询及导出 |
| admin | 查询、导出、数据和用户管理 |

`/?preview=1` 使用纯前端虚构样例；不登录真实账号、不写库、不替代业务接口鉴权。详情保留完整 `raw_data`；ONU 密码也是可查询字段，部署者需要控制账号授权。

## 测试与构建

从仓库根目录、已激活的虚拟环境执行。测试需要 Node.js 24；服务运行本身不需要 Node。普通测试不连接 MySQL，也不使用项目 `.env`；真实数据库集成测试单独运行，见 [测试说明](docs/TESTING.md)。

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --check web/app.js
node tests/frontend.cjs
python scripts/check_release.py
python -m pip_audit
python scripts/build_release.py --version 20261115-r2
```

构建结果位于 `dist/`，包含源码包、空库 SQL、社区整包和 SHA-256 校验文件。构建只采集允许的源码文件，拒绝私钥、运行配置及交付目录。

[使用手册](docs/USER_GUIDE.md) · [测试说明](docs/TESTING.md) · [审查记录](docs/REVIEW.md) · [GitHub 发布步骤](docs/PUBLISHING.md) · [贡献说明](CONTRIBUTING.md) · [安全说明](SECURITY.md)

## License

采用 [MIT License](LICENSE)，Copyright (c) 2026 hjie。第三方依赖保留各自许可；MIT 不授权任何部署者的业务数据。
