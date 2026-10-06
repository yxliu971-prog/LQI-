from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from threadpoolctl import threadpool_limits

from .chemistry import canonical, feature_matrix
from .data import validate_rows


@dataclass
class TrainingConfig:
    smiles_col: str = "smiles"
    target_col: str = "logS"
    mode: str = "descriptors"
    model: str = "Ridge"
    missing: str = "median"
    scaling: str = "standard"
    extra_cols: tuple = ()
    exclude_invalid: bool = False
    bootstrap: int = 60
    seed: int = 42


def prepare(frame, config):
    if config.target_col in config.extra_cols or config.smiles_col in config.extra_cols:
        raise ValueError("目标列和结构列不能同时用作附加特征。")
    invalid, missing_y = validate_rows(frame, config.smiles_col, config.target_col)
    if invalid.any() and not config.exclude_invalid:
        raise ValueError(f"存在 {invalid.sum()} 个非法 SMILES，请修正，或勾选排除非法结构。")
    mask = ~invalid & ~missing_y
    clean = frame.loc[mask].copy()
    X, names = feature_matrix(clean[config.smiles_col].astype(str), config.mode)
    if config.extra_cols:
        extra = clean[list(config.extra_cols)].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float, na_value=np.nan)
        X = np.column_stack([X, extra])
        names += list(config.extra_cols)
    X[~np.isfinite(X)] = np.nan
    missing_features = np.isnan(X).any(axis=1)
    dropped_features = int(missing_features.sum()) if config.missing == "drop" else 0
    if config.missing == "drop":
        clean = clean.loc[~missing_features].copy()
        X = X[~missing_features]
    y = pd.to_numeric(clean[config.target_col]).to_numpy(dtype=float)
    groups = np.array([canonical(str(s)) for s in clean[config.smiles_col]])
    if len(y) < 10 or len(np.unique(groups)) < 6:
        raise ValueError("建模至少需要 10 条有效观测、6 种不同分子；更少样本无法提供有意义的嵌套验证。")
    if np.ptp(y) == 0:
        raise ValueError("目标值全部相同，无法评估回归模型。")
    audit = {"input_rows": len(frame), "used_rows": len(y), "invalid_smiles": int(invalid.sum()),
             "missing_target": int(missing_y.sum()), "dropped_features": dropped_features,
             "dropped_rows": len(frame)-len(y), "unique_molecules": len(np.unique(groups)),
             "feature_count": len(names), "source_rows": (clean.index.to_numpy()+2).tolist()}
    return X, y, groups, names, clean, audit


def make_pipeline(config):
    if config.model == "Ridge":
        model, grid = Ridge(), {"model__alpha": [.1, 1., 10., 100.]}
    elif config.model == "Lasso":
        model, grid = Lasso(max_iter=20000), {"model__alpha": [.001, .01, .1, 1.]}
    elif config.model == "Random Forest":
        model = RandomForestRegressor(n_estimators=100, random_state=config.seed, n_jobs=1)
        grid = {"model__max_depth": [3, None], "model__min_samples_leaf": [1, 3]}
    elif config.model == "LightGBM":
        from lightgbm import LGBMRegressor
        model = LGBMRegressor(n_estimators=100, learning_rate=.05, min_child_samples=3, verbosity=-1, n_jobs=1, random_state=config.seed)
        grid = {"model__num_leaves": [3, 7], "model__reg_lambda": [1., 10.]}
    elif config.model == "XGBoost":
        from xgboost import XGBRegressor
        model = XGBRegressor(n_estimators=100, learning_rate=.05, n_jobs=1, random_state=config.seed, objective="reg:squarederror")
        grid = {"model__max_depth": [2, 3], "model__reg_lambda": [1., 10.]}
    else:
        raise ValueError(f"未知模型：{config.model}")
    scaler = StandardScaler() if config.scaling == "standard" else MinMaxScaler() if config.scaling == "minmax" else "passthrough"
    return Pipeline([("imputer", SimpleImputer(strategy="median" if config.missing == "drop" else config.missing, keep_empty_features=True)), ("scaler", scaler), ("model", model)]), grid


def splitter(groups, seed):
    return GroupKFold(n_splits=min(5, len(np.unique(groups))), shuffle=True, random_state=seed)


