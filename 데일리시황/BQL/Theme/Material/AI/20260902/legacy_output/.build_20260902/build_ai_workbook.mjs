import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const inputPath = "C:/Users/infomax/Documents/python/BQL/Theme/output/AI_Rotation/US_AI_Value_Chain_Data_20260902.json";
const outputPath = "C:/Users/infomax/Documents/python/BQL/Theme/output/AI_Rotation/US_AI_Value_Chain_Calculations_20260902.xlsx";
const previewDir = "C:/Users/infomax/Documents/python/BQL/Theme/output/AI_Rotation/.build_20260902/xlsx_preview";
const sourcePath = "C:/Users/infomax/Documents/python/BQL/Rawfile/BQuant_Master.xlsx";
const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
const wb = Workbook.create();
const summary = wb.worksheets.add("Stage_Performance");
const stocks = wb.worksheets.add("Stock_Returns");
const contrib = wb.worksheets.add("Contributors");
const method = wb.worksheets.add("Methodology");
const checks = wb.worksheets.add("Checks");
const spxProxy = data.benchmarks.SPX_cap_weight_proxy;

const navy = "#17365D", blue = "#4472C4", light = "#EAF0F8", gray = "#666666";
const green = "#008000", red = "#C00000", white = "#FFFFFF", black = "#000000", amber = "#FFF2CC";
const pctFmt = "0.0%;[Red](0.0%);-";
const priceFmt = "#,##0.00;[Red](#,##0.00);-";
const intFmt = "#,##0";

function title(sheet, range, text, subtitle) {
  sheet.getRange(range).merge();
  sheet.getRange(range).values = [[text]];
  sheet.getRange(range).format = { fill: navy, font: { bold: true, color: white, size: 16 }, rowHeight: 28, verticalAlignment: "center" };
  const subRange = range.replaceAll("1", "2");
  sheet.getRange(subRange).merge();
  sheet.getRange(subRange).values = [[subtitle]];
  sheet.getRange(subRange).format = { font: { color: gray, size: 9 }, rowHeight: 22, verticalAlignment: "center" };
}

function header(sheet, range) {
  sheet.getRange(range).format = {
    fill: blue,
    font: { bold: true, color: white, size: 9 },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
    rowHeight: 32,
    borders: { preset: "all", style: "thin", color: "#B4C6E7" },
  };
}

summary.showGridLines = false;
title(summary, "A1:K1", "US AI Value Chain - Calculation & Verification", `As of ${data.meta.asOf} | ${data.meta.members} classified / ${data.meta.validMembers} valid | daily rebalanced equal weight`);
summary.getRange("A4:K4").values = [["Rank", "Value Chain", "Valid Members", "1D", "Period 1", "Period 2", "Period 3", "3M", "3M Max Drawdown", "1D vs SPX cap-weight proxy", "Interpretation"]];
header(summary, "A4:K4");
const stages = [...data.stages].sort((a,b) => b.return1d - a.return1d);
for (let i=0; i<stages.length; i++) {
  const r = 5+i, s = stages[i];
  summary.getRange(`A${r}:C${r}`).values = [[i+1, s.name, s.members]];
  summary.getRange(`D${r}:J${r}`).values = [[s.return1d,s.month1,s.month2,s.month3,s.return3m,s.maxDrawdown3m,s.return1d-spxProxy.return1dCapWeightProxy]];
  summary.getRange(`K${r}`).values = [[s.return1d * s.return3m > 0 ? "추세 강화" : "단기 반전/반등"]];
}
summary.getRange("A5:K16").format.borders = { preset: "inside", style: "thin", color: "#D9E2F3" };
summary.getRange("A5:C16").format.font = { color: green, size: 9 };
summary.getRange("D5:J16").format = { numberFormat: pctFmt, font: { color: black, size: 9 }, horizontalAlignment: "right" };
summary.getRange("K5:K16").format = { font: { size: 9 }, horizontalAlignment: "center" };
summary.getRange("A18:K18").merge();
summary.getRange("A18:K18").values = [["[그래프 삽입 위치: 1D 단계별 수익률 막대] 핵심 메시지: AI 전체가 아니라 사이버보안·소프트웨어 중심 약세이며, 일부 인프라는 반등했다."]];
summary.getRange("A18:K18").format = { fill: amber, font: { bold: true, color: navy, size: 9 }, wrapText: true, rowHeight: 34 };
summary.getRange("A:A").format.columnWidth = 7; summary.getRange("B:B").format.columnWidth = 26; summary.getRange("C:C").format.columnWidth = 12;
summary.getRange("D:J").format.columnWidth = 13; summary.getRange("K:K").format.columnWidth = 18;
summary.freezePanes.freezeRows(4); summary.freezePanes.freezeColumns(2);

