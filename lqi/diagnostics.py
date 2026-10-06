"""Exercise the shipped binary without relying on a system Python installation."""
import json
import traceback
from pathlib import Path


def run(folder):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    state={"status":"running", "checks":[]}
    def save():
        (folder/"diagnostic.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    save()
    try:
        from PySide6.QtWidgets import QApplication
        from .data import DatasetStore
        from .ui import MainWindow
        from .engine import train,predict,TrainingConfig
        from .space import map_space
        from .reports import export_html,export_pdf,export_tables
        app=QApplication.instance() or QApplication([])
        store=DatasetStore(folder/"cache")
        sample=store.load().sample(24,random_state=42).reset_index(drop=True)
        from .data import read_table
        sample.to_excel(folder/"sample.xlsx",index=False)
        assert len(read_table(folder/"sample.xlsx"))==24
        state["checks"].append("Excel import")
        save()
        for model in ["Ridge","Lasso","Random Forest","LightGBM","XGBoost"]:
            result=train(sample,TrainingConfig(target_col="value",model=model,bootstrap=2))
            prediction=predict(result,"CCO")
            state["checks"].append({"model":model,"metrics":result["metrics"],"prediction":prediction})
            save()
        space=map_space(sample.head(4),"smiles","value",sample)
        export_html(folder/"smoke.html",result,space,prediction)
        export_pdf(folder/"smoke.pdf",result,space,prediction)
        export_tables(folder/"tables",result,space,prediction)
        state["checks"].append("PCA + HTML/PDF/CSV/JSON export")
        save()
        map_space(sample.head(4),"smiles","value",sample,"t-SNE")
        state["checks"].append("t-SNE")
        window=MainWindow()
        window.load_demo()
        window.training_done(result)
        window.space_done(space)
        window.show()
        app.processEvents()
        window.grab().save(str(folder/"window.png"))
        window.close()
        state["checks"].append("Native Qt window + table + rendering")
        state["status"]="passed"
        save()
        return 0
    except Exception:
        state.update(status="failed",error=traceback.format_exc())
        save()
        return 1
