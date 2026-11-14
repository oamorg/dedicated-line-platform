# GitHub 发布准备

建议仓库名 `dedicated-line-platform`，描述：政企专线与 ONU 台账导入、查询、统计及权限管理平台。MIT 版权主体保留 `hjie`。

将本源码目录作为仓库根目录，根目录应包含 README、LICENSE、app、web、sql、tests、.github。不要从内部工作目录执行 `git add .`，也不要上传旧交付整包、含数据数据库或 `.git` 历史。

创建远程仓库前可完成本地提交：

```bash
git init -b main
git add README.md LICENSE SECURITY.md CONTRIBUTING.md .gitignore .env.example requirements*.txt deploy.sh app web config sql scripts tests docs .github
python scripts/check_release.py --tracked
git diff --cached --stat
git diff --cached
git commit -m "Prepare MIT community release"
```

确认暂存内容后，通过已登录的 GitHub CLI 发布到自己的账户：

```bash
gh repo create dedicated-line-platform --public --source=. --remote=origin --push
```

同步前运行上述检查。此次准备未创建远程仓库、未提交或推送；账号与仓库归属由发布者的 Git/GitHub 配置决定。若目标仓库已经存在，添加该仓库的 origin 后再推送，不要重复创建。

发布后检查 Actions 中的 Python、MySQL 与依赖审计结果。开启 Secret scanning / Push protection 和私密漏洞报告，并配置 main 分支保护。

Actions 用法参考官方仓库：[checkout](https://github.com/actions/checkout)、[setup-python](https://github.com/actions/setup-python)、[setup-node](https://github.com/actions/setup-node)。

生成发布附件：

```bash
python scripts/build_release.py --version 20261115-r2
cd dist
shasum -a 256 -c SHA256SUMS.txt
```

整包内的校验清单只校验包内文件；外部清单额外校验整包本身，避免自校验循环。仅使用本次重新生成的社区发布文件。
