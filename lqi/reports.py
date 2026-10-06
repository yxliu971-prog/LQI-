from __future__ import annotations

import base64
import html
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
import numpy as np
import pandas as pd

from .chemistry import molecule_uri

TEAL = "#0e988b"
NAVY = "#152c44"


def chart(result, kind="fit", space=None):
    fig = Figure(figsize=(7.4, 3.9), dpi=150, facecolor="white")
    ax = fig.subplots()
    if kind == "fit":
        y, pred = result["y"], result["oof"]
        ax.scatter(y, pred, s=34, color=TEAL, alpha=.8, edgecolors="white", linewidths=.5)
        low, high = min(y.min(), pred.min()), max(y.max(), pred.max())
        ax.plot([low, high], [low, high], "--", color="#8897a8", lw=1)
        ax.set(xlabel="Observed target", ylabel="Out-of-fold prediction", title="Nested group cross-validation")
    elif kind == "shap":
        top = result["importance"].head(5).iloc[::-1]
        ax.barh(top.feature, top.mean_abs_shap, color=TEAL, height=.55)
        ax.set(xlabel="Mean absolute SHAP value", title="Top 5 feature contributions")
    else:
        for source, novel, color, label in [("公开/参考数据", False, "#bac9da", "Reference"), ("用户数据", False, TEAL, "User / covered"), ("用户数据", True, "#ec9864", "User / low similarity")]:
            records = [r for r in space["records"] if r["source"] == source and r["novel"] == novel]
            ax.scatter([r["x"] for r in records], [r["y"] for r in records], c=color, s=16 if source != "用户数据" else 42, alpha=.8, label=label)
        ax.legend(frameon=False, fontsize=8)
        ax.set(xlabel="Component 1", ylabel="Component 2", title=f"Chemical space / {space['method']}")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color("#d5dfe8")
    ax.tick_params(colors="#526479", labelsize=9)
    ax.grid(alpha=.12)
    fig.tight_layout(pad=1.5)
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=150)
    return out.getvalue()


def summary(result, space=None, prediction=None):
    return {k: result[k] for k in ("config", "metrics", "best_params", "audit", "folds", "timestamp")} | {
        "top5": result["importance"].head(5).to_dict("records"),
        "space": {k: v for k, v in space.items() if k != "records"} if space else None,
        "prediction": prediction,
        "warnings": result.get("warnings", []),
        "caveats": "OOF 为嵌套分组交叉验证结果；模型选择仍可能引入选择偏差。Bootstrap 仅估计模型均值不确定性，非校准的实验预测区间。SHAP 表示模型贡献而非因果关系。低相似度仅相对于当前参考集，不证明全球化学空间新颖性。"}


def export_html(path, result, space=None, prediction=None):
    esc = html.escape
    s = summary(result, space, prediction)
    def img(data):
        return '<img class="chart" src="data:image/png;base64,' + base64.b64encode(data).decode() + '">'
    metrics = "".join(f'<div class="metric"><small>{k}</small><strong>{v:.4f}</strong></div>' for k, v in result["metrics"].items())
    figures = '<section><h2>01 / 泛化能力</h2>' + img(chart(result)) + '</section><section><h2>02 / SHAP 特征贡献</h2>' + img(chart(result, "shap")) + result["importance"].head(5).to_html(index=False, escape=True) + '</section>'
    if space:
        figures += '<section><h2>03 / 化学空间</h2>' + img(chart(result, "space", space)) + f'<p>{esc(space["detail"])}；低相似度区域 {space["novel_count"]}/{space["user_count"]} 个用户分子，Tanimoto 阈值 {space["threshold"]:.2f}。</p><p>参考集：{esc(space.get("reference_name", "参考数据"))}；属性：{esc(space.get("reference_property", "未标注"))}</p></section>'
    if prediction:
        figures += f'<section><h2>04 / 新分子预测</h2><img width="240" src="{molecule_uri(prediction["smiles"])}"><p>{esc(prediction["smiles"])}</p><h3>{prediction["prediction"]:.4f}</h3><p>95% Bootstrap 模型均值区间 [{prediction["lower"]:.4f}, {prediction["upper"]:.4f}]</p></section>'
    content = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>LQI 诊断报告</title>
