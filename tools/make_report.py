"""Render the reviewed P3 Markdown report with stable ReportLab pagination.

Supported Markdown: headings, paragraphs, tables, images, emphasis, code, links.
No simulation is performed. Use the bundled document/PDF Python runtime.
"""
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
BLUE = colors.HexColor("#15384d")
TEAL = colors.HexColor("#126d78")
WIDTH = A4[0] - 84


def inline(text):
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="7.5">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return re.sub(r"\[([^]]+)\]\(([^)]+)\)", r'<link href="\2" color="#126d78">\1</link>', text)


def styles():
    body = dict(fontName="Helvetica", textColor=BLUE)
    return {
        "body": ParagraphStyle("Body", fontSize=9.3, leading=13, spaceAfter=8, **body),
        "h1": ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=24, leading=29,
                             textColor=BLUE, spaceAfter=16, keepWithNext=True),
        "h2": ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=14, leading=18,
                             textColor=TEAL, spaceBefore=15, spaceAfter=8, keepWithNext=True),
        "h3": ParagraphStyle("H3", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                             textColor=BLUE, spaceBefore=10, spaceAfter=6, keepWithNext=True),
        "cell": ParagraphStyle("Cell", fontSize=7.6, leading=10.2, **body),
        "caption": ParagraphStyle("Caption", fontSize=8, leading=10.5, spaceAfter=10, **body),
    }


def table(rows, sheet):
    count = len(rows[0])
    if any(len(row) != count for row in rows):
        raise ValueError("Inconsistent report table column count")
    if count == 2:
        fractions = [0.27, 0.73]
    elif count == 3:
        fractions = [0.24, 0.38, 0.38]
        if "Added rate" in rows[0][1]:
            fractions = [0.23, 0.18, 0.59]
    elif count == 5 and rows[0][0] == "Metric":
        fractions = [0.23, 0.12, 0.36, 0.17, 0.12]
    elif count == 5:
        fractions = [0.24, 0.12, 0.26, 0.12, 0.26]
    else:
        fractions = [1 / count] * count
    cells = [[Paragraph(("<b>" + inline(v) + "</b>") if i == 0 else inline(v), sheet["cell"])
              for v in row] for i, row in enumerate(rows)]
    result = Table(cells, colWidths=[WIDTH * f for f in fractions], repeatRows=1,
                   hAlign="LEFT", spaceBefore=4, spaceAfter=10)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5f0f2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#b4cbd2")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor("#dce5e8")),
    ]))
    return KeepTogether([result])


def paragraph(lines, start):
    values = []
    cursor = start
    while cursor < len(lines) and lines[cursor].strip():
        if lines[cursor].startswith(("#", "|", "![", "<!--")):
            break
        values.append(lines[cursor].strip())
        cursor += 1
    return " ".join(values), cursor


def flowables(source, sheet):
    lines = source.splitlines()
    result = []
    cursor = 0
    while cursor < len(lines):
        line = lines[cursor].strip()
        if not line or line.startswith("<!--"):
            cursor += 1
            continue
        if line.startswith("#"):
            match = re.fullmatch(r"(#{1,3}) (.+)", line)
            if not match:
                raise ValueError(f"Unsupported report heading: {line}")
            result.append(Paragraph(inline(match[2]), sheet[f"h{len(match[1])}"]))
            cursor += 1
        elif line.startswith("|"):
            rows = []
            while cursor < len(lines) and lines[cursor].strip().startswith("|"):
                row = lines[cursor].strip()
                if not re.fullmatch(r"\|[\s:|+\-]+\|", row):
                    rows.append([v.strip() for v in row.strip("|").split("|")])
                cursor += 1
            result.append(table(rows, sheet))
        elif line.startswith("!["):
            match = re.fullmatch(r"!\[([^]]*)\]\(([^)]+)\)", line)
            if not match:
                raise ValueError(f"Unsupported report image: {line}")
            path = (ROOT / 'docs' / match[2]).resolve()
            if not path.is_file():
                raise FileNotFoundError(path)
            picture = Image(str(path))
            scale = min(WIDTH / picture.imageWidth, 245 / picture.imageHeight)
            picture.drawWidth = picture.imageWidth * scale
            picture.drawHeight = picture.imageHeight * scale
            cursor += 1
            while cursor < len(lines) and not lines[cursor].strip():
                cursor += 1
            group = [Spacer(1, 7), picture, Spacer(1, 5)]
            if cursor < len(lines) and lines[cursor].startswith("Figure "):
                caption, cursor = paragraph(lines, cursor)
                group.append(Paragraph(inline(caption), sheet["caption"]))
            result.append(KeepTogether(group))
        else:
            value, next_cursor = paragraph(lines, cursor)
            if next_cursor == cursor:
                raise ValueError(f"Unsupported report content at line {cursor + 1}")
            result.append(Paragraph(inline(value), sheet["body"]))
            cursor = next_cursor
    return result


