# 测试说明

## 运行前提

从仓库根目录执行；Python 3.11–3.14 虚拟环境、Node.js 24。普通测试不需要 MySQL。测试使用合成数据，不需要也不应复制生产数据库。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
node --check web/app.js
node tests/frontend.cjs
node tests/frontend_security.cjs
bash -n deploy.sh
python scripts/check_release.py
```

普通 pytest 在 `tests/conftest.py` 中禁用 dotenv、强制内存 SQLite；不会使用运行环境的 `DATABASE_URL`。`mysql_smoke.py` 不被普通 pytest 自动执行。测试输出中的第三方弃用提示不等于失败；判断 pytest / Node 进程退出码与失败条目。

## 覆盖范围

| 检查 | 内容 | 是否需要 MySQL |
| --- | --- | --- |
| `test_community.py` | 鉴权、viewer 权限、SN 参数绑定、IPVPN 映射、完整原始数据、改密撤销会话、导入日志路径 | 否，部分数据库操作使用 SQLite / Mock |
| `test_release_workflow.py` | 测试数据库保护、首次部署停止于配置步骤、包内外哈希、敏感文件排除、文档相对链接 | 否 |
| `test_backup.py` | 备份失败不覆盖、流完整性、并发锁、空间/时效检查、本地告警、凭据文件及恢复实例身份保护 | 否，临时目录和 Mock，不读取生产配置 |
| `test_restore_schema.py` | 恢复数据/行数/表结构差异拒绝，仅接受冗余字符集声明且明确报告 | 否，合成 SQL |
| `frontend.cjs` | 虚构样例、CSV 内容转义、表头顺序、预览隔离 | 否，Node VM，不是浏览器视觉测试 |
| `test_security.py` | 管理事务回滚、登录预算、会话版本、导入锁与模板校验 | 否，虚构数据与 SQLite，含真实子进程锁测试 |
| `test_login_security.py` | 管理权限、配置校验与并发版本、IP 规范化/自身保护、到期解封、拒绝记录分页、审计失败回滚 | 否，复用隔离 SQLite fixture |
| `frontend_security.cjs` | 默认隐藏业务框架、待验证/失效会话、退出隐藏与清理、旧响应拒绝、账号切换、多标签页 | 否，Node VM |
| `mysql_security.py` | 旧库安全迁移、管理事务回滚、并发改密/下线、并发账号限流、遗留任务恢复 | 是，紧跟 mysql_smoke 在同一本机一次性测试库运行 |
| `mysql_login_security.py` | 规则实时生效/并发保存、IP 拦截/过期/解封、账号计数保留、审计回滚、06 迁移幂等 | 是，紧跟 mysql_security，在无账号和配置的一次性测试库运行 |
| `mysql_smoke.py` | 发布空库 SQL 恢复、重复初始化、无默认账号、Excel 演练/导入/去重、三类角色、详情、导出、退出登录 | 是，新建本机空测试库 |
| `pip-audit` | 当前安装依赖的已知漏洞查询 | 否，需要互联网 |

## MySQL 集成测试

必须使用本机新建的空库，库名以 `_test` 结尾。脚本只读取显式传入的 `MYSQL_TEST_DATABASE_URL`，不回退到部署的 `DATABASE_URL` 或 `.env`；远程地址、错误驱动、非空库均会被拒绝。脚本中的入口保护不使用可被 `python -O` 去掉的 assert。

通过 MySQL 管理员创建专用测试库和用户，替换密码：

```sql
CREATE DATABASE dedicated_line_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'community_test'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_TEST_PASSWORD';
GRANT ALL PRIVILEGES ON dedicated_line_test.* TO 'community_test'@'127.0.0.1';
```

在运行测试的终端设置连接串（特殊字符需 URL 编码）：

```bash
export MYSQL_TEST_DATABASE_URL='mysql+pymysql://community_test:REPLACE_WITH_TEST_PASSWORD@127.0.0.1:3306/dedicated_line_test?charset=utf8mb4'
python tests/mysql_smoke.py
python tests/mysql_security.py
python tests/mysql_login_security.py
unset MYSQL_TEST_DATABASE_URL
```

脚本先构建发布产物并恢复 `dedicated_line_empty.sql`，检查账号、会话、业务、批次与日志表均为空，再重复执行迁移。随后临时生成虚构 Excel，演练后验证无业务行，正式导入及再次导入后验证每类记录只有一条，并通过真实 API 检查 viewer/exporter/admin 权限。测试结束清除本轮合成记录和用户，保留表结构以便排错；下次运行应重新创建空的专用测试库。失败的表结构初始化也可能留下表，不能把失败当作已回滚。

GitHub CI 为 MySQL 8.0/8.4 各启一个临时容器，不需要配置生产 Secrets。CI 数据库密码仅适用于临时测试容器。

`mysql_security.py` 会重构安全字段的旧列形态来测试升级，拒绝含账号、业务或批次记录的测试库；绝不可用于现有业务库。当前工作副本的本地验收与远端 CI 结果应分开记录，未推送的修改不会触发 GitHub CI。公网发布门槛见 [PUBLIC_READINESS.md](PUBLIC_READINESS.md)。

## 发布前检查

```bash
python -m pip check
python -m pip_audit
python scripts/check_release.py
python scripts/build_release.py --version 0.1.0
cd dist
shasum -a 256 -c SHA256SUMS.txt
```

Linux 可用 `sha256sum -c SHA256SUMS.txt`。在独立 Git 仓库暂存后再执行 `python scripts/check_release.py --tracked`，它会核对暂存索引中是否混入非发布文件。

已完成和未完成的实际验证记录见 [REVIEW.md](REVIEW.md)。仅通过单元测试不代表真实 MySQL、Linux 服务或浏览器已通过验收。备份测试在临时目录中使用合成 SQL 和进程替身，CI 不会启动生产备份、运行恢复到现有数据库或删除旧备份。实际恢复流程见 [OPERATIONS.md](OPERATIONS.md)。

登录安全页浏览器验收应包含：管理员进入/筛选记录、修改规则与冲突提示、封禁/解封确认、空列表、IPv6 输入、窄屏内部表格滚动、viewer/exporter 无菜单且接口 403、退出后清空安全记录，慢查询或慢修改响应不能回填。离线 `?preview=1` 的登录安全模块只读，不模拟保存成功；真实修改必须在独立测试库验证。原生 Node 安全测试同时验证记录转义、慢响应和退出清理。
