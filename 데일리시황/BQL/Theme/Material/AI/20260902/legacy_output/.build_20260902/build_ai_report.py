from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

DATA = Path(r"C:\Users\infomax\Documents\python\BQL\Theme\output\AI_Rotation\US_AI_Value_Chain_Data_20260902.json")
OUT = Path(r"C:\Users\infomax\Documents\python\BQL\Theme\output\AI_Rotation\미국_AI_밸류체인_일간_로테이션_보고서_20260902.docx")
MASTER = r"C:\Users\infomax\Documents\python\BQL\Rawfile\BQuant_Master.xlsx"
CLASSIFICATION = r"C:\Users\infomax\Documents\python\BQL\Theme\AI\build_sp500_ai_value_chain.py"

d = json.loads(DATA.read_text(encoding="utf-8"))
stages = sorted(d["stages"], key=lambda x: x["return1d"], reverse=True)
stocks = [x for x in d["stocks"] if x.get("return1d") is not None and x.get("return3m") is not None]
top = sorted(stocks, key=lambda x: x["return1d"], reverse=True)[:5]
bottom = sorted(stocks, key=lambda x: x["return1d"])[:5]
ai_1d = sum(x["return1d"] for x in stocks) / len(stocks)
ai_3m = sum(x["return3m"] for x in stocks) / len(stocks)
spx_1d = d["benchmarks"]["SPX_cap_weight_proxy"]["return1dCapWeightProxy"]
spx_3m = d["benchmarks"]["SPX_cap_weight_proxy"]["return3mCapWeightProxy"]

NAVY = "17365D"; BLUE = "2E74B5"; DARK = "1F4D78"; LIGHT = "F2F4F7"; LINE = "D9E2F3"
WHITE = "FFFFFF"; GREEN = "15803D"; RED = "9B1C1C"; GOLD = "7A5A00"; GRAY = "666666"

def pct(v):
    return "—" if v is None else f"{v:+.1%}"

def set_font(run, name="Malgun Gothic", size=11, bold=False, color="000000", italic=False):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size); run.bold = bold; run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)

def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), fill); tc_pr.append(shd)

def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc = cell._tc; tc_pr = tc.get_or_add_tcPr(); tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None: tc_mar = OxmlElement("w:tcMar"); tc_pr.append(tc_mar)
    for m, v in (("top",top),("left",start),("bottom",bottom),("right",end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None: node = OxmlElement(f"w:{m}"); tc_mar.append(node)
        node.set(qn("w:w"), str(v)); node.set(qn("w:type"), "dxa")

def set_repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr(); tbl_header = OxmlElement("w:tblHeader"); tbl_header.set(qn("w:val"), "true"); tr_pr.append(tbl_header)

def set_table_geometry(table, widths):
    total = sum(widths); table.autofit = False; table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.first_child_found_in("w:tblW")
    if tbl_w is None: tbl_w = OxmlElement("w:tblW"); tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(total)); tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = OxmlElement("w:tblInd"); tbl_ind.set(qn("w:w"), "120"); tbl_ind.set(qn("w:type"), "dxa"); tbl_pr.append(tbl_ind)
    grid = table._tbl.tblGrid
    for child in list(grid): grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol"); col.set(qn("w:w"), str(width)); grid.append(col)
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            tc_pr = cell._tc.get_or_add_tcPr(); tc_w = tc_pr.first_child_found_in("w:tcW")
            if tc_w is None: tc_w = OxmlElement("w:tcW"); tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(width)); tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell); cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