stocks.showGridLines = false;
stocks.getRange("A1:P1").values = [["Ticker", "Company", "Value Chain", "GICS Sector", "Classification", "3M Start Price", "Previous Price", "End Price", "1D", "Period 1", "Period 2", "Period 3", "3M", "3M Max Drawdown", "Classification Note", "Exclusion / Missing Note"]];
header(stocks, "A1:P1");
const sortedStocks = [...data.stocks].sort((a,b) => a.stage.localeCompare(b.stage,"ko") || a.ticker.localeCompare(b.ticker));
for (let i=0; i<sortedStocks.length; i++) {
  const r = 2+i, x = sortedStocks[i];
  stocks.getRange(`A${r}:H${r}`).values = [[x.ticker,x.name,x.stage,x.sector,x.confidence,x.price3mStart,x.pricePrev,x.priceEnd]];
  stocks.getRange(`I${r}`).formulas = [[`=IFERROR(H${r}/G${r}-1,"")`]];
  stocks.getRange(`J${r}:L${r}`).values = [[x.month1,x.month2,x.month3]];
  stocks.getRange(`M${r}`).formulas = [[`=IFERROR(H${r}/F${r}-1,"")`]];
  stocks.getRange(`N${r}:P${r}`).values = [[x.maxDrawdown3m, x.confidence === "Adjacent" ? "[ASSUMPTION] Adjacent exposure" : "Core exposure", x.exclusionReason || ""]];
}
stocks.getRange("A2:H74").format.font = { color: green, size: 9 };
stocks.getRange("F2:H74").format.numberFormat = priceFmt;
stocks.getRange("I2:N74").format = { numberFormat: pctFmt, font: { color: black, size: 9 }, horizontalAlignment: "right" };
stocks.getRange("O2:P74").format = { font: { color: gray, size: 9 }, wrapText: true };
stocks.getRange("A2:P74").format.borders = { preset: "inside", style: "thin", color: "#E7E6E6" };
stocks.getRange("A:A").format.columnWidth=10; stocks.getRange("B:B").format.columnWidth=29; stocks.getRange("C:C").format.columnWidth=25; stocks.getRange("D:D").format.columnWidth=23;
stocks.getRange("E:E").format.columnWidth=14; stocks.getRange("F:N").format.columnWidth=13; stocks.getRange("O:P").format.columnWidth=28;
stocks.freezePanes.freezeRows(1); stocks.freezePanes.freezeColumns(2);

contrib.showGridLines = false;
contrib.getRange("A1:F1").values = [["Value Chain", "Period", "Ticker", "Constituent Return", "Valid Members", "Equal-weight Contribution"]];
header(contrib, "A1:F1");
let cr = 2;
const stockRow = Object.fromEntries(sortedStocks.map((x,i)=>[x.ticker,2+i]));
for (const s of data.stages) {
  for (const [key,label,retCol] of [["top1d","1D Top","I"],["bottom1d","1D Bottom","I"],["top3m","3M Top","M"],["bottom3m","3M Bottom","M"]]) {
    for (const item of s[key]) {
      const sr = stockRow[item.ticker];
      contrib.getRange(`A${cr}:C${cr}`).values = [[s.name,label,item.ticker]];
      contrib.getRange(`D${cr}`).values = [[item.contribution*s.members]];
      contrib.getRange(`E${cr}`).values = [[s.members]];
      contrib.getRange(`F${cr}`).formulas = [[`=D${cr}/E${cr}`]];
      cr++;
    }
  }
}
contrib.getRange(`A2:C${cr-1}`).format.font = { color: green, size: 9 };
contrib.getRange(`D2:D${cr-1}`).format = { numberFormat: pctFmt, font: { color: black, size: 9 } };
contrib.getRange(`E2:E${cr-1}`).format = { numberFormat: intFmt, font: { color: black, size: 9 } };
contrib.getRange(`F2:F${cr-1}`).format = { numberFormat: pctFmt, font: { color: black, size: 9 } };
contrib.getRange(`A2:F${cr-1}`).format.borders = { preset: "inside", style: "thin", color: "#E7E6E6" };
contrib.getRange("A:A").format.columnWidth=28; contrib.getRange("B:B").format.columnWidth=14; contrib.getRange("C:C").format.columnWidth=11; contrib.getRange("D:F").format.columnWidth=19;
contrib.freezePanes.freezeRows(1); contrib.freezePanes.freezeColumns(1);

