from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.formula import ArrayFormula


OUTPUT = Path(r"C:\Users\infomax\Documents\python\BQL\Europe_BQL_Rawdata_Simple_Final.xlsx")

SXXP_SECTORS = [
    "S600CSP Index", "SX3P Index", "SX4P Index", "SX6P Index", "SX7P Index",
    "SX86P Index", "SX8P Index", "SXAP Index", "SXCP Index", "SXDP Index",
    "SXEP Index", "SXFP Index", "SXIP Index", "SXKP Index", "SXMP Index",
    "SXNP Index", "SXOP Index", "SXPP Index", "SXQP Index", "SXRP Index",
    "SXTP Index",
]

SX5E_SECTORS = [
    "SX3E Index", "SX4E Index", "SX6E Index", "SX7E Index", "SX86E Index",
    "SX8E Index", "SXAE Index", "SXDE Index", "SXEE Index", "SXFE Index",
    "SXIE Index", "SXKE Index", "SXME Index", "SXNE Index", "SXOE Index",
    "SXPE Index", "SXQE Index", "SXRE Index", "SXTE Index",
]

INDEX_FIELDS = [
    ("Name", "name().value as #Name"),
    ("Market Cap", "cur_mkt_cap().value as #Market_Cap"),
    ("Price", "px_last().value as #Price"),
    ("Total Return 1Y", "total_return(calc_interval=1Y).value as #TR_1Y"),
    ("EPS FY0", "is_eps(fpt=A,fpo=0,ae=E).value as #EPS_FY0"),
    ("EPS FY1", "is_eps(fpt=A,fpo=1,ae=E).value as #EPS_FY1"),
    ("EPS FY2", "is_eps(fpt=A,fpo=2,ae=E).value as #EPS_FY2"),
    ("EPS NTM", "headline_eps_market(fpt=LTM,fpo=1,ae=E).value as #EPS_NTM"),
    ("EPS Rev 1M", "pct_chg(dropna(is_eps(fpt=A,fpo=1,ae=E,dates=range(-1M,0D)))).value as #EPS_Rev_1M"),
    ("EPS Rev 3M", "pct_chg(dropna(is_eps(fpt=A,fpo=1,ae=E,dates=range(-3M,0D)))).value as #EPS_Rev_3M"),
    ("EPS Rev 6M", "pct_chg(dropna(is_eps(fpt=A,fpo=1,ae=E,dates=range(-6M,0D)))).value as #EPS_Rev_6M"),
    ("Sales Growth Fwd", "sales_growth(fpt=LTM,fpo=1,ae=E).value as #Sales_Growth"),
    ("EBIT Growth Fwd", "pct_chg(dropna(ebit(fpt=A,fpo=range(0,1),ae=E))).value as #EBIT_Growth"),
    ("EBITDA Growth Fwd", "ebitda_growth(fpt=LTM,fpo=1,ae=E).value as #EBITDA_Growth"),
    ("EBIT Margin Fwd", "ebit_margin(fpt=LTM,fpo=1,ae=E).value as #EBIT_Margin_Fwd"),
    ("Margin Delta", "(ebit_margin(fpt=LTM,fpo=1,ae=E)-ebit_margin(fpt=LTM,fpo=0,ae=A)) as #Margin_Delta"),
    ("P/E NTM", "dropna(pe_ratio(fpt=LTM,fpo=1,ae=E)).value as #PE_NTM"),
    ("Earnings Yield", "(1/dropna(pe_ratio(fpt=LTM,fpo=1,ae=E))) as #Earnings_Yield"),
    ("P/B", "px_to_book_ratio(fpt=LTM,fpo=1,ae=E).value as #PB"),
    ("ROE Fwd", "return_com_eqy(fpt=A,fpo=1,ae=E).value as #ROE_Fwd"),
    ("FCF Yield", "free_cash_flow_yield(fpt=LTM).value as #FCF_Yield"),
    ("Dividend Yield", "headline_dvd_yield(fpt=LTM,fpo=1,ae=E).value as #Dividend_Yield"),
    ("Shareholder Yield", "shareholder_yield().value as #Shareholder_Yield"),
    ("Net Debt/EBITDA", "net_debt_to_ebitda(fpt=LTM,fpo=1,ae=E).value as #Net_Debt_EBITDA"),
]

