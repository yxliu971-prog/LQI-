import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
from pathlib import Path
import time
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from lqi.ui import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait_worker(app,window):
    deadline=time.time()+150
    while window.worker and window.worker.isRunning() and time.time()<deadline:
        app.processEvents()
        time.sleep(.03)  # Explicitly release the GIL for the Python QThread worker.
    app.processEvents()
    assert not window.worker.isRunning(), window.status.text()
    assert window.stack.isEnabled()


def test_ui_end_to_end(app,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    window=MainWindow()
    errors=[]
    window.error=errors.append
    window.show()
    window.load_demo()
    app.processEvents()
    assert window.table.rowCount()==60
    assert window.target_combo.currentData()=="logS (mol/L)"
    window.bootstrap_spin.setValue(20)
    window.navigate(1)
    window.start_training()
    wait_worker(app,window)
    assert not errors, errors
    assert window.result is not None
    window.navigate(2)
    window.start_space()
    wait_worker(app,window)
    assert not errors,errors
    assert window.space_result["user_count"]==60
    window.navigate(3)
    window.predict_input.setText("CC(=O)Oc1ccccc1C(=O)O")
    window.start_prediction()
    wait_worker(app,window)
    assert not errors,errors
    assert window.prediction is not None
    assert len(window.prediction["nearest"])==3
    monkeypatch.setattr(QFileDialog,"getSaveFileName",lambda *a,**kw:(str(tmp_path/"project.json"),""))
    window.save_project()
    monkeypatch.setattr(QFileDialog,"getOpenFileName",lambda *a,**kw:(str(tmp_path/"project.json"),""))
    window.load_project()
    assert window.result is None
    assert len(window.frame)==60
    assert window.bootstrap_spin.value()==20
    window.table.item(0,1).setText("invalid")
    assert window.data_metrics[2].text()=="1"
    assert window.table.item(0,1).background().color().name()=="#ffe7e7"
    assert not errors,errors
    window.close()
