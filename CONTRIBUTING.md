# 贡献指南

使用虚构数据复现问题，描述来源类型、筛选条件、预期结果和实际结果。禁止提交 `.env`、真实 Excel、数据库备份、内部地址、客户信息或设备凭据。

修改后运行：

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --check web/app.js
node tests/frontend.cjs
python scripts/check_release.py
```

测试前提、隔离方式和 MySQL 专用空库命令见 [测试说明](docs/TESTING.md)；CI 配置见 `.github/workflows/ci.yml`。PR 说明业务变化、测试结果和升级影响。提交的代码按项目 MIT 协议分发，新增依赖应保留其许可证。