def add_table(headers, rows, widths, sizes=None):
    table = doc.add_table(rows=1, cols=len(headers)); table.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]; shade(cell, NAVY); p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0); r = p.add_run(str(h)); set_font(r, size=8, bold=True, color=WHITE)
    set_repeat_header(table.rows[0])
    for ri, row in enumerate(rows):
        cells = table.add_row().cells
        for ci, value in enumerate(row):
            if ri % 2: shade(cells[ci], "FAFBFC")
            p = cells[ci].paragraphs[0]; p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if ci >= 2 and (sizes is None or sizes[ci] == "num") else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(value)); set_font(r, size=7.5, color="000000")
    set_table_geometry(table, widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table

def add_tagged(text, tag, after=6):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(after); p.paragraph_format.line_spacing = 1.10
    color = {"FACT":GREEN,"INFERENCE":BLUE,"ASSUMPTION":GOLD,"RISK":RED,"OPEN QUESTION":GOLD}.get(tag, NAVY)
    r = p.add_run(f"[{tag}] "); set_font(r, bold=True, color=color)
    r = p.add_run(text); set_font(r)
    return p

def add_placeholder(text):
    table = doc.add_table(rows=1, cols=1); table.style = "Table Grid"; shade(table.cell(0,0), "FFF2CC")
    p = table.cell(0,0).paragraphs[0]; p.paragraph_format.space_after = Pt(0); r = p.add_run(text); set_font(r, size=9, bold=True, color=NAVY)
    set_table_geometry(table, [9360]); doc.add_paragraph().paragraph_format.space_after = Pt(2)

doc = Document()
section = doc.sections[0]
section.page_width = Inches(8.5); section.page_height = Inches(11)
section.top_margin = Inches(1); section.bottom_margin = Inches(1); section.left_margin = Inches(1); section.right_margin = Inches(1)
section.header_distance = Inches(0.492); section.footer_distance = Inches(0.492)

styles = doc.styles
normal = styles["Normal"]; normal.font.name = "Malgun Gothic"; normal.font.size = Pt(11); normal.font.color.rgb = RGBColor(0,0,0)
normal.paragraph_format.space_after = Pt(6); normal.paragraph_format.line_spacing = 1.10
for name, size, color, before, after in (("Title",22,NAVY,0,8),("Subtitle",12,GRAY,0,12),("Heading 1",16,BLUE,16,8),("Heading 2",13,BLUE,12,6),("Heading 3",12,DARK,8,4)):
    st=styles[name]; st.font.name="Malgun Gothic"; st.font.size=Pt(size); st.font.bold=name.startswith("Heading") or name=="Title"; st.font.color.rgb=RGBColor.from_string(color)
    st.paragraph_format.space_before=Pt(before); st.paragraph_format.space_after=Pt(after); st.paragraph_format.keep_with_next=True

header = section.header.paragraphs[0]; header.alignment = WD_ALIGN_PARAGRAPH.LEFT
r=header.add_run("기관투자가용 | 미국 AI 밸류체인 일간 로테이션"); set_font(r,size=8,color=GRAY)
footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
r=footer.add_run("기준일 2026-09-02  |  "); set_font(r,size=8,color=GRAY)
fld=OxmlElement("w:fldSimple"); fld.set(qn("w:instr"),"PAGE"); footer._p.append(fld)

p=doc.add_paragraph(style="Title"); p.add_run("미국 AI 밸류체인 일간 로테이션 보고서")
p=doc.add_paragraph(style="Subtitle"); p.add_run("최근 1일을 먼저 읽고, 3개월 누적·구간별 흐름·낙폭·기여도를 함께 점검")
meta = [("기준일", d["meta"]["asOf"]),("직전 거래일",d["meta"]["previous"]),("3개월 시작",d["meta"]["start3m"]),("유니버스",f"분류 {d['meta']['members']}개 / 유효 {d['meta']['validMembers']}개")]
add_table(["항목","값","항목","값"], [[meta[0][0],meta[0][1],meta[1][0],meta[1][1]],[meta[2][0],meta[2][1],meta[3][0],meta[3][1]]], [1400,2600,1400,3960])

doc.add_heading("1. 오늘의 판단", level=1)
add_tagged(f"AI 분류 종목 동일가중은 1일 {pct(ai_1d)}로 SPX 시가총액가중 구성종목 프록시 {pct(spx_1d)}를 {pct(ai_1d-spx_1d)}p 하회했다.","FACT")
add_tagged(f"판정: 추세 강화. 3개월 AI 종목 동일가중 {pct(ai_3m)}와 같은 방향의 일간 약세이며, 소프트웨어·사이버보안 하락이 단기 언더퍼포먼스를 주도했다.","INFERENCE")
add_tagged("다만 하이퍼스케일러·AI 연산·전력·엣지는 1일 플러스여서 AI 전면 이탈보다 내부 로테이션 성격이 강하다.","INFERENCE")
add_placeholder("[그래프 삽입 위치: 1D 단계별 수익률 막대] 핵심 메시지: 방어적 인프라 반등과 소프트웨어·사이버보안 약세가 동시에 나타났다.")

doc.add_heading("2. 최근 1일: 단계별 로테이션", level=1)
stage_rows=[[s["name"],s["members"],pct(s["return1d"]),pct(s["breadth1d"]),pct(s["return1d"]-spx_1d)] for s in stages]
add_table(["밸류체인 단계","N","1D","상승 종목 비중","SPX 시총가중 대비"],stage_rows,[3500,700,1500,1700,1960], ["txt","num","num","num","num"])
add_tagged(f"상위 단계는 {stages[0]['name']} {pct(stages[0]['return1d'])}, {stages[1]['name']} {pct(stages[1]['return1d'])}; 하위는 {stages[-1]['name']} {pct(stages[-1]['return1d'])}, {stages[-2]['name']} {pct(stages[-2]['return1d'])}였다.","FACT")

doc.add_heading("3. 핵심 종목과 직접 촉매", level=1)
catalysts = {
    "DELL": "[FACT] 2026-09-01 FY2027 2Q 실적 발표. AI 주문·AI 서버 매출 확대가 직접 확인됐다. URL: https://investors.delltechnologies.com/",
    "NVDA": "[FACT] 당일 신규 공식 발표는 확인되지 않았다. 최근 공식 기준점은 2026-08-26 FY2027 2Q 실적(매출 962억달러, 데이터센터 890억달러)이다. URL: https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Second-Quarter-Fiscal-2027/default.aspx",
    "PANW": "[FACT] 2026-09-01 FY2026 4Q 실적 발표 직후 거래일이다. 매출·NGS ARR·RPO 성장과 FY2027 전망이 공개됐다. URL: https://investors.paloaltonetworks.com/news-releases/news-release-details/palo-alto-networks-reports-fiscal-fourth-quarter-and-fiscal-10",
    "PLTR": "[OPEN QUESTION] 2026-09-02 이전 동일 날짜의 신규 IR/SEC 직접 촉매를 확인하지 못했다. 최근 실적은 2026-08-03이다. URL: https://investors.palantir.com/news-details/2026/Palantir-Reports-",
    "DDOG": "[OPEN QUESTION] 2026-09-02 이전 동일 날짜의 신규 IR/SEC 직접 촉매를 확인하지 못했다. 최근 실적은 2026-08-06이다. URL: https://investors.datadoghq.com/news-releases/news-release-details/datadog-announces-second-quarter-2026-financial-results/",
}
mover_rows=[]
for label, items in (("상승",top),("하락",bottom)):
    for x in items:
        note=catalysts.get(x["ticker"],"[INFERENCE] 직접 촉매 확인 불가; 업종 동행성 또는 수급 영향 가능성.")
        mover_rows.append([label,x["ticker"],x["stage"],pct(x["return1d"]),pct(x["return3m"]),note])
add_table(["구분","티커","단계","1D","3M","공식 촉매·판정"],mover_rows,[700,700,1800,900,900,4360],["txt","txt","txt","num","num","txt"])
add_tagged("PANW 하락은 강한 헤드라인 수치 자체보다 기대치·인수통합·가이던스 소화가 영향을 줬을 가능성이 있으나, 가격 반응의 단일 원인으로 단정하지 않는다.","INFERENCE")

doc.add_heading("4. 3개월 추세, 구간 변화와 낙폭", level=1)
stage_3m=sorted(d["stages"],key=lambda x:x["return3m"],reverse=True)
rows=[[s["name"],s["members"],pct(s["month1"]),pct(s["month2"]),pct(s["month3"]),pct(s["return3m"]),pct(s["maxDrawdown3m"])] for s in stage_3m]
add_table(["밸류체인 단계","N","구간 1","구간 2","구간 3","3M","MDD"],rows,[3000,600,1100,1100,1100,1230,1230],["txt","num","num","num","num","num","num"])
add_tagged(f"3개월 수익률은 {stage_3m[0]['name']} {pct(stage_3m[0]['return3m'])}가 유일한 뚜렷한 플러스였고, {stage_3m[-1]['name']} {pct(stage_3m[-1]['return3m'])}가 최하위였다.","FACT")
add_tagged("구간 3에서 소프트웨어가 반등했지만 당일 다시 약세로 전환했다. 반전 확인에는 다음 실적·추정치 상향의 확산이 필요하다.","INFERENCE")
add_placeholder("[그래프 삽입 위치: 3개월 단계별 정규화 지수] 핵심 메시지: 소프트웨어 회복과 하드웨어·인프라의 누적 조정이 분리되어 있다.")
add_placeholder("[그래프 삽입 위치: 3개 월별 구간 히트맵] 핵심 메시지: 구간 3 반등이 전 단계로 확산되지 않았다.")

doc.add_heading("5. 단계별 1D·3M 기여 상하위", level=1)
contrib_rows=[]
for s in sorted(d["stages"],key=lambda x:x["name"]):
    fmt=lambda arr: ", ".join(f"{x['ticker']} {pct(x['contribution'])}" for x in arr)
    contrib_rows.append([s["name"],fmt(s["top1d"]),fmt(s["bottom1d"]),fmt(s["top3m"]),fmt(s["bottom3m"])])
add_table(["단계","1D 상위","1D 하위","3M 상위","3M 하위"],contrib_rows,[2200,1790,1790,1790,1790])

doc.add_heading("6. 방법론·검산·리스크", level=1)
add_tagged(f"기준일은 SPX 구성종목 가격이 실제로 변한 마지막 유효 거래일 {d['meta']['asOf']}이며, 직전 거래일은 {d['meta']['previous']}이다.","FACT")
add_tagged(f"월별 3개 구간 경계는 {' / '.join(d['meta']['monthBoundaries'])}이다. 단계 수익률은 매 거래일 유효 종목 수익률을 산술평균해 복리 연결했다.","FACT")
add_tagged(f"분류 73개, 유효 73개, 결측 제외 0개, 중복 단계 배정 0개다. Adjacent 31개는 [ASSUMPTION]으로 표시했으며 종목별 단계는 하나만 허용했다.","ASSUMPTION")
add_tagged("현재 S&P 500 구성종목을 과거로 소급하므로 생존편향·지수편입 변경 편향이 있다. 가격수익률이며 배당은 제외한다.","RISK")
add_tagged("동일가중 결과는 밸류체인 폭을 보기 위한 진단치이며, 시가총액·베타·유동성 중립 포트폴리오 성과와 다를 수 있다.","RISK")
add_tagged("APH 2대1 주식분할은 2026-08-06 공식 발표와 2026-09-02 배부일을 대조했다. 최종 Master의 분할조정 가격 기준 1D는 -3.3%로 검산됐다.","FACT")
add_tagged("소프트웨어 당일 약세가 다음 실적 시즌까지 이어지는 추세인가, 아니면 최근 반등 이후 차익실현인가?", "OPEN QUESTION")
add_tagged("PANW 실적 후 하락이 가이던스·마진·인수통합 중 어느 요인에 가장 민감했는가?", "OPEN QUESTION")

doc.add_heading("7. 출처", level=1)
sources=[
    ["가격·구성",d["meta"]["asOf"],MASTER],
    ["밸류체인 분류",d["meta"]["asOf"],CLASSIFICATION],
    ["Dell IR","2026-09-01","https://investors.delltechnologies.com/"],
    ["Palo Alto Networks IR","2026-09-01","https://investors.paloaltonetworks.com/news-releases/news-release-details/palo-alto-networks-reports-fiscal-fourth-quarter-and-fiscal-10"],
    ["NVIDIA IR","2026-08-26","https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Second-Quarter-Fiscal-2027/default.aspx"],
    ["Amphenol IR","2026-08-06","https://investors.amphenol.com/news-and-events/news-details/2026/Amphenol-Announces-Two-for-One-Stock-Split-and-Third-Quarter-2026-Dividend/default.aspx"],
    ["Palantir IR","2026-08-03","https://investors.palantir.com/news-details/2026/Palantir-Reports-"],
    ["Datadog IR","2026-08-06","https://investors.datadoghq.com/news-releases/news-release-details/datadog-announces-second-quarter-2026-financial-results/"],
]
source_table = add_table(["출처","발표일/기준일","URL 또는 로컬 경로"],sources,[1700,1500,6160])
for row in source_table.rows[1:]:
    for cell in row.cells:
        set_cell_margins(cell, top=35, start=80, bottom=35, end=80)
        for paragraph in cell.paragraphs:
            paragraph.paragraph_format.line_spacing = 0.9
            for run in paragraph.runs:
                set_font(run, size=6.5)

doc.core_properties.title = "미국 AI 밸류체인 일간 로테이션 보고서"
doc.core_properties.subject = "S&P 500 AI value-chain equal-weight rotation"
doc.core_properties.author = "OpenAI Codex"
doc.core_properties.comments = "standard_business_brief preset; Korean font override: Malgun Gothic"
OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(OUT)
