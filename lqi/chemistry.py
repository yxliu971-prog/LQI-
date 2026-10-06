from __future__ import annotations

import base64
import io
from functools import lru_cache

import numpy as np
from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import Descriptors, Draw, rdFingerprintGenerator

# A deliberately compact, interpretable descriptor panel for small datasets.
DESCRIPTORS = ["MolWt", "MolLogP", "TPSA", "NumHDonors", "NumHAcceptors",
               "NumRotatableBonds", "RingCount", "NumAromaticRings",
               "NumAliphaticRings", "FractionCSP3", "HeavyAtomCount", "NHOHCount",
               "NOCount", "NumHeteroatoms", "MolMR", "LabuteASA", "BertzCT",
               "BalabanJ", "HallKierAlpha", "Kappa1", "Kappa2", "Kappa3",
               "MaxPartialCharge", "MinPartialCharge"]
GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


@lru_cache(maxsize=20000)
def molecule(smiles: str):
    if not isinstance(smiles, str) or not smiles.strip():
        return None
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles.strip())
    return mol if mol is not None and mol.GetNumAtoms() else None


def canonical(smiles: str) -> str | None:
    mol = molecule(smiles)
    return Chem.MolToSmiles(mol) if mol is not None else None


def fingerprint(smiles: str):
    mol = molecule(smiles)
    if mol is None:
        raise ValueError(f"无法解析 SMILES：{smiles}")
    return GENERATOR.GetFingerprint(mol)


def feature_matrix(smiles, mode="descriptors"):
    names = DESCRIPTORS if mode == "descriptors" else [f"Morgan_{i:04d}" for i in range(2048)]
    rows = []
    for s in smiles:
        mol = molecule(str(s))
        if mol is None:
            raise ValueError(f"非法 SMILES：{s}")
        if mode == "morgan":
            rows.append(GENERATOR.GetFingerprintAsNumPy(mol).astype(float))
        else:
            row = []
            for name in names:
                try:
                    v = float(getattr(Descriptors, name)(mol))
                    row.append(v if np.isfinite(v) else np.nan)
                except (ValueError, RuntimeError, OverflowError, ZeroDivisionError):
                    row.append(np.nan)
            rows.append(row)
    return np.asarray(rows, dtype=float), list(names)


@lru_cache(maxsize=1024)
def molecule_png(smiles: str, width=300, height=180) -> bytes:
    mol = molecule(smiles)
    if mol is None:
        return b""
    out = io.BytesIO()
    Draw.MolToImage(mol, size=(width, height)).save(out, format="PNG")
    return out.getvalue()


def molecule_uri(smiles: str) -> str:
    return "data:image/png;base64," + base64.b64encode(molecule_png(smiles)).decode()


def nearest(smiles: str, reference, count=3):
    query = fingerprint(smiles)
    valid = reference[reference.smiles.map(lambda s: molecule(str(s)) is not None)].copy()
    scores = DataStructs.BulkTanimotoSimilarity(query, [fingerprint(str(s)) for s in valid.smiles])
    valid["similarity"] = scores
    return valid.sort_values("similarity", ascending=False).head(count).to_dict("records")
