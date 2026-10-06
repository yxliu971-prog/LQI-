# LQI

面向实验化学家的本地分子属性回归桌面应用。使用 PySide6、RDKit、Scikit-learn、LightGBM、XGBoost 和 SHAP；浅紫白色中文界面，英文技术术语附中文说明。实验数据在本机计算。


## 功能

- CSV / Excel 导入、工作表选择、列识别、表格编辑、非法分子结构标红。
- 24 项 RDKit 描述符、2048 位 Morgan 指纹、可选实验条件数值特征。
- Ridge、Lasso、Random Forest、LightGBM、XGBoost；嵌套分组交叉验证与网格搜索。
- 折外 R²、MAE、RMSE；分组 Bootstrap 模型区间；SHAP 前五项特征贡献。
- 内置 ESOL 水溶解度参考集，可离线使用、主动在线更新或添加本地参考集。
- 联合 PCA / t-SNE 化学空间、分子图悬停、结构相似性分析、新分子预测。
- HTML / PDF 诊断报告、CSV / JSON 分析导出、数据与设置保存恢复。

## 快速启动

**直接使用软件：** 在本仓库的 [Releases 下载区](https://github.com/yxliu971-prog/LQI-/releases) 下载 Windows 便携程序压缩包，解压完整文件夹后双击 `LQI.exe`。不要只取出 EXE 文件。

**运行或修改源码：** 通过 GitHub 下载的源码不包含本机 Python 环境及打包程序，首次使用需安装依赖。开发运行建议使用 Windows x64 和 Python 3.12。已配置好环境的本机项目可直接运行 `start-source.bat`；`start.bat` 优先启动本机 `dist/LQI/` 下的便携程序。

首次从 GitHub 获取源码时，双击根目录 `setup.bat` 安装项目依赖，成功后双击 `start-source.bat`。也可以在仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

已下载独立便携版本的用户可直接启动其中的 `LQI.exe`，应保留整个发布文件夹。

## 用自带数据体验

1. 数据与预处理 → **加载溶解度示例 · 60 条**。
2. 模型与解释 → 保持 Ridge（岭回归）、24 描述符、标准化缩放 → **开始训练与交叉验证**。
3. 化学空间 → **生成联合化学空间**；悬停查看分子结构。
4. 新分子预测 → 输入 `CC(=O)Oc1ccccc1C(=O)O`，附加特征留空 → **预测分子属性**。
5. 诊断报告 → 导出 HTML / PDF 或分析表格。

这组固定示例的折外指标约为 R² 0.856、MAE 0.683、RMSE 0.902。它只用于验证和体验流程，不代表对其他数据的保证。

软件顶部提供“使用说明”，也可查看 [快速体验](docs/自带数据快速体验.md)、[用户手册](docs/用户手册.md) 或离线打开 [使用说明网页](data/quickstart.html)。

## 导入自己的实验数据

打开根目录的 **导入模板** 文件夹，复制 [Excel 填写模板](导入模板/LQI_数据导入模板.xlsx) 或 [CSV 填写模板](导入模板/LQI_数据导入模板.csv)，填入自己的实测数据后再导入。Excel 的“填写数据”用于填写，“格式示例”展示 12 条公开数据，“填写说明”解释每列要求。

第一行是列名，每行一条实验记录。结构列和目标实测值必填；温度、时间、浓度可选。数值列只填写数字，单位放在列名中。详见 [数据导入格式说明](docs/数据导入格式说明.md) 或双击 [网页说明](导入模板/导入格式说明.html)。软件顶部“使用说明”也包含这套格式要求。

## 仓库结构

```text
main.py                  桌面应用入口
lqi/              数据、化学、模型、解释、界面、绘图、报告模块
data/                    内置公开数据、界面资源及离线帮助
examples/                60 条示例数据（CSV / Excel）
导入模板/                 Excel / CSV 填写模板、12 条格式示例和格式说明
docs/                    用户手册、设计说明、数据来源、截图和第三方声明
tests/                   核心和桌面交互测试
scripts/                 发布构建、第三方声明收集工具
.vscode/                 项目解释器与调试配置
.github/workflows/       Windows 自动测试配置
requirements.txt         运行依赖
requirements-dev.txt     测试与打包依赖
requirements-lock.txt    已验证环境的完整版本快照
setup.bat / start.bat    Windows 安装与一键启动入口
start-source.bat         使用本机开发环境运行源码
build.bat                Windows 便携程序构建入口
```

运行时生成的 `.venv/`、`user_data/`、`logs/`、构建目录和导出报告均已在 `.gitignore` 中排除。

## 开发与测试

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

`.vscode` 使用仓库内 `.venv` 解释器。需要复现已验证的完整环境时，可在空虚拟环境中安装 `requirements-lock.txt`。运行依赖、开发依赖与版本快照各有用途，不要把虚拟环境本身提交到仓库。

## 构建 Windows 便携版本

运行 `build.bat`，或安装开发依赖后执行：

```powershell
.\.venv\Scripts\python.exe scripts/build_release.py
```

结果写入 `releases/日期时间/LQI/`，整个目录可独立分发。每次构建使用新发布目录，保留旧版本中的用户数据。构建脚本隔离 DLL 搜索路径，防止误收集其他软件的 ICU/Qt 动态库。

独立程序支持 `LQI.exe --self-test 指定诊断目录`。自检使用很少的重采样次数来验证依赖与流程，不用于科学结论。

## 模型和数据边界

- 当前为单目标连续数值回归，至少 10 条有效观测、6 种不同分子；推荐少于 100 条。
- 描述符为选定的 24 项面板，另可选 Morgan 指纹；不包含反应指纹或自动反应机理推断。
- 同一规范化分子编码不跨验证折；缺失填充和缩放只在训练折拟合。缺失目标不做填充。
- Bootstrap 输出模型均值的重采样区间，不是校准的单次实验预测区间。SHAP 不代表化学因果关系。
- 低相似度只针对当前参考集；二维投影距离不等于化学相似度。
- 预载且支持在线更新的公开集为 ESOL；催化收率等其他参考集可本地导入。
- 项目文件保存数据和配置，重新打开后需要重训。

## 数据、第三方组件与许可证

公开数据出处见 [DATA_SOURCES.md](docs/DATA_SOURCES.md)，第三方组件声明见 [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md)，原始许可文件保存在 `docs/third_party_licenses/`。

本项目自身代码采用 [Apache License 2.0](LICENSE)。第三方组件和公开数据保留各自的来源与许可条件，本项目许可证不替代第三方许可。

## 上传 GitHub

本文件所在目录就是仓库根目录。使用 GitHub Desktop 或 Git 提交，`.gitignore` 会自动排除本机的 `dist/`、`.venv/`、用户实验数据与运行日志，这些文件仍保留在电脑上供正常使用。不要在网页中把整个文件夹全部拖入上传。具体操作见 [GitHub 上传说明](docs/GITHUB_UPLOAD.md)。