STOCK_FIELDS = [
    ("Name", "name().value as #Name"),
    ("GICS Sector", "classification_name(gics,1) as #GICS_Sector"),
    ("Country", "country_full_name().value as #Country"),
    ("Index Weight", "id().weights as #Index_Weight"),
    ("Market Cap", "cur_mkt_cap().value as #Market_Cap"),
    ("Price", "px_last().value as #Price"),
    ("Total Return 1Y", "total_return(calc_interval=1Y).value as #TR_1Y"),
    ("EPS FY0", "is_eps(fpt=A,fpo=0,ae=E).value as #EPS_FY0"),
    ("EPS FY1", "is_eps(fpt=A,fpo=1,ae=E).value as #EPS_FY1"),
    ("EPS FY2", "is_eps(fpt=A,fpo=2,ae=E).value as #EPS_FY2"),
    ("EPS NTM", "is_eps(fpt=BT,fpo=1,ae=E).value as #EPS_NTM"),
    ("EPS Rev 1M", "pct_chg(dropna(is_eps(fpt=A,fpo=1,ae=E,dates=range(-1M,0D)))).value as #EPS_Rev_1M"),
    ("EPS Rev 3M", "pct_chg(dropna(is_eps(fpt=A,fpo=1,ae=E,dates=range(-3M,0D)))).value as #EPS_Rev_3M"),
    ("EPS Rev 6M", "pct_chg(dropna(is_eps(fpt=A,fpo=1,ae=E,dates=range(-6M,0D)))).value as #EPS_Rev_6M"),
    ("Analyst Up 4W", "contributor_revisions(is_eps(fpt=A,fpo=1,ae=E),NUMUP,4W).value as #Analyst_Up_4W"),
    ("Analyst Down 4W", "contributor_revisions(is_eps(fpt=A,fpo=1,ae=E),NUMDN,4W).value as #Analyst_Down_4W"),
    ("Sales Growth Fwd", "sales_growth(fpt=LTM,fpo=1,ae=E).value as #Sales_Growth"),
    ("EBIT Growth Fwd", "pct_chg(dropna(ebit(fpt=A,fpo=range(0,1),ae=E))).value as #EBIT_Growth"),
    ("EBITDA Growth Fwd", "ebitda_growth(fpt=LTM,fpo=1,ae=E).value as #EBITDA_Growth"),
    ("EBIT Margin Fwd", "ebit_margin(fpt=LTM,fpo=1,ae=E).value as #EBIT_Margin_Fwd"),
    ("Margin Delta", "(ebit_margin(fpt=LTM,fpo=1,ae=E)-ebit_margin(fpt=LTM,fpo=0,ae=A)) as #Margin_Delta"),
    ("P/E NTM", "pe_ratio(fpt=BT,fpo=1,ae=E).value as #PE_NTM"),
    ("Earnings Yield", "(1/pe_ratio(fpt=BT,fpo=1,ae=E)) as #Earnings_Yield"),
    ("P/B", "px_to_book_ratio(fpt=LTM,fpo=1,ae=E).value as #PB"),
    ("ROE Fwd", "return_com_eqy(fpt=A,fpo=1,ae=E).value as #ROE_Fwd"),
    ("FCF Yield", "free_cash_flow_yield(fpt=LTM).value as #FCF_Yield"),
    ("Dividend Yield", "headline_dvd_yield(fpt=LTM,fpo=1,ae=E).value as #Dividend_Yield"),
    ("Shareholder Yield", "shareholder_yield().value as #Shareholder_Yield"),
    ("Net Debt/EBITDA", "net_debt_to_ebitda(fpt=LTM,fpo=1,ae=E).value as #Net_Debt_EBITDA"),
]


NAVY = "162A46"
BLUE = "274C77"
LIGHT_BLUE = "DCE6F1"
LIGHT_GREY = "E7E9ED"
YELLOW = "FFF2CC"
ORANGE = "F4B183"
WHITE = "FFFFFF"
BLACK = "000000"
thin_grey = Side(style="thin", color="B8BEC7")


