from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QThread, Signal, QTranslator
from PySide6.QtGui import QColor, QPixmap, QFont, QPalette
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QComboBox, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QMessageBox, QFormLayout, QListWidget, QListWidgetItem, QAbstractItemView,
    QTextBrowser, QProgressBar, QInputDialog, QScrollArea, QSizePolicy, QDialog)

from .chemistry import molecule, molecule_png, nearest
from .data import ROOT, RESOURCE, DatasetStore, read_table, detect_columns, validate_rows
from .engine import TrainingConfig, train, predict
from .space import map_space
from .plots import ScatterPlot
from .reports import export_html, export_pdf, export_tables
from .localization import annotate, feature_label, parameter_label


STYLE = """
QMainWindow, QWidget#body, QWidget#page, QWidget#viewport { background:#f8f5fc; }
QWidget { font-family:'Microsoft YaHei UI','Segoe UI'; font-size:13px; color:#4c3b60; }
QFrame#sidebar { background:#eee5f8; border:none; }
QFrame#sidebar QLabel { color:#79648d; background:transparent; }
QFrame#sidebar QPushButton { background:transparent; border:0; text-align:left; color:#725a88; padding:15px 16px; border-radius:9px; font-size:14px; }
QFrame#sidebar QPushButton:checked { background:#ddcef1; color:#623c8e; font-weight:600; }
QFrame#sidebar QPushButton:hover { background:#e5d8f3; }
QLabel#title { font-size:27px; font-weight:700; color:#49325f; }
QLabel#subtitle { color:#8a789b; font-size:13px; }
QLabel#eyebrow { color:#8a64b5; font-size:12px; font-weight:700; }
QFrame#card { background:white; border:1px solid #e8def1; border-radius:13px; }
QLabel#cardTitle { font-size:16px; font-weight:600; }
QLabel#metricValue { font-size:29px; font-weight:700; color:#8359b0; }
QLabel#muted { color:#8a789b; }
QLabel#notice { background:#f0e9f9; color:#765694; padding:12px; border-radius:8px; }
QPushButton { background:white; border:1px solid #e0d3ed; padding:9px 15px; border-radius:7px; color:#654e7e; }
QPushButton:hover { background:#f5effb; border-color:#c2a5df; }
QPushButton#primary { background:#9673c3; color:white; border:1px solid #9673c3; font-weight:600; }
QPushButton#primary:hover { background:#805bad; }
QPushButton:disabled { color:#aaa0b5; background:#f0ebf5; border-color:#e6dfee; }
QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox { background:white; border:1px solid #e0d3ed; border-radius:6px; padding:7px; min-height:19px; }
QComboBox::drop-down { border:0; width:24px; }
QComboBox QAbstractItemView { background:white; selection-background-color:#e9dcf7; }
QTableWidget { background:white; border:0; gridline-color:#f0eaf6; selection-background-color:#ecdef9; selection-color:#503466; }
QHeaderView::section { background:#faf7fd; padding:9px; border:0; border-bottom:1px solid #eee5f5; color:#887596; }
QTableCornerButton::section { background:#faf7fd; border:0; }
QTableWidget::item { padding:5px; }
QListWidget,QTextBrowser { background:white; border:1px solid #e8def1; border-radius:7px; padding:7px; }
QProgressBar { background:#e8dcf2; border:0; border-radius:3px; height:5px; }
QProgressBar::chunk { background:#a385c9; border-radius:3px; }
QToolTip { background:white; color:#58416f; border:1px solid #d4bde8; padding:8px; }
QScrollArea { border:0; background:transparent; }
QComboBox::down-arrow { image:url(ASSETS/down.svg); width:14px; height:14px; }
QSpinBox,QDoubleSpinBox { padding-right:24px; }
QSpinBox::up-button,QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:22px; background:#f6f0fb; border-top-right-radius:5px; }
QSpinBox::down-button,QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:22px; background:#f6f0fb; border-bottom-right-radius:5px; }
QSpinBox::up-arrow,QDoubleSpinBox::up-arrow { image:url(ASSETS/up.svg); width:12px; height:12px; }
QSpinBox::down-arrow,QDoubleSpinBox::down-arrow { image:url(ASSETS/down.svg); width:12px; height:12px; }
QCheckBox::indicator { width:16px; height:16px; border:1px solid #c9b1df; border-radius:3px; background:white; }
QCheckBox::indicator:checked { background:#9673c3; border-color:#9673c3; image:url(ASSETS/check.svg); }
QScrollBar:vertical { background:#f8f5fc; width:10px; margin:0; }
QScrollBar::handle:vertical { background:#d2bde6; min-height:30px; border-radius:5px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
"""
STYLE=STYLE.replace("ASSETS",(RESOURCE/"data"/"ui").as_posix())


class AnnotatedLabel(QLabel):
    def __init__(self,text="",parent=None):
        super().__init__(annotate(text),parent)
    def setText(self,text):
        super().setText(annotate(text))


