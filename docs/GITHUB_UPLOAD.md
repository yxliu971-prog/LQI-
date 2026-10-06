# 将整理后的项目上传到 GitHub

本说明的“项目目录”指包含 README.md、main.py、lqi 等文件的这一层目录。

## 推荐：GitHub Desktop

1. 打开 GitHub Desktop，选择 File → Add local repository（添加本地仓库）。
2. 选择这个项目目录。如果提示尚不是 Git 仓库，按界面链接在这个目录创建仓库。
3. 查看变更列表：应包含源码、文档、测试和公开示例；不应出现 `.venv`、EXE、用户实验数据或运行日志。
4. 填写提交说明，例如 `Initial LQI source`，提交到主分支。
5. 点击 Publish repository（发布仓库），填写仓库名（例如 `LQI`）并自行选择公开或私有。

本次整理没有登录账户、创建远程仓库或执行上传操作。

## 命令行方式

在项目目录打开终端，先创建本地仓库并提交：

```powershell
git init -b main
git add .
git status
git commit -m "Initial LQI source"
```

如首次使用 Git，按 Git 提示设置你自己的提交用户名与邮箱。然后在 GitHub 创建空仓库，复制它显示的远程地址：

```powershell
git remote add origin <从你的GitHub仓库复制的地址>
git push -u origin main
```

尖括号内容需替换为自己的真实地址，不要原样执行。认证由 GitHub 的登录流程处理，不要把密码或访问令牌写进源码或文档。

## 上传哪些内容

使用 GitHub Desktop 或 Git 上传本项目目录内的源码、配置、文档、公开数据与测试。本机的完整项目保留了 `dist/` 便携程序和 `.venv/` 开发环境，这两项由 `.gitignore` 自动排除，仍可在本机运行。不要在网页中将整个目录全部拖入上传，也不要上传本机资料或快捷方式。

`.gitignore` 已排除环境、缓存、生成的报告、构建输出、日志和本地数据目录。若以后向其他位置加入自己的实验表，提交前仍应检查。

## 可运行软件如何分发

若以后需要提供桌面下载，可在 GitHub Releases 中附上整个便携目录的压缩包，而不是将数百 MB 的运行依赖提交到源码仓库。

GitHub 官方资料：[添加现有本地代码](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)、[大文件限制与 Releases](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。