method.showGridLines = false;
title(method, "A1:B1", "Methodology, QA & Sources", "Source dates, population, missing-data treatment and direct catalyst references");
method.getRange("A4:B4").values = [["Item", "Definition / Value"]]; header(method,"A4:B4");
const notes = [
  ["Master source", sourcePath],
  ["Classification source", "C:/Users/infomax/Documents/python/BQL/Theme/AI/build_sp500_ai_value_chain.py"],
  ["As of / previous", `${data.meta.asOf} / ${data.meta.previous}`],
  ["3M start", data.meta.start3m],
  ["Monthly boundaries", data.meta.monthBoundaries.join(" / ")],
  ["Population", `${data.meta.members} classified; ${data.meta.validMembers} valid; one stage per ticker; no duplicates`],
  ["Missing values", "Require positive finite prices at each period boundary. Missing period observations are excluded from that metric; no forward-fill across the report boundary."],
  ["Equal weight", "Daily-rebalanced stage return = arithmetic mean of valid constituent price returns, compounded across sessions. Dividends excluded."],
  ["Contribution", "Constituent simple return / valid stage member count; attribution approximation."],
  ["Corporate actions", "APH 2-for-1 split distributed 2026-09-02 was checked against official IR; Master prices are split-adjusted in the final refresh."],
  ["SPX cap-weight 1D proxy", spxProxy.return1dCapWeightProxy],
  ["SPX cap-weight 3M proxy", spxProxy.return3mCapWeightProxy],
  ["DELL IR 2026-09-01", "https://investors.delltechnologies.com/"],
  ["PANW IR 2026-09-01", "https://investors.paloaltonetworks.com/news-releases/news-release-details/palo-alto-networks-reports-fiscal-fourth-quarter-and-fiscal-10"],
  ["NVDA IR 2026-08-26", "https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Second-Quarter-Fiscal-2027/default.aspx"],
  ["APH IR 2026-08-06", "https://investors.amphenol.com/news-and-events/news-details/2026/Amphenol-Announces-Two-for-One-Stock-Split-and-Third-Quarter-2026-Dividend/default.aspx"],
  ["PLTR IR 2026-08-03", "https://investors.palantir.com/news-details/2026/Palantir-Reports-"],
  ["DDOG IR 2026-08-06", "https://investors.datadoghq.com/news-releases/news-release-details/datadog-announces-second-quarter-2026-financial-results/"],
];
for (let i=0;i<notes.length;i++) method.getRange(`A${5+i}:B${5+i}`).values=[[notes[i][0],notes[i][1]]];
method.getRange("A5:A22").format = { font: { bold: true, color: navy, size: 9 }, fill: light };
method.getRange("B5:B22").format = { font: { color: green, size: 9 }, wrapText: true };
method.getRange("B15:B16").format.numberFormat = pctFmt;
method.getRange("A5:B22").format.borders = { preset:"inside", style:"thin", color:"#D9E2F3" };
method.getRange("A:A").format.columnWidth=25; method.getRange("B:B").format.columnWidth=105;

checks.showGridLines=false;
checks.getRange("A1:F1").values=[["Check","Actual","Expected","Difference","Tolerance","Status"]]; header(checks,"A1:F1");
const checkRows = [
  ["Classified members", data.meta.members, 73, "=B2-C2", 0, "=IF(ABS(D2)<=E2,\"OK\",\"FAIL\")"],
  ["Valid 1D returns", data.stocks.filter(x=>x.return1d!==null).length, data.meta.validMembers, "=B3-C3", 0, "=IF(ABS(D3)<=E3,\"OK\",\"FAIL\")"],
  ["Valid 3M returns", data.stocks.filter(x=>x.return3m!==null).length, data.meta.validMembers, "=B4-C4", 0, "=IF(ABS(D4)<=E4,\"OK\",\"FAIL\")"],
  ["Duplicate ticker assignments", data.stocks.length-new Set(data.stocks.map(x=>x.ticker)).size, 0, "=B5-C5", 0, "=IF(ABS(D5)<=E5,\"OK\",\"FAIL\")"],
  ["Stage member total", data.stages.reduce((a,x)=>a+x.members,0), data.meta.validMembers, "=B6-C6", 0, "=IF(ABS(D6)<=E6,\"OK\",\"FAIL\")"],
  ["APH final 1D split-adjusted sanity", sortedStocks.find(x=>x.ticker==="APH").return1d, 0, "=ABS(B7-C7)", 0.40, "=IF(D7<E7,\"OK\",\"FAIL\")"],
];
for(let i=0;i<checkRows.length;i++){
  const r=2+i, row=checkRows[i];
  checks.getRange(`A${r}`).values=[[row[0]]];
  if(typeof row[1] === "string" && row[1].startsWith("=")) checks.getRange(`B${r}`).formulas=[[row[1]]]; else checks.getRange(`B${r}`).values=[[row[1]]];
  checks.getRange(`C${r}`).values=[[row[2]]]; checks.getRange(`D${r}`).formulas=[[row[3]]]; checks.getRange(`E${r}`).values=[[row[4]]]; checks.getRange(`F${r}`).formulas=[[row[5]]];
}
checks.getRange("A2:A7").format.font={bold:true,color:navy,size:9}; checks.getRange("B2:F7").format.font={color:black,size:9};
checks.getRange("A2:F7").format.borders={preset:"all",style:"thin",color:"#D9E2F3"};
checks.getRange("A:A").format.columnWidth=36; checks.getRange("B:E").format.columnWidth=15; checks.getRange("F:F").format.columnWidth=12;
checks.getRange("B7:E7").format.numberFormat=pctFmt;

const out = await SpreadsheetFile.exportXlsx(wb);
await out.save(outputPath);
console.log(`OUTPUT=${outputPath}`);
