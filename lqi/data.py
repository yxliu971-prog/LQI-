from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .chemistry import molecule

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
RESOURCE = Path(getattr(sys, "_MEIPASS", ROOT))
SOURCE_URL = "https://raw.githubusercontent.com/deepchem/deepchem/master/datasets/delaney-processed.csv"


def read_table(path, sheet=0):
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        frame = pd.read_excel(path, sheet_name=sheet)
    elif path.suffix.lower() == ".csv":
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                frame = pd.read_csv(path, encoding=encoding, sep=None, engine="python")
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("无法识别 CSV 编码，请另存为 UTF-8 CSV。")
    else:
        raise ValueError("只支持 .csv 和 .xlsx 文件。")
    if frame.empty:
        raise ValueError("文件中没有数据行。")
    if len(frame) > 10000:
        raise ValueError("本版本支持最多 10,000 行；推荐以小于 100 行的数据开展实验。")
    frame.columns = [str(c).strip() for c in frame.columns]
    if len(set(frame.columns)) != len(frame.columns):
        raise ValueError("存在重复列名，请修改后重新导入。")
    return frame.reset_index(drop=True)


def detect_columns(frame):
    scores = {}
    for col in frame.columns:
        sample = frame[col].dropna().astype(str).head(30)
        scores[col] = (sum(molecule(s) is not None for s in sample) / max(1, len(sample)))
    smiles = max(scores, key=lambda c: (scores[c], "smile" in c.lower()))
    numeric = [c for c in frame.columns if c != smiles and pd.to_numeric(frame[c], errors="coerce").notna().mean() >= .5]
    target = next((c for c in numeric if any(w in c.lower() for w in ["measured", "target", "yield", "收率", "溶解", "log_s", "logs", "带隙"])), numeric[-1] if numeric else None)
    return smiles, target, numeric


def validate_rows(frame, smiles_col, target_col):
    bad_smiles = frame[smiles_col].map(lambda x: molecule(str(x)) is None).to_numpy()
    target = pd.to_numeric(frame[target_col], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    bad_target = ~np.isfinite(target)
    return bad_smiles, bad_target


class DatasetStore:
    """JSON registry + CSV snapshots; updates never destroy a valid offline snapshot."""
    def __init__(self, folder=None):
        self.folder = (Path(folder) if folder else ROOT / "user_data").resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.registry = self.folder / "catalog.json"
        if not self.registry.exists():
            self._save({"datasets": [{"id": "delaney", "name": "Delaney / ESOL 溶解度", "property": "logS (mol/L)", "path": "", "source": SOURCE_URL, "updated": "内置快照"}]})

    def catalog(self):
        return json.loads(self.registry.read_text(encoding="utf-8"))["datasets"]

    def _save(self, data):
        temp = self.registry.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.registry)

    def load(self, dataset_id="delaney"):
        entry = next(x for x in self.catalog() if x["id"] == dataset_id)
        path = Path(entry["path"]) if entry["path"] else RESOURCE / "data" / "delaney.csv"
        if entry["path"] and not path.is_absolute():
            path = self.folder / path
        if dataset_id == "delaney":
            raw = pd.read_csv(path)
            out = raw.rename(columns={"Compound ID": "name", "measured log solubility in mols per litre": "value"})[["name", "smiles", "value"]]
        else:
            out = pd.read_csv(path)
        return out[out.smiles.map(lambda s: molecule(str(s)) is not None)].reset_index(drop=True)

    def update_delaney(self):
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "LQI/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read(10_000_001)
        if len(data) > 10_000_000:
            raise ValueError("下载文件超过大小限制。")
        frame = pd.read_csv(io.BytesIO(data))
        required = {"Compound ID", "smiles", "measured log solubility in mols per litre"}
        if not required.issubset(frame.columns) or len(frame) < 100:
            raise ValueError("公开源格式变化，已保留原有离线数据。")
        if frame.smiles.map(lambda s: molecule(str(s)) is not None).mean() < .95:
            raise ValueError("公开源结构校验未通过，已保留原有离线数据。")
        # Immutable content-addressed snapshot; registry swap is atomic.
        digest = hashlib.sha256(data).hexdigest()
        path = self.folder / f"delaney_{digest[:12]}.csv"
        path.write_bytes(data)
        catalog = self.catalog()
        entry = next(x for x in catalog if x["id"] == "delaney")
        entry.update(path=path.name, updated=datetime.now(timezone.utc).isoformat(), sha256=digest)
        self._save({"datasets": catalog})
        return len(frame)

    def add_local(self, frame, name, smiles_col, target_col, source="用户导入"):
        bad_s, bad_y = validate_rows(frame, smiles_col, target_col)
        if bad_s.any() or bad_y.any():
            raise ValueError("参考集含无效结构或缺失属性，请清理后再导入。")
        out = pd.DataFrame({"name": [f"{name} #{i+1}" for i in range(len(frame))], "smiles": frame[smiles_col].astype(str), "value": pd.to_numeric(frame[target_col])})
        key = hashlib.sha256(out.to_csv(index=False).encode()).hexdigest()[:12]
        path = self.folder / f"custom_{key}.csv"
        out.to_csv(path, index=False, encoding="utf-8-sig")
        catalog = [x for x in self.catalog() if x["id"] != key]
        catalog.append({"id": key, "name": name, "path": path.name, "source": source, "property": target_col, "updated": datetime.now(timezone.utc).isoformat()})
        self._save({"datasets": catalog})
        return key