class AnnotatedBrowser(QTextBrowser):
    def setHtml(self,text):
        # Annotate visible text only, preserving HTML attributes and image data URLs.
        import re
        parts=re.split(r"(<[^>]*>)",text)
        super().setHtml("".join(part if part.startswith("<") else annotate(part) for part in parts))


def label(text, name=None, wrap=False):
    obj = AnnotatedLabel(text)
    if name:
        obj.setObjectName(name)
    obj.setWordWrap(wrap)
    return obj


def button(text, callback, primary=False):
    obj = QPushButton(annotate(text))
    if primary:
        obj.setObjectName("primary")
    obj.clicked.connect(callback)
    obj.setCursor(Qt.CursorShape.PointingHandCursor)
    return obj


def card(title=None):
    box = QFrame()
    box.setObjectName("card")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(20,18,20,18)
    layout.setSpacing(13)
    if title:
        layout.addWidget(label(title,"cardTitle"))
    return box, layout


def combo(items):
    obj = QComboBox()
    for title,value in items:
        obj.addItem(annotate(title),value)
    return obj


class Worker(QThread):
    progress = Signal(str)
    success = Signal(object)
    failed = Signal(str)
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task=task
    def run(self):
        try:
            self.success.emit(self.task(self.progress.emit))
        except Exception as exc:
            logging.exception("Background operation failed")
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        QApplication.setStyle("Fusion")
        self.qt_translator=QTranslator(self)
        if self.qt_translator.load(str(RESOURCE/"data"/"ui"/"qtbase_zh_CN.qm")):
            QApplication.instance().installTranslator(self.qt_translator)
        palette=QPalette()
        for role,color in [(QPalette.ColorRole.Window,"#f8f5fc"),(QPalette.ColorRole.WindowText,"#4c3b60"),(QPalette.ColorRole.Base,"#ffffff"),(QPalette.ColorRole.AlternateBase,"#fcfaff"),(QPalette.ColorRole.Text,"#4c3b60"),(QPalette.ColorRole.Button,"#ffffff"),(QPalette.ColorRole.ButtonText,"#4c3b60"),(QPalette.ColorRole.Highlight,"#9673c3"),(QPalette.ColorRole.HighlightedText,"#ffffff"),(QPalette.ColorRole.ToolTipBase,"#ffffff"),(QPalette.ColorRole.ToolTipText,"#4c3b60")]:
            palette.setColor(role,QColor(color))
        QApplication.setPalette(palette)
        self.setWindowTitle("LQI· 轻量化化学机器学习工作台")
        self.resize(1360,900)
        self.setMinimumSize(1200,800)
        self.frame=None
        self.result=None
        self.space_result=None
        self.prediction=None
        self.worker=None
        self.loading=False
        self.source_name="尚未导入数据"
        self.store=DatasetStore()
        self.setStyleSheet(STYLE)
        outer=QWidget()
        outer.setObjectName("body")
        self.setCentralWidget(outer)
        root=QHBoxLayout(outer)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        side=QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(245)
        sl=QVBoxLayout(side)
        sl.setContentsMargins(18,30,18,22)
        logo=label("⬡  LQI")
        logo.setStyleSheet("font-size:15px;font-weight:700;color:#6d4b91;")
        sl.addWidget(logo)
        sl.addWidget(label("   连接分子与实验洞察"))
        sl.addSpacing(34)
        sl.addWidget(label("  实验工作台"))
        sl.addSpacing(10)
        self.nav=[]
        for i,title in enumerate(["01   数据与预处理", "02   模型与解释", "03   化学空间", "04   新分子预测", "05   诊断报告"]):
            b=button(title,lambda checked=False, idx=i:self.navigate(idx))
            b.setCheckable(True)
            self.nav.append(b)
            sl.addWidget(b)
        sl.addStretch()
        sl.addWidget(label("●  本地计算 · 数据留在本机"))
        sl.addSpacing(10)
        sl.addWidget(label("小样本，也有清晰的下一步。",wrap=True))
        sl.addSpacing(15)
        sl.addWidget(label("LQI  1.0.0"))
        root.addWidget(side)
        main=QVBoxLayout()
        main.setContentsMargins(30,25,30,18)
        main.setSpacing(16)
        root.addLayout(main,1)
        top=QHBoxLayout()
        top.addWidget(label("分子学习工作台","eyebrow"))
        top.addStretch()
        top.addWidget(button("使用说明",self.show_quickstart))
        top.addWidget(button("打开项目",self.load_project))
        top.addWidget(button("保存项目",self.save_project))
        main.addLayout(top)
        self.title=label("", "title")
        self.subtitle=label("", "subtitle",True)
        main.addWidget(self.title)
        main.addWidget(self.subtitle)
        self.stack=QStackedWidget()
        main.addWidget(self.stack,1)
        self.build_data()
        self.build_model()
        self.build_space()
        self.build_predict()
        self.build_report()
        self.progress=QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.hide()
        main.addWidget(self.progress)
        self.status=label("就绪  ·  导入实验数据，或加载 60 个分子的示例开始探索。","muted",True)
        main.addWidget(self.status)
        self.navigate(0)
        self.refresh_catalog()

    def page(self):
        widget=QWidget()
        widget.setObjectName("page")
        layout=QVBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(16)
        scroll=QScrollArea()
        scroll.viewport().setObjectName("viewport")
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        self.stack.addWidget(scroll)
        return layout

    def navigate(self,index):
        titles=[("数据与预处理","从一张实验表开始 · 校验分子结构，明确学习目标"), ("模型与解释","为小样本设计 · 嵌套交叉验证、模型不确定性与特征解释"), ("化学空间","把实验放入更大的分子图景 · 联合降维与结构相似性"), ("新分子预测","在下一次实验之前 · 预测属性，理解不确定性，寻找相似分子"), ("诊断报告","把结果变成可分享的证据 · 离线报告与完整分析记录")]
        self.title.setText(titles[index][0])
        self.subtitle.setText(titles[index][1])
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav): b.setChecked(i==index)

    def build_data(self):
        lay=self.page()
        row=QHBoxLayout()
        self.data_metrics=[]
        for title,value in [("数据记录","—"),("有效结构","—"),("待处理行","—")]:
            box,bl=card()
            bl.addWidget(label(title,"muted"))
            v=label(value,"metricValue")
            self.data_metrics.append(v)
            bl.addWidget(v)
            row.addWidget(box)
        lay.addLayout(row)
        box,bl=card("01 / 导入实验数据")
        r=QHBoxLayout()
        r.addWidget(button("＋ 导入 CSV / Excel",self.import_data,True))
        r.addWidget(button("加载溶解度示例 · 60 条",self.load_demo))
        r.addWidget(button("导出当前表格",self.save_data))
        r.addStretch()
        bl.addLayout(r)
        self.file_label=label("支持 CSV（逗号分隔表格）与 Excel（电子表格）；推荐 10–100 条有效观测。","muted",True)
        bl.addWidget(self.file_label)
        mapping=QHBoxLayout()
        self.smiles_combo=QComboBox()
        self.target_combo=QComboBox()
        mapping.addWidget(label("分子结构列"))
        mapping.addWidget(self.smiles_combo,1)
        mapping.addSpacing(16)
        mapping.addWidget(label("目标属性列"))
        mapping.addWidget(self.target_combo,1)
        bl.addLayout(mapping)
        self.validation_label=label("导入后自动识别列；可以手动修改。","notice",True)
        bl.addWidget(self.validation_label)
        self.table=QTableWidget()
        self.table.setMinimumHeight(250)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self.cell_changed)
        bl.addWidget(self.table,1)
        lay.addWidget(box,1)
        self.smiles_combo.currentTextChanged.connect(self.columns_changed)
        self.target_combo.currentTextChanged.connect(self.columns_changed)

    def build_model(self):
        lay=self.page()
        box,bl=card("02 / 训练设置")
        row=QHBoxLayout()
        left=QFormLayout()
        right=QFormLayout()
        self.feature_combo=combo([("化学描述符 · 24 个","descriptors"),("Morgan 指纹 · 2048 位","morgan")])
        self.model_combo=combo([(s,s) for s in ["Ridge","Lasso","Random Forest","LightGBM","XGBoost"]])
        self.missing_combo=combo([("中位数填充（特征）","median"),("均值填充（特征）","mean"),("删除特征缺失行","drop")])
        self.scale_combo=combo([("StandardScaler","standard"),("MinMaxScaler","minmax"),("不标准化","none")])
        self.bootstrap_spin=QSpinBox()
        self.bootstrap_spin.setRange(20,300)
        self.bootstrap_spin.setValue(60)
        self.bootstrap_spin.setSingleStep(20)
        self.exclude_check=QCheckBox("排除非法分子编码行（否则阻止训练）")
        left.addRow("分子特征",self.feature_combo)
        left.addRow("回归模型",self.model_combo)
        left.addRow(annotate("Bootstrap 次数"),self.bootstrap_spin)
        right.addRow("缺失处理",self.missing_combo)
        right.addRow("数据缩放",self.scale_combo)
        right.addRow(self.exclude_check)
        row.addLayout(left,1)
        row.addSpacing(22)
        row.addLayout(right,1)
        bl.addLayout(row)
        self.extra_list=QListWidget()
        self.extra_list.setMaximumHeight(80)
        bl.addWidget(label("附加数值特征（可选，例如温度、时间；勿选泄漏目标的信息）","muted",True))
        bl.addWidget(self.extra_list)
        r=QHBoxLayout()
        self.train_button=button("开始训练与交叉验证 →",self.start_training,True)
        r.addWidget(self.train_button)
        r.addWidget(label("5 折外层验证 · 折内网格搜索 · 固定随机种子 42","muted",True),1)
        bl.addLayout(r)
        lay.addWidget(box)
        self.model_notice=label("缺失目标行将排除；同一分子的重复观测不跨验证折。","notice",True)
        lay.addWidget(self.model_notice)
        row=QHBoxLayout()
        self.score_labels={}
        for name in ["R2","MAE","RMSE"]:
            b,l=card()
            l.addWidget(label(name+" / 折外评估","muted"))
            v=label("—","metricValue")
            self.score_labels[name]=v
            l.addWidget(v)
            row.addWidget(b)
        lay.addLayout(row)
        row=QHBoxLayout()
        box,bl=card("观测值与折外预测")
        self.fit_plot=ScatterPlot()
        bl.addWidget(self.fit_plot)
        row.addWidget(box,3)
        box,bl=card("SHAP（沙普利特征贡献）/ 前五项")
        self.shap_text=AnnotatedBrowser()
        self.shap_text.setMinimumHeight(230)
        self.shap_text.setHtml("<p style='color:#93819f'>完成训练后，显示对当前模型贡献最大的五个特征。</p>")
        bl.addWidget(self.shap_text)
        bl.addWidget(label("贡献不等于因果；指纹位可能包含多种子结构。","muted",True))
        row.addWidget(box,3)
        lay.addLayout(row)
        for control in [self.feature_combo,self.model_combo,self.missing_combo,self.scale_combo]: control.currentIndexChanged.connect(self.invalidate_model)
        self.bootstrap_spin.valueChanged.connect(self.invalidate_model)
        self.exclude_check.toggled.connect(self.invalidate_model)
        self.extra_list.itemChanged.connect(self.invalidate_model)

    def build_space(self):
        lay=self.page()
        box,bl=card("03 / 参考数据与空间映射")
        row=QHBoxLayout()
        self.dataset_combo=QComboBox()
        row.addWidget(self.dataset_combo,1)
        row.addWidget(button("在线更新 ESOL",self.update_dataset))
        row.addWidget(button("添加本地参考集",self.add_reference))
        bl.addLayout(row)
        self.dataset_info=label("","muted",True)
        bl.addWidget(self.dataset_info)
        row=QHBoxLayout()
        self.method_combo=combo([("PCA","PCA"),("t-SNE","t-SNE")])
        self.threshold_spin=QDoubleSpinBox()
        self.threshold_spin.setRange(.05,.95)
        self.threshold_spin.setSingleStep(.05)
        self.threshold_spin.setValue(.4)
        row.addWidget(label("降维方法"))
        row.addWidget(self.method_combo)
        row.addWidget(label("低相似度阈值"))
        row.addWidget(self.threshold_spin)
        row.addStretch()
        row.addWidget(button("生成联合化学空间 →",self.start_space,True))
        bl.addLayout(row)
        lay.addWidget(box)
        self.space_notice=label("新颖性使用原始指纹的 Tanimoto 相似度判断，二维图上的远近仅作探索参考。","notice",True)
        lay.addWidget(self.space_notice)
        box,bl=card()
        row=QHBoxLayout()
        row.addWidget(label("● 用户数据", "eyebrow"))
        a=label("● 低相似度区域")
        a.setStyleSheet("color:#c079ae")
        row.addWidget(a)
        row.addWidget(label("● 公开 / 参考数据","muted"))
        row.addStretch()
        row.addWidget(label("滚轮缩放 · 拖动平移 · 双击复位","muted"))
        bl.addLayout(row)
        self.space_plot=ScatterPlot()
        self.space_plot.setMinimumHeight(390)
        bl.addWidget(self.space_plot,1)
        lay.addWidget(box,1)
        self.dataset_combo.currentIndexChanged.connect(self.reference_changed)
        self.method_combo.currentIndexChanged.connect(self.invalidate_space)
        self.threshold_spin.valueChanged.connect(self.invalidate_space)

    def build_predict(self):
        lay=self.page()
        box,bl=card("04 / 输入新的分子结构")
        row=QHBoxLayout()
        self.predict_input=QLineEdit()
        self.predict_input.setPlaceholderText("输入 SMILES（分子线性编码），例如 CC(=O)Oc1ccccc1C(=O)O")
        row.addWidget(self.predict_input,1)
        row.addWidget(button("预测分子属性 →",self.start_prediction,True))
        bl.addLayout(row)
        self.extra_input=QLineEdit()
        self.extra_input.setPlaceholderText('有附加特征时填写 JSON（结构化数据），例如 {"温度": 80, "时间": 2}')
        bl.addWidget(self.extra_input)
        bl.addWidget(label("请先完成模型训练。预测单位与训练时的目标列保持一致。","muted",True))
        lay.addWidget(box)
        row=QHBoxLayout()
        box,bl=card("预测分子")
        self.mol_image=label("分子结构预览")
        self.mol_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mol_image.setMinimumHeight(200)
        bl.addWidget(self.mol_image)
        row.addWidget(box,1)
        box,bl=card("属性预测")
        self.pred_value=label("—","metricValue")
        self.pred_interval=label("训练后输入分子，获取估计值与模型不确定性。","muted",True)
        bl.addWidget(self.pred_value)
        bl.addWidget(self.pred_interval)
        bl.addWidget(label("95% Bootstrap 模型均值区间；不含全部实验噪声，也不保证未来观测落在其中。","notice",True))
        row.addWidget(box,2)
        lay.addLayout(row)
        box,bl=card("最相似的参考分子 / Morgan Tanimoto")
        self.similar_text=AnnotatedBrowser()
        self.similar_text.setMinimumHeight(210)
        bl.addWidget(self.similar_text)
        lay.addWidget(box,1)
        self.predict_input.textChanged.connect(self.invalidate_prediction)
        self.extra_input.textChanged.connect(self.invalidate_prediction)

    def build_report(self):
        lay=self.page()
        box,bl=card("把每一次探索，变成可复查的记录")
        bl.addWidget(label("导出拟合指标、SHAP 特征图、化学空间图和最近一次新分子预测。所有图像嵌入报告，离线也可打开。","muted",True))
        r=QHBoxLayout()
        r.addWidget(button("导出 HTML 报告",lambda:self.export_report("html"),True))
        r.addWidget(button("导出 PDF 报告",lambda:self.export_report("pdf")))
        r.addWidget(button("导出分析表格 / JSON",self.export_analysis))
        r.addStretch()
        bl.addLayout(r)
        lay.addWidget(box)
        box,bl=card("报告内容与方法边界")
        self.report_status=label("尚无训练结果。先在“模型与解释”中完成训练。","notice",True)
        bl.addWidget(self.report_status)
        text=AnnotatedBrowser()
        text.setHtml('''<h3>01　模型验证</h3><p>R²、MAE 与 RMSE 来自嵌套交叉验证的折外预测。重复分子按 canonical SMILES 分组，预处理在训练折内完成。</p><h3>02　特征解释</h3><p>导出前 5 个特征的平均绝对 SHAP 值。描述符与指纹位均可分析，SHAP 描述模型而非化学因果关系。</p><h3>03　空间覆盖</h3><p>联合 PCA / t-SNE 图叠加用户分子与参考数据。低相似度区域仅表示当前参考集覆盖不足，不能断言该分子从未被研究。</p><h3>04　预测不确定性</h3><p>按分子分组 Bootstrap 重拟合，给出 2.5%–97.5% 分位数。固定最佳超参数，区间不包含参数选择的全部不确定性，不是经校准的单次实验预测区间。</p><h3>数据留在本机</h3><p>只有点击“在线更新 ESOL”时下载公开参考数据。用户实验数据不上传。保存项目包含表格和配置，重新打开后需重训模型。</p>''')
        text.setMinimumHeight(340)
        bl.addWidget(text,1)
        lay.addWidget(box,1)

    def error(self,message):
        self.status.setText("操作未完成 · "+annotate(message))
        QMessageBox.warning(self,"LQI",annotate(message))

    def run_task(self,task,done,title):
        if self.worker and self.worker.isRunning(): return
        self.stack.setEnabled(False)
        self.progress.setRange(0,0)
        self.progress.show()
        self.status.setText(title)
        self.worker=Worker(task,self)
        self.worker.progress.connect(self.status.setText)
        self.worker.success.connect(done)
        self.worker.failed.connect(self.error)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()

    def task_finished(self):
        self.stack.setEnabled(True)
        self.progress.hide()

    def import_data(self):
        path,_=QFileDialog.getOpenFileName(self,"导入实验数据",str(ROOT),"实验数据 (*.csv *.xlsx)")
        if not path:return
        try:
            sheet=0
            if Path(path).suffix.lower()==".xlsx":
                sheets=pd.ExcelFile(path).sheet_names
                if len(sheets)>1:
                    sheet,ok=QInputDialog.getItem(self,"选择工作表","Excel（电子表格）工作表",sheets,0,False)
                    if not ok:return
            self.set_frame(read_table(path,sheet),Path(path).name)
        except Exception as exc:self.error(str(exc))

    def load_demo(self):
        try:
            raw=pd.read_csv(RESOURCE/"data"/"delaney.csv")
            sample=raw.sample(n=60,random_state=42).rename(columns={"Compound ID":"分子名称","measured log solubility in mols per litre":"logS (mol/L)"})[["分子名称","smiles","logS (mol/L)"]].reset_index(drop=True)
            self.set_frame(sample,"ESOL 随机示例 · 60 个分子")
        except Exception as exc:self.error(str(exc))

    def set_frame(self,frame,name):
        self.loading=True
        self.frame=frame.copy().astype(object)
        self.source_name=name
        self.smiles_combo.clear()
        self.target_combo.clear()
        for col in frame.columns:
            self.smiles_combo.addItem(annotate(col),col)
            self.target_combo.addItem(annotate(col),col)
        s,t,_=detect_columns(frame)
        self.smiles_combo.setCurrentIndex(self.smiles_combo.findData(s))
        if t:self.target_combo.setCurrentIndex(self.target_combo.findData(t))
        self.table.setRowCount(len(frame))
        self.table.setColumnCount(len(frame.columns))
        self.table.setHorizontalHeaderLabels([annotate(c) for c in frame.columns])
        for i,row in enumerate(frame.itertuples(index=False,name=None)):
            for j,value in enumerate(row):
                self.table.setItem(i,j,QTableWidgetItem("" if pd.isna(value) else str(value)))
        self.table.resizeColumnsToContents()
        for j in range(len(frame.columns)):self.table.setColumnWidth(j,min(360,max(130,self.table.columnWidth(j))))
        self.file_label.setText(name+f"  ·  {len(frame)} 行 × {len(frame.columns)} 列  ·  双击单元格可修正数据")
        self.loading=False
        self.columns_changed()
        self.status.setText("已加载数据 · 检查目标列后，进入模型与解释。")

    def cell_changed(self,item):
        if self.loading or self.frame is None:return
        self.frame.iat[item.row(),item.column()]=item.text() or np.nan
        self.columns_changed()

    def columns_changed(self,*args):
        if self.loading or self.frame is None:return
        s,t=self.smiles_combo.currentData(),self.target_combo.currentData()
        if not s or not t:return
        bad_s,bad_y=validate_rows(self.frame,s,t)
        self.loading=True
        for i in range(len(self.frame)):
            for j in range(len(self.frame.columns)):
                item=self.table.item(i,j)
                item.setBackground(QColor("#ffe7e7" if bad_s[i] else "#fff4df" if bad_y[i] else "#ffffff"))
                item.setToolTip("非法或空 SMILES" if bad_s[i] else "目标缺失或非数值：训练时排除" if bad_y[i] else "")
        previous={self.extra_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.extra_list.count()) if self.extra_list.item(i).checkState()==Qt.CheckState.Checked}
        self.extra_list.clear()
        for c in self.frame.columns:
            if c not in (s,t) and pd.to_numeric(self.frame[c],errors="coerce").notna().any():
                item=QListWidgetItem(annotate(c))
                item.setData(Qt.ItemDataRole.UserRole,c)
                item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if c in previous else Qt.CheckState.Unchecked)
                self.extra_list.addItem(item)
        self.loading=False
        self.extra_list.setVisible(self.extra_list.count()>0)
        for obj,value in zip(self.data_metrics,[len(self.frame),int((~bad_s).sum()),int((bad_s|bad_y).sum())]):obj.setText(str(value))
        self.validation_label.setText(f"结构校验：{bad_s.sum()} 行无效（红色）  ·  目标缺失 / 非数值：{bad_y.sum()} 行（黄色）  ·  目标值不会用均值代替。")
        self.invalidate_model()
        self.invalidate_space()

    def invalidate_model(self,*args):
        if self.loading:return
        self.result=None
        self.invalidate_prediction()
        for l in self.score_labels.values():l.setText("—")
        self.fit_plot.set_data([],"fit")
        self.shap_text.setHtml("<p>配置或数据已变更，请重新训练以生成特征解释。</p>")
        self.model_notice.setText("等待训练 · 预处理在训练折内拟合；至少 10 条观测与 6 种分子。")
        self.report_status.setText("尚无当前配置的训练结果，请先训练。")

    def invalidate_space(self,*args):
        self.space_result=None
        self.space_plot.set_data([])
        self.space_notice.setText("请生成当前数据的联合化学空间；低相似度不等于全球未知分子。")

    def invalidate_prediction(self,*args):
        self.prediction=None
        self.pred_value.setText("—")
        self.pred_interval.setText("等待新分子预测")
        self.similar_text.clear()
        self.mol_image.clear()

    def config(self):
        return TrainingConfig(smiles_col=self.smiles_combo.currentData(),target_col=self.target_combo.currentData(),mode=self.feature_combo.currentData(),model=self.model_combo.currentData(),missing=self.missing_combo.currentData(),scaling=self.scale_combo.currentData(),extra_cols=tuple(self.extra_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.extra_list.count()) if self.extra_list.item(i).checkState()==Qt.CheckState.Checked),exclude_invalid=self.exclude_check.isChecked(),bootstrap=self.bootstrap_spin.value())

    def start_training(self):
        if self.frame is None:return self.error("请先导入实验数据。")
        c=self.config()
        if c.smiles_col==c.target_col:return self.error("分子结构列与目标列不能相同。")
        frame=self.frame.copy()
        self.run_task(lambda progress:train(frame,c,progress),self.training_done,"开始训练…")

    def training_done(self,result):
        self.result=result
        self.invalidate_prediction()
        for key,obj in self.score_labels.items():obj.setText(f"{result['metrics'][key]:.3f}")
        records=[{"x":float(y),"y":float(p),"smiles":s,"name":f"训练样本 {i+1}","value":float(y)} for i,(y,p,s) in enumerate(zip(result["y"],result["oof"],result["smiles"]))]
        self.fit_plot.set_data(records,"fit")
        top=result["importance"].head(5)
        import html
        maximum=max(float(top.mean_abs_shap.max()),1e-12)
        self.shap_text.setHtml("".join(f'<p><b>{html.escape(feature_label(r.feature))}</b><br><span style="color:#9673c3">{"━"*max(1,int(r.mean_abs_shap/maximum*18))}</span> {r.mean_abs_shap:.4f}</p>' for r in top.itertuples()))
        a=result["audit"]
        self.model_notice.setText(f"训练完成 · 使用 {a['used_rows']} 行 / {a['unique_molecules']} 种分子 · 排除 {a['dropped_rows']} 行 · 参数 {parameter_label(result['best_params'])}")
        if result.get("warnings"):
            self.model_notice.setText(self.model_notice.text()+"\n存在拟合/数值警告，结果需谨慎解释；详情随报告导出。")
            self.model_notice.setToolTip("\n".join(result["warnings"]))
        self.report_status.setText(f"报告就绪 · {result['config']['model']} / {result['config']['target_col']} · {result['timestamp']}。可先生成化学空间和分子预测以补充报告。")
        self.status.setText("训练完成 · 指标为折外评估，SHAP 解释最终模型。")

    def refresh_catalog(self,selected=None):
        self.dataset_combo.blockSignals(True)
        self.dataset_combo.clear()
        for entry in self.store.catalog():self.dataset_combo.addItem(annotate(entry["name"]),entry["id"])
        if selected:self.dataset_combo.setCurrentIndex(max(0,self.dataset_combo.findData(selected)))
        self.dataset_combo.blockSignals(False)
        self.reference_changed()

    def reference_changed(self,*args):
        key=self.dataset_combo.currentData()
        if not key:return
        try:
            entry=next(e for e in self.store.catalog() if e["id"]==key)
            self.reference=self.store.load(key)
            self.reference_entry=entry
            self.dataset_info.setText(f"{len(self.reference)} 个分子 · 属性：{entry['property']} · 更新：{entry['updated']}")
            self.invalidate_space()
            self.invalidate_prediction()
        except Exception as exc:self.error(str(exc))

    def update_dataset(self):
        self.run_task(lambda progress:self.store.update_delaney(),lambda n:(self.refresh_catalog("delaney"),self.status.setText(f"ESOL 更新完成 · {n} 个分子")),"下载并校验公开数据；原有快照将在失败时保留…")

    def add_reference(self):
        path,_=QFileDialog.getOpenFileName(self,"添加参考数据集",str(ROOT),"数据表 (*.csv *.xlsx)")
        if not path:return
        try:
            frame=read_table(path)
            s,t,_=detect_columns(frame)
            s,ok=QInputDialog.getItem(self,"结构列","选择参考集 SMILES 列",list(frame.columns),list(frame.columns).index(s),False)
            if not ok:return
            t,ok=QInputDialog.getItem(self,"属性列","选择数值属性列",list(frame.columns),list(frame.columns).index(t) if t else 0,False)
            if not ok:return
            key=self.store.add_local(frame,Path(path).stem,s,t,str(path))
            self.refresh_catalog(key)
            self.status.setText("本地参考集已加入目录。")
        except Exception as exc:self.error(str(exc))

    def start_space(self):
        if self.frame is None:return self.error("请先导入实验数据。")
        frame=self.frame.copy()
        s,t=self.smiles_combo.currentData(),self.target_combo.currentData()
        ref=self.reference.copy()
        method,threshold=self.method_combo.currentData(),self.threshold_spin.value()
        entry=dict(self.reference_entry)
        def task(progress):
            result=map_space(frame,s,t,ref,method,threshold)
            result.update(reference_name=entry["name"],reference_property=entry["property"],reference_source=entry["source"])
            return result
        self.run_task(task,self.space_done,"计算 Morgan 指纹与联合降维…")

    def space_done(self,result):
        self.space_result=result
        self.space_plot.set_data(result["records"])
        self.space_notice.setText(f"{result['method']} · {result['detail']} · 用户 {result['user_count']} / 参考 {result['reference_count']} · 低相似度 {result['novel_count']} 个；阈值 {result['threshold']:.2f}")
        self.status.setText("化学空间已生成 · 悬停查看分子结构与属性。")

    def start_prediction(self):
        if self.result is None:return self.error("请先训练当前数据和配置的模型。")
        s=self.predict_input.text().strip()
        if molecule(s) is None:return self.error("请输入有效 SMILES。")
        try:
            extra=json.loads(self.extra_input.text() or "{}")
            if not isinstance(extra,dict):raise ValueError("附加特征必须是 JSON 对象。")
        except Exception as exc:return self.error(str(exc))
        result=self.result
        ref=self.reference.copy()
        self.run_task(lambda progress:(predict(result,s,extra),nearest(s,ref)),self.prediction_done,"估计分子属性和最相似参考分子…")

    def prediction_done(self,data):
        import html
        prediction,matches=data
        self.prediction=prediction
        self.prediction["nearest"]=matches
        self.prediction["reference_name"]=self.reference_entry["name"]
        self.pred_value.setText(f"{prediction['prediction']:.4f}")
        self.pred_interval.setText(f"{self.result['config']['target_col']}\n95% 模型均值区间：[{prediction['lower']:.4f}, {prediction['upper']:.4f}]\nBootstrap 重拟合 {prediction['bootstrap_count']} 次")
        pix=QPixmap()
        pix.loadFromData(molecule_png(prediction["smiles"]))
        self.mol_image.setPixmap(pix)
        from .chemistry import molecule_uri
        self.similar_text.setHtml("<p>参考属性："+html.escape(self.reference_entry["property"])+"（可能与预测目标不同）</p>"+"".join(f'<p><img width="200" src="{molecule_uri(r["smiles"])}"><br><b>{html.escape(str(r["name"]))}</b> · 相似度 {r["similarity"]:.3f}<br>参考属性 {html.escape(str(r["value"]))} · {html.escape(r["smiles"])}</p>' for r in matches))
        self.status.setText("预测完成 · 参考集相似度不代表模型训练域覆盖。")

    def export_report(self,kind):
        if self.result is None:return self.error("请先完成模型训练。")
        path,_=QFileDialog.getSaveFileName(self,"导出诊断报告",str(ROOT/f"LQI_report.{kind}"),f"报告 (*.{kind})")
        if not path:return
        if not path.lower().endswith('.'+kind):path+='.'+kind
        result,space,prediction=self.result,self.space_result,self.prediction
        exporter=export_html if kind=="html" else export_pdf
        self.run_task(lambda progress:exporter(path,result,space,prediction),lambda _:self.status.setText("报告已导出："+path),"正在生成包含内嵌图像的报告…")

    def export_analysis(self):
        if self.result is None:return self.error("请先完成模型训练。")
        folder=QFileDialog.getExistingDirectory(self,"选择分析导出位置",str(ROOT))
        if not folder:return
        try:
            path=Path(folder)/("LQI_analysis_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
            export_tables(path,self.result,self.space_result,self.prediction)
            self.status.setText("分析记录已导出："+str(path))
        except Exception as exc:self.error(str(exc))

    def save_data(self):
        if self.frame is None:return self.error("请先导入数据。")
        path,_=QFileDialog.getSaveFileName(self,"保存当前表格",str(ROOT/"experiment.csv"),"CSV（逗号分隔表格） (*.csv);;Excel（电子表格） (*.xlsx)")
        if not path:return
        try:
            if path.lower().endswith(".xlsx"):self.frame.to_excel(path,index=False)
            else:self.frame.to_csv(path,index=False,encoding="utf-8-sig")
            self.status.setText("表格已导出："+path)
        except Exception as exc:self.error(str(exc))

    def save_project(self):
        if self.frame is None:return self.error("请先导入数据。")
        path,_=QFileDialog.getSaveFileName(self,"保存项目",str(ROOT/"experiment.lqi.json"),"LQI项目 (*.json)")
        if not path:return
        try:
            from dataclasses import asdict
            payload={"format":"lqi-project-1", "name":self.source_name, "table":json.loads(self.frame.to_json(orient="split",force_ascii=False)),"config":asdict(self.config())}
            Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            self.status.setText("项目已保存 · 包含原始数据与配置，重开后重新训练。")
        except Exception as exc:self.error(str(exc))

    def load_project(self):
        if self.worker and self.worker.isRunning():return self.error("当前分析正在运行，请等待完成后打开项目。")
        path,_=QFileDialog.getOpenFileName(self,"打开项目",str(ROOT),"LQI项目 (*.json)")
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            if data.get("format") not in {"lqi-project-1", "chembridge-project-1"}:raise ValueError("不是支持的 LQI 项目。")
            table=data["table"]
            self.set_frame(pd.DataFrame(table["data"],columns=table["columns"]),data["name"])
            c=data["config"]
            self.smiles_combo.setCurrentIndex(self.smiles_combo.findData(c["smiles_col"]))
            self.target_combo.setCurrentIndex(self.target_combo.findData(c["target_col"]))
            for obj,key in [(self.feature_combo,"mode"),(self.model_combo,"model"),(self.missing_combo,"missing"),(self.scale_combo,"scaling")]:obj.setCurrentIndex(max(0,obj.findData(c[key])))
            self.bootstrap_spin.setValue(c["bootstrap"])
            self.exclude_check.setChecked(c["exclude_invalid"])
            for i in range(self.extra_list.count()):
                item=self.extra_list.item(i)
                item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in c["extra_cols"] else Qt.CheckState.Unchecked)
            self.status.setText("项目已恢复 · 请重新训练模型。")
        except Exception as exc:self.error(str(exc))

    def show_quickstart(self):
        dialog=QDialog(self)
        dialog.setWindowTitle("自带数据 · 简单使用说明")
        dialog.resize(790,720)
        layout=QVBoxLayout(dialog)
        text=QTextBrowser()
        text.setHtml((RESOURCE/"data"/"quickstart.html").read_text(encoding="utf-8"))
        layout.addWidget(text)
        close=button("明白了，开始体验",dialog.accept,True)
        layout.addWidget(close)
        dialog.exec()

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.status.setText("分析正在运行，请等待完成后关闭。")
            event.ignore()
        else:event.accept()
