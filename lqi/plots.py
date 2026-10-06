from __future__ import annotations

import html
import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QToolTip

from .chemistry import molecule_uri


class ScatterPlot(QWidget):
    """Native lightweight scatter plot with zoom, pan and molecular tooltips."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self.records = []
        self.kind = "space"
        self.bounds = (0., 1., 0., 1.)
        self.points = []
        self.drag = None

    def set_data(self, records, kind="space"):
        self.records, self.kind = records, kind
        self.reset_view()

    def reset_view(self):
        if self.records:
            x = np.array([r["x"] for r in self.records])
            y = np.array([r["y"] for r in self.records])
            dx, dy = max(np.ptp(x), .5)*.1, max(np.ptp(y), .5)*.1
            self.bounds = (float(x.min()-dx), float(x.max()+dx), float(y.min()-dy), float(y.max()+dy))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("white"))
        self.area = QRectF(62, 25, max(20,self.width()-90), max(20,self.height()-78))
        a = self.area
        p.setPen(QColor("#eee6f5"))
        for i in range(6):
            xx, yy = a.left()+i*a.width()/5, a.top()+i*a.height()/5
            p.drawLine(QPointF(xx,a.top()), QPointF(xx,a.bottom()))
            p.drawLine(QPointF(a.left(),yy), QPointF(a.right(),yy))
        xmin,xmax,ymin,ymax = self.bounds
        p.setPen(QColor("#9683a5"))
        p.drawText(QRectF(a.left(),0,a.width(),22), Qt.AlignmentFlag.AlignLeft, "折外预测 ↑" if self.kind=="fit" else "维度 2 ↑")
        for i in range(6):
            p.drawText(QRectF(a.left()+i*a.width()/5-30, a.bottom()+6, 60, 22), Qt.AlignmentFlag.AlignCenter, f"{xmin+i*(xmax-xmin)/5:.2g}")
            p.drawText(QRectF(0, a.bottom()-i*a.height()/5-10, 53, 22), Qt.AlignmentFlag.AlignRight, f"{ymin+i*(ymax-ymin)/5:.2g}")
        p.drawText(QRectF(a.left(), self.height()-26,a.width(),22), Qt.AlignmentFlag.AlignCenter, "实验观测值 →" if self.kind == "fit" else "化学空间 · 维度 1 →")
        if not self.records:
            p.setPen(QColor("#9683a5"))
            p.drawText(a, Qt.AlignmentFlag.AlignCenter, "准备好数据后，分析结果将显示在这里")
            return
        def pt(x,y):
            return QPointF(a.left()+(x-xmin)/(xmax-xmin)*a.width(), a.bottom()-(y-ymin)/(ymax-ymin)*a.height())
        p.save()
        p.setClipRect(a)
        if self.kind == "fit":
            p.setPen(QPen(QColor("#bba7ce"),1,Qt.PenStyle.DashLine))
            p.drawLine(pt(min(xmin,ymin),min(xmin,ymin)),pt(max(xmax,ymax),max(xmax,ymax)))
        self.points = []
        for r in self.records:
            q = pt(r["x"], r["y"])
            user = r.get("source") == "用户数据" or self.kind == "fit"
            p.setBrush(QColor("#c079ae" if r.get("novel") else "#a385c9" if user else "#ddd2e8"))
            p.setPen(QPen(QColor("white"), .7))
            radius = 5.5 if user else 3.5
            p.drawEllipse(q, radius, radius)
            self.points.append((q,r))
        p.restore()

    def mouseMoveEvent(self, event):
        if self.drag:
            dx,dy = event.position().x()-self.drag.x(),event.position().y()-self.drag.y()
            x0,x1,y0,y1=self.bounds
            ox,oy=dx/self.area.width()*(x1-x0),dy/self.area.height()*(y1-y0)
            self.bounds=(x0-ox,x1-ox,y0+oy,y1+oy)
            self.drag=event.position()
            self.update()
            return
        for pos,r in reversed(self.points):
            if (pos-event.position()).manhattanLength() < 12:
                text = f'<b>{html.escape(r.get("name", "分子"))}</b><br><img width="250" src="{molecule_uri(r["smiles"])}"><br>{html.escape(r["smiles"])}<br>属性：{html.escape(str(r.get("value", "")))}'
                if self.kind == "space":
                    text += f'<br>{r["source"]} · 最近相似度 {r["similarity"]:.3f}'
                else:
                    text += f'<br>折外预测：{r["y"]:.4f}'
                QToolTip.showText(event.globalPosition().toPoint(), text, self)
                return
        QToolTip.hideText()

    def wheelEvent(self, event):
        if not self.records:
            return
        factor=.85 if event.angleDelta().y()>0 else 1.18
        x0,x1,y0,y1=self.bounds
        cx,cy=(x0+x1)/2,(y0+y1)/2
        self.bounds=(cx+(x0-cx)*factor,cx+(x1-cx)*factor,cy+(y0-cy)*factor,cy+(y1-cy)*factor)
        self.update()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.drag=event.position()

    def mouseReleaseEvent(self,event):
        self.drag=None

    def mouseDoubleClickEvent(self,event):
        self.reset_view()
