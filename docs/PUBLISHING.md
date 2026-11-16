# GitHub 发布说明

公开仓库：[oamorg/dedicated-line-platform](https://github.com/oamorg/dedicated-line-platform)，默认分支 `main`。描述：政企专线与 ONU 台账导入、查询、统计及权限管理平台。MIT 版权声明统一为 `Copyright (c) 2026 oamorg`。

2026-11-16 本轮为源码更新，不自动发布新标签或修改 v0.1.0 附件。下文 v0.1.0 是历史发布示例；下一次正式发布必须使用新的版本号，并固定到完成 CI 的提交，不能用新内容覆盖旧标签或附件。

2026-11-15 已完成首次推送及 [Community checks](https://github.com/oamorg/dedicated-line-platform/actions/runs/43642821184) 验证。以下建仓命令供发布独立副本参考；更新现有仓库请使用后面的同步步骤。

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

同步前运行上述检查，账号与仓库归属由发布者的 Git/GitHub 配置决定。若目标仓库已经存在，添加该仓库的 origin 后再推送，不要重复创建。更新现有仓库时，先确认当前分支和远程地址，再暂存需要发布的具体文件：

```bash
git status --short --branch
git remote -v
git add <本次修改的源码或文档文件>
python scripts/check_release.py --tracked
git diff --cached --check
git diff --cached
git commit -m "Describe the community update"
git push origin HEAD:main
gh run list --workflow ci.yml --branch main --limit 3
```

若使用 GitHub CLI 的 OAuth 登录且推送 `.github/workflows/ci.yml` 被拒绝，运行 `gh auth refresh -h github.com -s workflow`，由账号持有者完成设备授权后重试。不要把令牌放进源码或远程 URL，也不要删除 CI 文件来绕过权限检查。

发布后检查 Actions 中的 Python、MySQL 与依赖审计结果。开启 Secret scanning / Push protection 和私密漏洞报告，并配置 main 分支保护。

Actions 用法参考官方仓库：[checkout](https://github.com/actions/checkout)、[setup-python](https://github.com/actions/setup-python)、[setup-node](https://github.com/actions/setup-node)。

生成发布附件：

```bash
python scripts/build_release.py --version 0.1.0
cd dist
shasum -a 256 -c SHA256SUMS.txt
```

整包内的校验清单只校验包内文件；外部清单额外校验整包本身，避免自校验循环。仅使用本次重新生成的社区发布文件。

Release 应固定到通过 CI 的提交，以 `v0.1.0` 为标签。上传时明确列出五个附件，不使用包含历史产物的 `dist/*`：

- `dedicated-line-community-release-0.1.0.tar.gz`：整包，含源码包、空库 SQL、完整文档、MIT 许可及包内校验清单。
- `dedicated-line-community-source-0.1.0.tar.gz`：独立源码包。
- `dedicated_line_empty.sql`：仅结构、角色和权限，不含账号、会话或业务记录。
- `DEPLOYMENT.md`：可独立阅读的部署指南。
- `SHA256SUMS.txt`：上述四个文件的 SHA-256 校验值。

建议先创建草稿，回下载附件验证校验值、源码与标签一致后再公开。发布说明中列明环境、无默认管理员、真实数据排除范围和 CI 链接。不要上传内部备份或将已有 Release 附件静默替换。