<style>body{{margin:0;background:#edf2f6;color:#172f47;font:15px/1.7 'Microsoft YaHei',sans-serif}}main{{max-width:1000px;margin:40px auto}}header{{padding:36px;background:#152c44;color:white;border-radius:18px}}header small{{color:#70d6c7}}h1{{font-size:32px}}section{{background:white;padding:26px;margin-top:20px;border-radius:16px;break-inside:avoid}}.metrics{{display:flex;gap:16px;margin-top:20px}}.metric{{flex:1;background:white;padding:22px;border-radius:14px}}strong{{display:block;font-size:30px;color:#0e988b}}.chart{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #e3e9ef}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}@media print{{body{{background:white}}main{{margin:0}}}}</style>
<main><header><small>LQI / EXPERIMENT INTELLIGENCE</small><h1>分子学习 · 诊断报告</h1><p>{esc(result['config']['target_col'])} / {esc(result['config']['model'])} / {esc(result['timestamp'])}</p></header><div class="metrics">{metrics}</div>{figures}<section><h2>方法、数据审计与边界</h2><p>{esc(s['caveats'])}</p><p>缺失目标不会被填充。预处理仅在各训练折拟合。同一 canonical SMILES 不跨折。摩根指纹位可能发生哈希碰撞，不能直接解释为唯一化学基团。</p><pre>{esc(json.dumps(s, ensure_ascii=False, indent=2))}</pre></section></main></html>'''
    Path(path).write_text(content, encoding="utf-8")


def export_pdf(path, result, space=None, prediction=None):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    normal = ParagraphStyle("body", fontName="STSong-Light", fontSize=10, leading=16, textColor=colors.HexColor(NAVY))
    heading = ParagraphStyle("heading", parent=normal, fontSize=20, leading=28, spaceAfter=14)
    sub = ParagraphStyle("sub", parent=normal, fontSize=13, leading=21, spaceBefore=8, spaceAfter=8)
    esc = html.escape
    story = []
    def p(text, style=normal):
        story.append(Paragraph(esc(str(text)), style))
    def picture(data):
        story.append(Image(io.BytesIO(data), width=480, height=253))
    p("LQI | 分子学习诊断报告", heading)
    p(f"目标：{result['config']['target_col']}    模型：{result['config']['model']}    {result['timestamp']}")
    p(f"有效观测 {result['audit']['used_rows']} / {result['audit']['input_rows']}；不同分子 {result['audit']['unique_molecules']}；特征 {result['audit']['feature_count']}")
    p("01 / 模型泛化能力", sub)
    p("    ".join(f"{k}: {v:.4f}" for k, v in result["metrics"].items()))
    picture(chart(result))
    p("指标来自 5 折嵌套分组交叉验证的折外预测；同一分子不跨折。内层最多 5 折网格搜索，按不同分子数量自适应。缺失填充和标准化仅拟合训练折。")
    p("02 / SHAP 特征贡献", sub)
    table = [["特征", "平均绝对 SHAP"]] + [[str(r.feature), f"{r.mean_abs_shap:.5f}"] for r in result["importance"].head(5).itertuples()]
    t = Table(table, colWidths=[300, 180])
    t.setStyle(TableStyle([("FONTNAME", (0,0), (-1,-1), "STSong-Light"), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e4f4f0")), ("BOTTOMPADDING", (0,0), (-1,-1), 9), ("TOPPADDING", (0,0), (-1,-1), 9), ("LINEBELOW", (0,0), (-1,-1), .3, colors.HexColor("#d9e3ec"))]))
    story.append(t)
    story.append(PageBreak())
    p("特征解释与化学空间", heading)
    picture(chart(result, "shap"))
    p("SHAP 基于最终模型的训练样本计算，用于描述该模型，不能解释为因果效应。Morgan 位为子结构哈希位，可能碰撞。")
    if space:
        p("03 / 联合化学空间映射", sub)
        picture(chart(result, "space", space))
        p(f"{space['detail']}；低相似度用户分子 {space['novel_count']}/{space['user_count']}；阈值 {space['threshold']:.2f}。")
        p(f"参考集：{space.get('reference_name', '参考数据')}；属性：{space.get('reference_property', '未标注')}。")
    story.append(PageBreak())
    p("方法记录与预测边界", heading)
    if prediction:
        p("04 / 新分子属性预测", sub)
        p(f"SMILES：{prediction['smiles']}")
        p(f"预测值 {prediction['prediction']:.4f}；95% Bootstrap 模型均值区间 [{prediction['lower']:.4f}, {prediction['upper']:.4f}]")
    p(summary(result)["caveats"])
    for warning in result.get("warnings", []):
        p("数值诊断：" + warning)
    p("训练设置", sub)
    for key, value in result["config"].items():
        p(f"{key}: {value}")
    p("最佳参数：" + json.dumps(result["best_params"], ensure_ascii=False))
    p("数据审计", sub)
    for key, value in result["audit"].items():
        if key != "source_rows":
            p(f"{key}: {value}")
    p("数据出处及许可证说明见随软件提供的 docs/DATA_SOURCES.md；参考集用于结构相似性比较，不自动加入用户训练集。")
    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(42, 24, "LQI 1.0 / Local analysis")
        canvas.drawRightString(553, 24, str(doc.page))
    SimpleDocTemplate(str(path), pagesize=(595, 842), rightMargin=48, leftMargin=48, topMargin=40, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)


def export_tables(folder, result, space=None, prediction=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    result["importance"].head(5).to_csv(folder / "top5_features.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"source_row": result["audit"]["source_rows"], "smiles": result["smiles"], "observed": result["y"], "oof_prediction": result["oof"], "residual": result["y"]-result["oof"]}).to_csv(folder / "cross_validation.csv", index=False, encoding="utf-8-sig")
    if space:
        pd.DataFrame(space["records"]).to_csv(folder / "chemical_space.csv", index=False, encoding="utf-8-sig")
    (folder / "analysis.json").write_text(json.dumps(summary(result, space, prediction), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
