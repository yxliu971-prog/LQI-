# 公开数据与技术来源

## Delaney / ESOL

- 快照文件：`data/delaney.csv`，1,128 条。
- 下载日期：2026-10-01。
- CSV 来源：https://raw.githubusercontent.com/deepchem/deepchem/master/datasets/delaney-processed.csv
- DeepChem 数据文件页面：https://github.com/deepchem/deepchem/blob/master/datasets/delaney-processed.csv
- 数据原始研究：John S. Delaney, “ESOL: Estimating Aqueous Solubility Directly from Molecular Structure”, Journal of Chemical Information and Computer Sciences, 2004, 44(3), 1000–1005. DOI: 10.1021/ci034243x。
- 使用列：`Compound ID`、`smiles`、`measured log solubility in mols per litre`。应用中统一为 name / smiles / value。
- 属性：logS，溶解度 mol/L 的十进对数。不要将其直接当作 mol/L 浓度。
- 示例：固定随机种子 42，抽取 60 条，不改写实验目标。其余原文件列不自动作为训练特征，避免意外使用由目标衍生的信息。
- 本文件保留来源追踪，不对原始数据另行声称新的独立许可；分发者应核对上游数据使用条件。DeepChem 项目源码许可证不自动等同于所有上游数据的独立许可。

在线更新只接受预定 HTTPS 地址并校验列结构、行数和 SMILES 有效率，采用 SHA-256 命名快照后原子更新本地 JSON 目录。目录记录更新时间与内容哈希；网络失败保留原有数据。

## 官方技术参考

- RDKit Morgan generator：https://www.rdkit.org/docs/source/rdkit.Chem.rdFingerprintGenerator.html
- RDKit 使用说明：https://www.rdkit.org/docs/GettingStartedInPython.html
- Scikit-learn 数据泄漏与 Pipeline：https://scikit-learn.org/stable/common_pitfalls.html
- Scikit-learn 嵌套交叉验证：https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html
- SHAP API：https://shap.readthedocs.io/en/stable/api.html
- Qt for Python 线程信号示例：https://doc.qt.io/qtforpython-6/examples/example_widgets_thread_signals.html

## 扩展参考集

可在“化学空间”中添加本地 CSV/Excel，选择 SMILES 与数值属性列。软件会保存用户指定的来源文件路径、列名和导入时间。对于催化反应收率，应明确 SMILES 对应底物、催化剂还是产物，并将必要实验条件作为附加特征；当前版本不自动构建反应指纹，也不将不同实验体系的收率强行合并。