def footer(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(BLUE)
    canvas.drawString(42, 22, "SYNTHETIC | educational P3 | tier-B agent-produced work")
    canvas.drawRightString(A4[0] - 42, 22, str(document.page))
    canvas.restoreState()


def result_figures():
    """Python charts of saved native exports; never presented as native screenshots."""
    import json
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output=ROOT/'docs/report-figures';output.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.labelcolor':'#15384d','text.color':'#15384d'})
    colors=['#126d78','#d37535','#355c91']
    def save(fig,name):
        fig.savefig(output/name,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig)
    effects=pd.read_csv(ROOT/'results/analysis/e2-confirmation/effects.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,3.6),layout='constrained')
    for ax,metric,title in zip(axes,['mean_lead_h','p90_lead_h'],['Mean lead-time saving','Replication P90 saving']):
        data=effects[effects.metric==metric].sort_values('scenario');y=np.arange(len(data))
        ax.errorbar(data['mean'],y,xerr=[data['mean']-data.ci95_low,data.ci95_high-data['mean']],fmt='o',color=colors[0],capsize=4)
        ax.set(yticks=y,yticklabels=data.scenario_name,xlabel='Hours saved versus baseline',title=title)
        ax.axvline(0,color='#8899aa',lw=1);ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
    fig.suptitle('SYNTHETIC native E2 confirmation | n=200 paired seeds | pointwise 95% CIs',fontsize=12)
    save(fig,'fig02-e2-alternatives.png')
    source=json.loads((ROOT/'analysis/calibration/summary.json').read_text())['observed']
    observed_total=next(row for row in source if row['step']=='end_to_end')
    fig,axes=plt.subplots(1,2,figsize=(10,3.3),layout='constrained')
    for ax,metric,key,title,tolerance in zip(axes,['mean_lead_h','p90_lead_h'],['mean_h','p90_h'],['Mean lead time','P90 lead time'],[.10,.15]):
        target=observed_total[key];means=[target];lows=[target];highs=[target]
        for family in ['e1-pilot','e2-confirmation']:
            data=pd.read_csv(ROOT/f'results/analysis/{family}/summary.csv')
            row=data[(data.scenario==0)&(data.metric==metric)].iloc[0]
            means.append(row['mean']);lows.append(row.ci95_low);highs.append(row.ci95_high)
        ax.axhspan(target*(1-tolerance),target*(1+tolerance),color='#d9e9e1',alpha=.7)
        ax.bar(range(3),means,color=['#355c91','#126d78','#d37535'],width=.6)
        ax.errorbar(range(3),means,yerr=[np.array(means)-lows,np.array(highs)-means],fmt='none',ecolor='#15384d',capsize=4)
        ax.set(xticks=range(3),xticklabels=['Observed\nelapsed','E1 no-wait\nlimit','E2 assumed\ncapacity'],ylabel='Hours',title=title)
        for x,value in enumerate(means):ax.text(x,value+2,f'{value:.2f}',ha='center',fontsize=9)
    fig.suptitle('SYNTHETIC validation boundary | shaded mean/P90 accuracy bands are +/-10% / +/-15%',fontsize=11)
    save(fig,'fig01-validation-boundary.png')
    stations=pd.read_csv(ROOT/'results/analysis/e2-confirmation/stations.csv')
    stages=['Kitting','Assembly','Test','Quality','Handover'];fig,axes=plt.subplots(2,3,figsize=(12,5),layout='constrained')
    for col,(scenario,title) in enumerate([(0,'Baseline'),(2,'Assembly +1'),(3,'Test +1')]):
        data=stations[stations.scenario==scenario].groupby('stage')[['utilization','mean_queue']].mean().loc[stages]
        for row,metric,label in [(0,'utilization','Busy fraction per unit'),(1,'mean_queue','Mean waiting orders')]:
            ax=axes[row,col];ax.bar(stages,data[metric],color=colors[col]);ax.tick_params(axis='x',rotation=35)
            ax.set_ylabel(label)
            if row==0:ax.set(title=title,ylim=(0,1))
    fig.suptitle('SYNTHETIC native E2 post-cutoff state evidence | starvation fractions reported in Table 8',fontsize=12)
    save(fig,'fig03-bottleneck.png')
    grid=pd.read_csv(ROOT/'results/plans/manifold-grid.csv');points=pd.read_csv(ROOT/'results/plans/manifold-points.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,3.8),layout='constrained')
    for (ca,ct),data in grid.groupby(['cap_assembly','cap_test']):
        point=points[(points.cap_assembly==ca)&(points.cap_test==ct)].iloc[0]
        for ax in axes:
            ax.plot(data.service_scale,data.mean_lead_h,marker='o',label=f'Assembly {ca}, Test {ct}')
            ax.scatter(point.service_scale,point.target_mean_h,marker='*',s=90,color='#111827',zorder=5)
    for ax,title in zip(axes,['Full finite grid, including overloaded cases','Zoom near the observed mean']):
        ax.axhline(points.target_mean_h.iloc[0],color='#b45309',ls='--',label='Observed mean 55.4603 h')
        ax.set(xlabel='Assumed serviceScale',ylabel='Post-W500 mean lead time (h)',title=title)
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8);axes[1].set_ylim(40,80)
    fig.suptitle('SYNTHETIC native E4 grid | five seeds per point; stars are interpolated s*',fontsize=12)
    save(fig,'fig04-manifold.png')
    contrasts=pd.read_csv(ROOT/'results/manifold-summary/contrasts.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,3.6),layout='constrained')
    for ax,metric,title in zip(axes,['mean_lead_h','p90_lead_h'],['Mean advantage','P90 advantage']):
        data=contrasts[contrasts.metric==metric];y=np.arange(len(data))
        labels=[f'A{int(r.cap_assembly)} / T{int(r.cap_test)}, s={r.service_scale:.3f}'
                for r in data.itertuples()]
        ax.errorbar(data['mean'],y,xerr=[data['mean']-data.ci95_low,data.ci95_high-data['mean']],
                    fmt='o',color=colors[0],capsize=4)
        ax.axvline(0,color='#8899aa',lw=1);ax.grid(axis='x',alpha=.2)
        ax.set(yticks=y,yticklabels=labels,xlabel='Hours: positive favors Assembly +1',title=title)
        ax.invert_yaxis()
    fig.suptitle('SYNTHETIC E4 | ten paired seeds per point | pointwise 95% CIs\nApproximate mean matching: achieved baseline residuals remain in the report',fontsize=11)
    save(fig,'fig04b-manifold-contrasts.png')
    names=['capacity-low','capacity-high','service-half','service-threequarter','fitted','rework05','rework10','components']
    labels=['Low capacity','High capacity','Service x0.50','Service x0.75','Fitted marginals','Rework p=0.05','Rework p=0.10','Independent kits']
    fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
    for ax,metric,title in zip(axes,['mean_lead_h','p90_lead_h'],['Mean advantage','P90 advantage']):
        rows=[]
        for name in names:
            frame=pd.read_csv(ROOT/f'results/analysis/e5-{name}/primary.csv');rows.append(frame[frame.metric==metric].iloc[0])
        data=pd.DataFrame(rows);y=np.arange(8)
        ax.errorbar(data['mean'],y,xerr=[data['mean']-data.ci95_low,data.ci95_high-data['mean']],fmt='o',color=colors[0],capsize=3)
        ax.axvline(0,color='#8899aa',lw=1);ax.set_xscale('symlog',linthresh=.5)
        ax.set_xlim(-.6,500)
        ax.set_xticks([-.5,0,1,10,100,400],['-0.5','0','1','10','100','400'])
        ax.set(yticks=y,yticklabels=labels,xlabel='Hours: positive favors Assembly +1',title=title)
        ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
    fig.suptitle('SYNTHETIC E5 | 30 paired seeds; last 100 of 600 orders | exploratory pointwise 95% CIs\nSymmetric log scale, linear within +/-0.5 h; low-capacity cases are finite overload studies',fontsize=11)
    save(fig,'fig05-sensitivity.png')
    mmc=json.loads((ROOT/'results/analysis/e6-confirmation/acceptance.json').read_text())['mmc']['checks']
    fig,ax=plt.subplots(figsize=(9,3.5),layout='constrained')
    for i,row in enumerate(mmc):
        x=row['mean']/row['target'];low=row['ci95_low']/row['target'];high=row['ci95_high']/row['target']
        ax.errorbar(x,i,xerr=[[x-low],[high-x]],fmt='o',color=colors[0],capsize=4)
    ax.axvspan(.95,1.05,color='#d9e9e1',alpha=.7);ax.axvline(1,color='#355c91',ls='--')
    ax.set(yticks=range(len(mmc)),yticklabels=['Time in system','Wait','WIP','Queue','Throughput','Utilization'],xlabel='Native estimate / Erlang-C target',title='SYNTHETIC M/M/3 confirmation | 30 fresh seeds | marginal 95% CIs')
    ax.invert_yaxis();ax.grid(axis='x',alpha=.2);save(fig,'fig06-mmc.png')


def main():
    result_figures()
    source = ROOT / "docs/report.md"
    destination = ROOT / "model/Model-description.pdf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=42,
                                 rightMargin=42, topMargin=40, bottomMargin=40,
                                 title="P3 v2 - Sensor-module assembly and capacity",
                                 author="Agent-produced under Taim's direction")
    document.build(flowables(source.read_text(encoding="utf-8"), styles()),
                   onFirstPage=footer, onLaterPages=footer)
    from pypdf import PdfReader
    pages = len(PdfReader(destination).pages)
    if not 1 <= pages <= 25:
        raise RuntimeError(f"Unexpected report pagination: {pages}")
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(destination)
    page = pdf[0]
    bitmap = page.render(scale=1.25)
    bitmap.to_pil().save(ROOT / "results/report-preview.png")
    bitmap.close()
    page.close()
    pdf.close()
    print(f"Built {destination.name}: {pages} pages")


if __name__ == "__main__":
    main()
