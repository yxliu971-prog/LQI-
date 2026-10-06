import json
import numpy as np
import pandas as pd
import pytest
from lqi.chemistry import canonical, feature_matrix, molecule, nearest
from lqi.data import DatasetStore, read_table, detect_columns, validate_rows
from lqi.engine import TrainingConfig, prepare, train, predict
from lqi.space import map_space
from lqi.reports import export_html, export_pdf, export_tables


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    return DatasetStore(tmp_path_factory.mktemp("store")).load().sample(30,random_state=42).reset_index(drop=True)


@pytest.fixture(scope="module")
def result(sample):
    return train(sample,TrainingConfig(target_col="value",bootstrap=20))


def test_chemistry():
    assert molecule("bad smiles") is None
    assert molecule("") is None
    assert canonical("OCC")==canonical("CCO")
    X,names=feature_matrix(["CCO","c1ccccc1"])
    assert X.shape==(2,24) and np.isfinite(X).all()
    X,names=feature_matrix(["CCO"],"morgan")
    assert X.shape==(1,2048) and set(np.unique(X))=={0.,1.}


@pytest.mark.parametrize("suffix",["csv","xlsx"])
def test_import(tmp_path,sample,suffix):
    path=tmp_path/f"data.{suffix}"
    if suffix=="csv":sample.to_csv(path,index=False)
    else:sample.to_excel(path,index=False)
    frame=read_table(path)
    assert len(frame)==len(sample)
    s,t,n=detect_columns(frame)
    assert s=="smiles" and t=="value"


def test_validation_and_missing_target(sample):
    frame=sample.copy()
    frame.loc[0,"smiles"]="not_a_smiles"
    frame.loc[1,"value"]=np.nan
    c=TrainingConfig(target_col="value")
    with pytest.raises(ValueError,match="非法 SMILES"):prepare(frame,c)
    c.exclude_invalid=True
    X,y,groups,names,clean,audit=prepare(frame,c)
    assert len(y)==28 and audit["dropped_rows"]==2
    assert 0 not in clean.index and 1 not in clean.index


def test_extras_and_leakage_rejection(sample):
    frame=sample.copy()
    frame["temperature"]=np.arange(len(frame),dtype=float)
    frame.loc[0,"temperature"]=np.nan
    c=TrainingConfig(target_col="value",extra_cols=("temperature",),missing="drop")
    assert prepare(frame,c)[-1]["used_rows"]==29
    c.extra_cols=("value",)
    with pytest.raises(ValueError,match="目标列"):prepare(frame,c)


def test_nested_cv_and_prediction(result,sample):
    assert len(result["folds"])==5
    for f in result["folds"]:
        assert not set(f["train_groups"])&set(f["test_groups"])
    assert sum(f["test"] for f in result["folds"])==len(sample)
    assert np.isfinite(result["oof"]).all()
    p=predict(result,"CCO")
    assert np.isfinite(p["prediction"]) and p["lower"]<=p["upper"]
    with pytest.raises(ValueError):predict(result,"invalid")
    assert len(result["importance"])==24


def test_duplicate_groups(sample):
    frame=pd.concat([sample,sample.iloc[:3]],ignore_index=True)
    result=train(frame,TrainingConfig(target_col="value",bootstrap=2))
    for f in result["folds"]:assert not set(f["train_groups"])&set(f["test_groups"])


@pytest.mark.parametrize("model",["Lasso","Random Forest","LightGBM","XGBoost"])
def test_all_models(sample,model):
    result=train(sample,TrainingConfig(target_col="value",model=model,bootstrap=2))
    assert np.isfinite(result["shap_values"]).all()
    assert np.isfinite(predict(result,"CCO")["prediction"])
    assert isinstance(result["warnings"],list)


def test_morgan_model(sample):
    result=train(sample,TrainingConfig(target_col="value",mode="morgan",bootstrap=2))
    assert result["shap_values"].shape==(30,2048)
    assert np.isfinite(predict(result,"CCO")["prediction"])


@pytest.mark.parametrize("method",["PCA","t-SNE"])
def test_space(sample,method):
    result=map_space(sample.head(8),"smiles","value",sample,method)
    assert result["user_count"]==8
    assert result["novel_count"]==0
    assert len(result["records"])==38
    for r in result["records"]:assert np.isfinite(r["x"]) and np.isfinite(r["y"])
    assert nearest(sample.smiles.iloc[0],sample)[0]["similarity"]==1


def test_local_catalog(tmp_path,sample):
    store=DatasetStore(tmp_path)
    key=store.add_local(sample,"my reference","smiles","value")
    assert len(store.load(key))==len(sample)
    assert len(store.catalog())==2


def test_portable_catalog(tmp_path,sample):
    import shutil
    original=tmp_path/"original"
    store=DatasetStore(original)
    key=store.add_local(sample,"portable reference","smiles","value")
    copied=tmp_path/"copied"
    shutil.copytree(original,copied)
    assert len(DatasetStore(copied).load(key))==len(sample)
    assert not __import__('pathlib').Path(store.catalog()[-1]["path"]).is_absolute()


def test_failed_update_preserves_cache(tmp_path,monkeypatch):
    import urllib.request
    store=DatasetStore(tmp_path)
    before=store.registry.read_bytes()
    def fail(*args,**kwargs):raise OSError("offline")
    monkeypatch.setattr(urllib.request,"urlopen",fail)
    with pytest.raises(OSError):store.update_delaney()
    assert store.registry.read_bytes()==before
    assert len(store.load())>1000


def test_report_exports(tmp_path,result,sample):
    import fitz
    space=map_space(sample.head(8),"smiles","value",sample)
    p=predict(result,"CCO")
    export_html(tmp_path/"report.html",result,space,p)
    export_pdf(tmp_path/"report.pdf",result,space,p)
    export_tables(tmp_path,result,space,p)
    assert "data:image/png;base64" in (tmp_path/"report.html").read_text(encoding="utf-8")
    pdf=fitz.open(tmp_path/"report.pdf")
    assert len(pdf)>=3
    assert "LQI" in pdf[0].get_text()
    assert len(pd.read_csv(tmp_path/"top5_features.csv"))==5
    payload=json.loads((tmp_path/"analysis.json").read_text(encoding="utf-8"))
    assert payload["metrics"]==result["metrics"]