def train(frame, config, progress=lambda message: None):
    with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", ConvergenceWarning)
        result = _train(frame, config, progress)
    convergence = [w for w in captured if issubclass(w.category, ConvergenceWarning)]
    numerical = [w for w in captured if issubclass(w.category, RuntimeWarning)]
    result["warnings"] = []
    if convergence:
        result["warnings"].append(f"{len(convergence)} 次拟合出现收敛警告（包含调参候选或 Bootstrap 模型）；当前结果需谨慎解释，可尝试 Ridge、减少相关特征或选择更稳定的模型。首条：{convergence[0].message}")
    if numerical:
        result["warnings"].append(f"{len(numerical)} 次数值警告；首条：{numerical[0].message}")
    return result


def _train(frame, config, progress):
    X, y, groups, names, clean, audit = prepare(frame, config)
    pipe, grid = make_pipeline(config)
    oof = np.empty_like(y)
    folds = []
    for k, (tr, te) in enumerate(splitter(groups, config.seed).split(X, y, groups), 1):
        progress(f"嵌套交叉验证 {k}/5 · 分子分组，折内预处理与调参")
        search = GridSearchCV(clone(pipe), grid, cv=splitter(groups[tr], config.seed), scoring="neg_mean_absolute_error", n_jobs=1, error_score="raise")
        search.fit(X[tr], y[tr], groups=groups[tr])
        oof[te] = search.predict(X[te])
        folds.append({"fold": k, "train": len(tr), "test": len(te), "inner_folds": min(5, len(np.unique(groups[tr]))), "mae": float(mean_absolute_error(y[te], oof[te])), "train_groups": sorted(set(groups[tr])), "test_groups": sorted(set(groups[te]))})
    progress("全数据拟合最终模型")
    final_search = GridSearchCV(pipe, grid, cv=splitter(groups, config.seed), scoring="neg_mean_absolute_error", n_jobs=1, error_score="raise")
    final_search.fit(X, y, groups=groups)
    fitted = final_search.best_estimator_
    rng = np.random.default_rng(config.seed)
    boots = []
    unique = np.unique(groups)
    for b in range(config.bootstrap):
        if b % 10 == 0:
            progress(f"Bootstrap 不确定性估计 {b}/{config.bootstrap}")
        chosen = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([np.flatnonzero(groups == g) for g in chosen])
        est = clone(fitted).fit(X[idx], y[idx])
        boots.append(est)
    progress("计算 SHAP 特征贡献")
    import shap
    transformed = fitted[:-1].transform(X)
    model = fitted.named_steps["model"]
    if config.model in ("Ridge", "Lasso"):
        explainer = shap.LinearExplainer(model, transformed)
        values = np.asarray(explainer.shap_values(transformed))
    else:
        explainer = shap.TreeExplainer(model)
        values = np.asarray(explainer.shap_values(transformed))
    importance = pd.DataFrame({"feature": names, "mean_abs_shap": np.abs(values).mean(axis=0)}).sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    return {"config": asdict(config), "pipeline": fitted, "bootstrap_models": boots, "features": names,
            "X": X, "y": y, "oof": oof, "groups": groups, "shap_values": values, "importance": importance,
            "metrics": {"R2": float(r2_score(y, oof)), "MAE": float(mean_absolute_error(y, oof)), "RMSE": float(np.sqrt(mean_squared_error(y, oof)))},
            "best_params": final_search.best_params_, "audit": audit, "folds": folds,
            "timestamp": datetime.now().isoformat(timespec="seconds"), "smiles": clean[config.smiles_col].astype(str).tolist()}


def predict(result, smiles, extra=None):
    config = TrainingConfig(**result["config"])
    X, _ = feature_matrix([smiles], config.mode)
    if config.extra_cols:
        extra = extra or {}
        missing = [c for c in config.extra_cols if c not in extra or not np.isfinite(float(extra[c]))]
        if missing:
            raise ValueError("请填写附加实验条件：" + ", ".join(missing))
        X = np.column_stack([X, [[float(extra[c]) for c in config.extra_cols]]])
    if config.missing == "drop" and not np.isfinite(X).all():
        raise ValueError("新分子特征存在缺失；当前模型选择了删除缺失行，无法预测。")
    point = float(result["pipeline"].predict(X)[0])
    samples = np.array([m.predict(X)[0] for m in result["bootstrap_models"]])
    lo, hi = np.quantile(samples, [.025, .975])
    return {"smiles": smiles, "prediction": point, "lower": float(lo), "upper": float(hi), "bootstrap_count": len(samples), "interval": "95% Bootstrap 模型均值区间（非单次实验预测区间）"}