def style_cell(cell, *, fill=None, color=BLACK, bold=False, size=10, wrap=False, horizontal="left"):
    cell.font = Font(name="Arial", size=size, bold=bold, color=color)
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    cell.alignment = Alignment(vertical="center", horizontal=horizontal, wrap_text=wrap)
    cell.border = Border(left=thin_grey, right=thin_grey, top=thin_grey, bottom=thin_grey)


def add_sheet(wb, title, subtitle, ticker, universe, fields, is_stock=False, tab_color=BLUE):
    ws = wb.create_sheet(title)
    ws.sheet_properties.tabColor = tab_color
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A10"

    ws.merge_cells("A1:AZ1")
    ws["A1"] = subtitle
    style_cell(ws["A1"], fill=NAVY, color=WHITE, bold=True, size=15)
    ws.row_dimensions[1].height = 25

    ws["A2"] = "Index ticker"
    ws["B2"] = ticker
    style_cell(ws["A2"], fill=LIGHT_BLUE, bold=True)
    style_cell(ws["B2"], fill=YELLOW, bold=True)

    if is_stock:
        ws["C2"] = "Min market cap"
        ws["D2"] = 0
        style_cell(ws["C2"], fill=LIGHT_BLUE, bold=True)
        style_cell(ws["D2"], fill=YELLOW, bold=True)

    ws["A3"] = "BQL universe"
    style_cell(ws["A3"], fill=LIGHT_BLUE, bold=True)
    if is_stock:
        ws["B3"] = '="filter(members([\'"&$B$2&"\'], dates=TODAY()), cur_mkt_cap >= "&TEXT($D$2,"0")&")"'
    else:
        ws["B3"] = universe
    ws.merge_cells("B3:AZ3")
    style_cell(ws["B3"], fill=YELLOW, wrap=True)
    ws.row_dimensions[3].height = 34

    ws["A4"] = "사용법"
    style_cell(ws["A4"], fill=LIGHT_BLUE, bold=True)
    ws["B4"] = "B6:AZ6의 BQL item을 수정하면 B7이 자동 결합됩니다. A10의 BQL 한 셀만 Bloomberg에서 Refresh하면 전체 raw dataset이 spill됩니다."
    ws.merge_cells("B4:AZ4")
    style_cell(ws["B4"], fill="F7F9FC", wrap=True)
    ws.row_dimensions[4].height = 30

    ws["A5"] = "Display label"
    ws["A6"] = "BQL item"
    style_cell(ws["A5"], fill=BLUE, color=WHITE, bold=True, horizontal="center")
    style_cell(ws["A6"], fill=LIGHT_GREY, bold=True, horizontal="center")

    for col, (label, item) in enumerate(fields, start=2):
        c5 = ws.cell(5, col, label)
        c6 = ws.cell(6, col, item)
        style_cell(c5, fill=BLUE, color=WHITE, bold=True, wrap=True, horizontal="center")
        style_cell(c6, fill=LIGHT_GREY, wrap=True, size=8)
        ws.column_dimensions[get_column_letter(col)].width = max(16, min(23, len(label) + 4))
    ws.row_dimensions[5].height = 32
    ws.row_dimensions[6].height = 68

    ws["A7"] = "Joined expression"
    style_cell(ws["A7"], fill=LIGHT_BLUE, bold=True)
    field_refs = [f"{get_column_letter(col)}6" for col in range(2, 2 + len(fields))]
    ws["B7"] = "=" + '&", "&'.join(field_refs)
    ws.merge_cells("B7:AZ7")
    style_cell(ws["B7"], fill="F7F9FC", wrap=True, size=8)
    ws.row_dimensions[7].height = 40

    ws["A8"] = "Bloomberg call"
    style_cell(ws["A8"], fill=ORANGE, bold=True)
    ws["B8"] = "A10 한 셀: =BQL($B$3,$B$7)  |  BDP/BDH 없음"
    ws.merge_cells("B8:AZ8")
    style_cell(ws["B8"], fill="FCE4D6", bold=True)

    # The only Bloomberg formula on the sheet. A single-cell array record is the
    # openpyxl storage form empirically verified to open without Excel recovery.
    ws["A10"] = ArrayFormula(ref="A10", text='=_xll.BQL($B$3,$B$7)')
    for col in range(1, 53):
        style_cell(ws.cell(10, col), fill=NAVY, color=WHITE, bold=True, horizontal="center")

    ws.column_dimensions["A"].width = 20
    for col in range(len(fields) + 2, 53):
        ws.column_dimensions[get_column_letter(col)].width = 16

    ws.auto_filter.ref = "A10:AZ10"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    return ws


