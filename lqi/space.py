from __future__ import annotations

import numpy as np
from rdkit import DataStructs
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from threadpoolctl import threadpool_limits

from .chemistry import feature_matrix, fingerprint, molecule


def map_space(user_frame, smiles_col, target_col, reference, method="PCA", threshold=.4):
    users = user_frame[user_frame[smiles_col].map(lambda s: molecule(str(s)) is not None)].copy()
    if users.empty:
        raise ValueError("用户数据没有有效 SMILES。")
    if len(users) + len(reference) > 12000:
        raise ValueError("联合映射最多支持 12,000 个分子。")
    records = [{"smiles": str(r.smiles), "value": r.value, "name": str(r.name), "source": "公开/参考数据"} for r in reference.itertuples(index=False)]
    records += [{"smiles": str(row[smiles_col]), "value": str(row[target_col]), "name": f"用户行 {i+2}", "source": "用户数据"} for i, row in users.iterrows()]
    X, _ = feature_matrix([r["smiles"] for r in records], "morgan")
    with threadpool_limits(limits=1):
        if method == "PCA":
            reducer = PCA(n_components=2, random_state=42)
            coordinates = reducer.fit_transform(X)
            detail = f"前两主成分解释方差 {reducer.explained_variance_ratio_.sum():.1%}"
        else:
            reduced = PCA(n_components=min(30, len(X)-1, X.shape[1]), random_state=42).fit_transform(X)
            perplexity = min(30., max(2., (len(X)-1)/3))
            coordinates = TSNE(n_components=2, perplexity=perplexity, init="pca", learning_rate="auto", random_state=42).fit_transform(reduced)
            detail = f"perplexity={perplexity:g} · 坐标距离不等于化学相似度"
    refs = [fingerprint(str(s)) for s in reference.smiles]
    for i, record in enumerate(records):
        record["x"], record["y"] = map(float, coordinates[i])
        if record["source"] == "用户数据":
            score = max(DataStructs.BulkTanimotoSimilarity(fingerprint(record["smiles"]), refs), default=0.)
            record["similarity"] = score
            record["novel"] = score < threshold
        else:
            record.update(similarity=1., novel=False)
    return {"records": records, "method": method, "threshold": threshold, "detail": detail,
            "novel_count": sum(r["novel"] for r in records), "user_count": len(users), "reference_count": len(reference)}
