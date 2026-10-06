"""Display-only Chinese annotations. Never modify SMILES, column IDs or model keys."""
import re

TERMS = {
    "MOLECULAR LEARNING STUDIO": "分子学习工作台", "WORKSPACE": "实验工作台",
    "Random Forest": "随机森林", "Ridge": "岭回归", "Lasso": "套索回归",
    "LightGBM": "轻量梯度提升树", "XGBoost": "极端梯度提升树",
    "StandardScaler": "标准化缩放", "MinMaxScaler": "最小最大值缩放",
    "Bootstrap": "自助重采样", "SHAP": "沙普利特征贡献", "TOP 5": "前五项",
    "Morgan": "摩根", "Tanimoto": "谷本相似度", "PCA": "主成分分析",
    "t-SNE": "分布随机邻域嵌入", "perplexity": "困惑度",
    "canonical SMILES": "规范化分子编码", "SMILES": "分子线性编码", "smiles": "分子线性编码",
    "logS (mol/L)": "摩尔每升溶解度的十进对数", "logS": "溶解度的十进对数",
    "mol/L": "摩尔每升", "R²": "决定系数", "R2": "决定系数",
    "MAE": "平均绝对误差", "RMSE": "均方根误差", "OOF": "折外预测",
    "CSV": "逗号分隔表格", "Excel": "电子表格", "JSON": "结构化数据",
    "HTML": "网页格式", "PDF": "便携文档格式", "ESOL": "水溶解度数据集",
    "Delaney": "德莱尼", "RDKit": "化学信息工具库",
    "MolWt": "分子量", "MolLogP": "脂水分配系数对数", "TPSA": "拓扑极性表面积",
    "NumHDonors": "氢键供体数", "NumHAcceptors": "氢键受体数",
    "NumRotatableBonds": "可旋转键数", "RingCount": "环数",
    "NumAromaticRings": "芳香环数", "NumAliphaticRings": "非芳香环数",
    "FractionCSP3": "饱和碳原子比例", "HeavyAtomCount": "重原子数",
    "NHOHCount": "氮氧连接氢计数", "NOCount": "氮氧原子计数",
    "NumHeteroatoms": "杂原子数", "MolMR": "分子摩尔折射率",
    "LabuteASA": "拉布特近似表面积", "BertzCT": "伯茨分子复杂度",
    "BalabanJ": "巴拉班拓扑指数", "HallKierAlpha": "霍尔基尔修正参数",
    "Kappa1": "一阶形状指数", "Kappa2": "二阶形状指数", "Kappa3": "三阶形状指数",
    "MaxPartialCharge": "最大部分电荷", "MinPartialCharge": "最小部分电荷",
    "name": "名称", "value": "属性值", "temperature": "温度", "Temperature": "温度",
    "time": "时间", "yield": "收率", "target": "目标属性",
}
PATTERN = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(k) for k in sorted(TERMS, key=len, reverse=True)) + r")(?![A-Za-z0-9_]|（)")


def annotate(text):
    return PATTERN.sub(lambda m: m.group()+"（"+TERMS[m.group()]+"）", str(text))


def feature_label(name):
    if str(name).startswith("Morgan_"):
        return f"{name}（摩根指纹第 {int(name.split('_')[-1])} 位）"
    return annotate(name)


def parameter_label(parameters):
    names={"alpha":"正则化强度", "max_depth":"最大树深", "min_samples_leaf":"叶节点最少样本数", "num_leaves":"叶节点数", "reg_lambda":"二范数正则化强度"}
    return "；".join(f"{names.get(k.split('__')[-1],k)}：{'不限制' if v is None else v}" for k,v in parameters.items())