def build():
    wb = Workbook()
    wb.remove(wb.active)
    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True

    add_sheet(wb, "SXXP_Index", "STOXX Europe 600 — index raw data", "SXXP Index", "SXXP Index", INDEX_FIELDS, tab_color="1F4E78")
    add_sheet(wb, "SXXP_Sectors", "STOXX Europe 600 — sector raw data", "SXXP Index", ", ".join(SXXP_SECTORS), INDEX_FIELDS, tab_color="5B9BD5")
    add_sheet(wb, "SXXP_Stocks", "STOXX Europe 600 — constituent raw data", "SXXP Index", "", STOCK_FIELDS, is_stock=True, tab_color="70AD47")

    add_sheet(wb, "SX5E_Index", "EURO STOXX 50 — index raw data", "SX5E Index", "SX5E Index", INDEX_FIELDS, tab_color="1F4E78")
    add_sheet(wb, "SX5E_Sectors", "EURO STOXX 50 — sector raw data", "SX5E Index", ", ".join(SX5E_SECTORS), INDEX_FIELDS, tab_color="5B9BD5")
    add_sheet(wb, "SX5E_Stocks", "EURO STOXX 50 — constituent raw data", "SX5E Index", "", STOCK_FIELDS, is_stock=True, tab_color="70AD47")

    add_sheet(wb, "DAX_Index", "DAX 40 — index raw data", "DAX Index", "DAX Index", INDEX_FIELDS, tab_color="1F4E78")
    add_sheet(wb, "DAX_Stocks", "DAX 40 — constituent raw data", "DAX Index", "", STOCK_FIELDS, is_stock=True, tab_color="70AD47")

    wb.active = 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT)


def validate():
    wb = load_workbook(OUTPUT, data_only=False, read_only=False)
    assert len(wb.sheetnames) == 8
    assert wb.sheetnames == [
        "SXXP_Index", "SXXP_Sectors", "SXXP_Stocks", "SX5E_Index",
        "SX5E_Sectors", "SX5E_Stocks", "DAX_Index", "DAX_Stocks",
    ]
    for ws in wb.worksheets:
        bql = []
        banned = []
        for cell in ws._cells.values():
            value = cell.value
            text = getattr(value, "text", None)
            if isinstance(text, str) and "_xll.BQL" in text:
                bql.append((cell.coordinate, value.ref, text))
            formula = text if isinstance(text, str) else value if isinstance(value, str) else ""
            if "_xll.BDP" in formula or "_xll.BDH" in formula:
                banned.append((cell.coordinate, formula))
        assert bql == [("A10", "A10", "=_xll.BQL($B$3,$B$7)")], (ws.title, bql)
        assert not banned, (ws.title, banned)
        expected_refs = [f"{get_column_letter(col)}6" for col in range(2, 2 + (len(STOCK_FIELDS) if "Stocks" in ws.title else len(INDEX_FIELDS)))]
        assert ws["B7"].value == "=" + '&", "&'.join(expected_refs)

    # A data-only pass should still open cleanly even though Bloomberg has not refreshed it yet.
    data_wb = load_workbook(OUTPUT, data_only=True, read_only=False)
    assert len(data_wb.sheetnames) == 8
    print(OUTPUT)
    print("Sheets:", ", ".join(wb.sheetnames))
    print("Bloomberg calls:", len(wb.sheetnames), "(one BQL call per sheet)")
    print("BDP/BDH calls: 0")


if __name__ == "__main__":
    build()
    validate()
