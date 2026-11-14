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
bash -n deploy.sh
python scripts/check_release.py
```

普通 pytest 在 `tests/conftest.py` 中禁用 dotenv、强制内存 SQLite；不会使用运行环境的 `DATABASE_URL`。`mysql_smoke.py` 不被普通 pytest 自动执行。测试输出中的第三方弃用提示不等于失败；判断 pytest / Node 进程退出码与失败条目。

## 覆盖范围

| 检查 | 内容 | 是否需要 MySQL |
| --- | --- | --- |
| `test_community.py` | 鉴权、viewer 权限、SN 参数绑定、IPVPN 映射、完整原始数据、改密撤销会话、导入日志路径 | 否，部分数据库操作使用 SQLite / Mock |
| `test_release_workflow.py` | 测试数据库保护、首次部署停止于配置步骤、包内外哈希、敏感文件排除、文档相对链接 | 否 |
| `frontend.cjs` | 虚构样例、CSV 内容转义、表头顺序、预览隔离 | 否，Node VM，不是浏览器视觉测试 |
| `mysql_smoke.py` | 重复初始化、无默认账号、Excel 演练/导入/去重、三类角色、详情、导出、退出登录 | 是，新建本机空测试库 |
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
unset MYSQL_TEST_DATABASE_URL
```

脚本临时生成虚构 Excel，演练后验证无业务行，正式导入及再次导入后验证每类记录只有一条，并通过真实 API 检查 viewer/exporter/admin 权限。测试结束清除本轮合成记录和用户，保留表结构以便排错；下次运行应重新创建空的专用测试库。失败的表结构初始化也可能留下表，不能把失败当作已回滚。

GitHub CI 为 MySQL 8.0/8.4 各启一个临时容器，不需要配置生产 Secrets。CI 数据库密码仅适用于临时测试容器。

## 发布前检查

```bash
python -m pip check
python -m pip_audit
python scripts/check_release.py
python scripts/build_release.py --version 20261115-r2
cd dist
shasum -a 256 -c SHA256SUMS.txt
```

Linux 可用 `sha256sum -c SHA256SUMS.txt`。在独立 Git 仓库暂存后再执行 `python scripts/check_release.py --tracked`，它会核对暂存索引中是否混入非发布文件。

已完成和未完成的实际验证记录见 [REVIEW.md](REVIEW.md)。仅通过单元测试不代表真实 MySQL、Linux 服务或浏览器已通过验收。
