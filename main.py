"""LQI desktop entry point. All user data remains local."""
import os
import sys
import logging
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MPLBACKEND", "Agg")


def main():
    import multiprocessing
    multiprocessing.freeze_support()
    if "--self-test" in sys.argv:
        from lqi.diagnostics import run
        index=sys.argv.index("--self-test")
        from lqi.data import ROOT
        return run(sys.argv[index+1] if len(sys.argv)>index+1 else ROOT/"diagnostics")
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtGui import QFont
    from lqi.data import ROOT
    logs=ROOT/"logs"
    logs.mkdir(exist_ok=True)
    logging.basicConfig(filename=str(logs/"lqi.log"),level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",encoding="utf-8")
    app=QApplication(sys.argv)
    app.setApplicationName("LQI")
    app.setFont(QFont("Microsoft YaHei UI",10))
    def exception_hook(kind,value,tb):
        logging.error("Unhandled exception",exc_info=(kind,value,tb))
        QMessageBox.critical(None,"LQI",f"操作发生错误：{value}\n详细信息已写入 logs/lqi.log。")
    sys.excepthook=exception_hook
    from lqi.ui import MainWindow
    window=MainWindow()
    if "--demo" in sys.argv:
        window.load_demo()
    window.show()
    return app.exec()


if __name__=="__main__":
    raise SystemExit(main())
