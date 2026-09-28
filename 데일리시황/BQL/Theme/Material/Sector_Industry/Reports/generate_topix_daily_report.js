const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  Header,
  HeadingLevel,
  ImageRun,
  PageBreak,
  PageOrientation,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[++i];
  }
  return out;
}

const args = parseArgs(process.argv);
if (!args.data) throw new Error("Usage: node generate_topix_daily_report.js --data <json> [--output <docx>]");

const inputPath = path.resolve(args.data);
const payload = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const market = payload.markets.find((row) => row.key === "TOPIX");
if (!market) throw new Error(`TOPIX was not found in ${inputPath}`);

const dateTag = market.asOf.replaceAll("-", "");
const outputPath = path.resolve(
  args.output || path.join(path.dirname(path.dirname(path.dirname(inputPath))), "output", dateTag, "Sector_Industry", `TOPIX_섹터_산업_1D_보고서_${dateTag}.docx`)
);
fs.mkdirSync(path.dirname(outputPath), { recursive: true });

const C = {
  navy: "17365D",
  blue: "2F75B5",
  paleBlue: "D9EAF7",
  light: "F3F6FA",
  line: "B8C5D6",
  green: "008000",
  red: "C00000",
  amber: "FFF2CC",
  gray: "666666",
  white: "FFFFFF",
  ink: "1F2937",
};

const pct = (v, digits = 2) => v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;
const pp = (v, digits = 2) => v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(digits)}%p`;
const ratio = (v) => v == null ? "—" : `${(v * 100).toFixed(1)}%`;
const fmt = (v) => Number(v).toLocaleString("ko-KR");
const retColor = (v) => v != null && v < 0 ? C.red : C.green;

function run(text, options = {}) {
  return new TextRun({ text: String(text), font: "Malgun Gothic", size: 18, color: C.ink, ...options });
}

function para(textOrRuns, options = {}) {
  const children = Array.isArray(textOrRuns) ? textOrRuns : [run(textOrRuns, options.run || {})];
  return new Paragraph({ children, spacing: { after: 100, line: 260 }, ...options });
}

function cell(text, width, options = {}) {
  const fill = options.fill || C.white;
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill },
    margins: { top: 80, bottom: 80, left: 90, right: 90 },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: C.line },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: C.line },
      left: { style: BorderStyle.SINGLE, size: 4, color: C.line },
      right: { style: BorderStyle.SINGLE, size: 4, color: C.line },
    },
    children: [new Paragraph({
      alignment: options.align || AlignmentType.LEFT,
      children: [run(text, { bold: !!options.bold, color: options.color || C.ink, size: options.size || 16 })],
    })],
  });
}

function table(headers, widths, rows) {
  const header = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => cell(h, widths[i], { fill: C.navy, color: C.white, bold: true, align: i ? AlignmentType.CENTER : AlignmentType.LEFT })),
  });
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [header, ...rows],
  });
}

function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    heading: level,
    spacing: { before: 180, after: 100 },
    children: [run(text, { bold: true, color: C.navy, size: level === HeadingLevel.HEADING_1 ? 28 : 22 })],
  });
}

function callout(title, text, fill = C.amber) {
  return new Table({
    width: { size: 15000, type: WidthType.DXA },
    columnWidths: [15000],
    rows: [new TableRow({ children: [new TableCell({
      width: { size: 15000, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill },
      margins: { top: 150, bottom: 150, left: 180, right: 180 },
      borders: {
        top: { style: BorderStyle.SINGLE, size: 6, color: C.line },
        bottom: { style: BorderStyle.SINGLE, size: 6, color: C.line },
        left: { style: BorderStyle.SINGLE, size: 6, color: C.line },
        right: { style: BorderStyle.SINGLE, size: 6, color: C.line },
      },
      children: [para([run(`${title}  `, { bold: true, color: C.navy }), run(text)])],
    })] })],
  });
}

const sectors = [...market.sectors].sort((a, b) => b.return - a.return);
const industries = [...market.industries].sort((a, b) => b.return - a.return);
const stocks = market.stocks.filter((row) => !row.excluded && row.periodReturn != null);
const topStocks = [...stocks].sort((a, b) => b.periodReturn - a.periodReturn).slice(0, 10);
const bottomStocks = [...stocks].sort((a, b) => a.periodReturn - b.periodReturn).slice(0, 10);
const up = stocks.filter((row) => row.periodReturn > 0).length;
const down = stocks.filter((row) => row.periodReturn < 0).length;
const flat = stocks.length - up - down;
const strongest = sectors[0];
const weakest = sectors[sectors.length - 1];
const positiveIndustries = industries.filter((row) => row.return > 0).length;

const children = [];
children.push(new Paragraph({
  spacing: { after: 80 },
  children: [run("TOPIX 섹터·산업 데일리", { bold: true, size: 42, color: C.navy })],
}));
children.push(para(`${market.startDate} → ${market.asOf} · 현재 구성종목 ${fmt(market.memberCount)}개 · 로컬 가격 동일가중`, { run: { color: C.gray, size: 18 } }));
children.push(callout(
  "한 줄 결론",
  `전체 평균은 ${pct(market.overall.return)}였지만 중앙값은 ${pct(market.overall.median)}, 상승 비율은 ${ratio(market.overall.breadth)}에 그쳤다. 에너지·소재·유틸리티가 방어한 반면 금융은 거의 전 종목이 하락해 시장 내부 체감은 지수 평균보다 약했다.`,
  C.paleBlue
));

children.push(heading("1. 시장 내부 요약"));
children.push(para([
  run(`TOPIX 구성종목 동일가중 수익률은 ${pct(market.overall.return)}다. `, { bold: true }),
  run(`상승 ${fmt(up)}개, 하락 ${fmt(down)}개, 보합 ${fmt(flat)}개로 상승 비율은 ${ratio(market.overall.breadth)}였다. 분산은 ${pct(market.overall.dispersion)}로, 소수 급등주가 평균을 끌어올렸지만 전형적인 종목 확산형 상승은 아니었다.`),
]));
children.push(para(`섹터 선두는 ${strongest.sector} ${pct(strongest.return)}, 최하위는 ${weakest.sector} ${pct(weakest.return)}다. 24개 산업그룹 중 상승한 그룹은 ${positiveIndustries}개뿐이었다.`));
children.push(para("핵심 차별화는 정보기술과 경기소비재 내부에서 나타났다. 정보기술은 하드웨어·반도체가 버틴 반면 소프트웨어가 약했고, 경기소비재는 자동차가 플러스였지만 유통·소매가 하락했다."));

const imagePath = market.tableImage && fs.existsSync(market.tableImage) ? market.tableImage : null;
if (imagePath) {
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 120 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(imagePath), transformation: { width: 760, height: 357 } })],
  }));
}

children.push(heading("2. 전체 섹터 스코어보드"));
const sectorWidths = [3000, 900, 1500, 1500, 1500, 1500, 1500, 1600];
children.push(table(
  ["섹터", "N", "1D 평균", "중앙값", "상승 비율", "분산", "시장 대비", "판정"],
  sectorWidths,
  sectors.map((s, i) => new TableRow({ children: [
    cell(s.sector, sectorWidths[0], { bold: true, fill: i % 2 ? C.light : C.white }),
    cell(fmt(s.members), sectorWidths[1], { align: AlignmentType.RIGHT, fill: i % 2 ? C.light : C.white }),
    cell(pct(s.return), sectorWidths[2], { align: AlignmentType.RIGHT, color: retColor(s.return), fill: i % 2 ? C.light : C.white }),
    cell(pct(s.median), sectorWidths[3], { align: AlignmentType.RIGHT, color: retColor(s.median), fill: i % 2 ? C.light : C.white }),
    cell(ratio(s.breadth), sectorWidths[4], { align: AlignmentType.RIGHT, fill: i % 2 ? C.light : C.white }),
    cell(pct(s.dispersion), sectorWidths[5], { align: AlignmentType.RIGHT, fill: i % 2 ? C.light : C.white }),
    cell(pp(s.excessVsMarket), sectorWidths[6], { align: AlignmentType.RIGHT, color: retColor(s.excessVsMarket), fill: i % 2 ? C.light : C.white }),
    cell(s.state, sectorWidths[7], { fill: i % 2 ? C.light : C.white }),
  ] }))
));

children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading("3. 산업그룹 리더와 래거드"));
const industryWidths = [3500, 2800, 1100, 1600, 1600, 1600, 1600];
children.push(table(
  ["산업그룹", "섹터", "N", "1D 평균", "중앙값", "상승 비율", "시장 대비"],
  industryWidths,
  [...industries.slice(0, 10), ...industries.slice(-10)].map((x, i) => new TableRow({ children: [
    cell(x.industry, industryWidths[0], { bold: true, fill: i % 2 ? C.light : C.white }),
    cell(x.sector, industryWidths[1], { fill: i % 2 ? C.light : C.white }),
    cell(fmt(x.members), industryWidths[2], { align: AlignmentType.RIGHT, fill: i % 2 ? C.light : C.white }),
    cell(pct(x.return), industryWidths[3], { align: AlignmentType.RIGHT, color: retColor(x.return), fill: i % 2 ? C.light : C.white }),
    cell(pct(x.median), industryWidths[4], { align: AlignmentType.RIGHT, color: retColor(x.median), fill: i % 2 ? C.light : C.white }),
    cell(ratio(x.breadth), industryWidths[5], { align: AlignmentType.RIGHT, fill: i % 2 ? C.light : C.white }),
    cell(pp(x.excessVsMarket), industryWidths[6], { align: AlignmentType.RIGHT, color: retColor(x.excessVsMarket), fill: i % 2 ? C.light : C.white }),
  ] }))
));

children.push(heading("4. 종목 상·하위"));
const stockWidths = [1200, 3000, 2400, 1000, 1200, 3000, 2400, 1000];
const stockRows = [];
for (let i = 0; i < 10; i += 1) {
  const a = topStocks[i];
  const b = bottomStocks[i];
  const fill = i % 2 ? C.light : C.white;
  stockRows.push(new TableRow({ children: [
    cell(a.ticker.split(" ")[0], stockWidths[0], { bold: true, fill }),
    cell(a.name, stockWidths[1], { fill }),
    cell(a.sector, stockWidths[2], { fill }),
    cell(pct(a.periodReturn), stockWidths[3], { align: AlignmentType.RIGHT, color: C.green, fill }),
    cell(b.ticker.split(" ")[0], stockWidths[4], { bold: true, fill }),
    cell(b.name, stockWidths[5], { fill }),
    cell(b.sector, stockWidths[6], { fill }),
    cell(pct(b.periodReturn), stockWidths[7], { align: AlignmentType.RIGHT, color: C.red, fill }),
  ] }));
}
children.push(table(["상위", "회사", "섹터", "1D", "하위", "회사", "섹터", "1D"], stockWidths, stockRows));

children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading("5. 섹터별 내부 구조"));
for (const s of sectors) {
  const sectorIndustries = market.industries.filter((x) => x.sector === s.sector).sort((a, b) => b.return - a.return);
  const topNames = (s.topGainers || []).slice(0, 3).map((x) => `${x.name} ${pct(x.periodReturn)}`).join(", ") || "—";
  const bottomNames = (s.bottomLosers || []).slice(0, 3).map((x) => `${x.name} ${pct(x.periodReturn)}`).join(", ") || "—";
  children.push(heading(`${s.rank}. ${s.sector}`, HeadingLevel.HEADING_2));
  children.push(para(`${fmt(s.validMembers)}/${fmt(s.members)}개 유효 · 평균 ${pct(s.return)} · 중앙값 ${pct(s.median)} · 상승 비율 ${ratio(s.breadth)} · 시장 대비 ${pp(s.excessVsMarket)} · ${s.state}`));
  if (sectorIndustries.length > 1) {
    children.push(para(`산업그룹은 ${sectorIndustries[0].industry} ${pct(sectorIndustries[0].return)}가 가장 강했고, ${sectorIndustries[sectorIndustries.length - 1].industry} ${pct(sectorIndustries[sectorIndustries.length - 1].return)}가 가장 약했다. 내부 스프레드는 ${pp(sectorIndustries[0].return - sectorIndustries[sectorIndustries.length - 1].return)}다.`));
  }
  children.push(para([run("상위 종목: ", { bold: true }), run(topNames), run("   |   하위 종목: ", { bold: true }), run(bottomNames)]));
}

children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading("6. 해석과 데이터 주의사항"));
children.push(callout("투자 해석", "에너지·소재·유틸리티의 동반 강세는 원자재 및 인플레이션 노출의 단기 우위를 보여준다. 반면 금융은 평균·중앙값·breadth가 모두 약해 대형주 몇 종목이 아니라 섹터 전반의 매도였다. IT 전체는 보합권이지만 하드웨어와 소프트웨어의 방향이 갈려 AI·전자부품 노출을 한 덩어리로 해석하면 안 된다."));
children.push(para(`수익률은 ${market.startDate} 종가 대비 ${market.asOf} 종가의 단순 가격수익률이다. 배당과 환율은 제외하며 현재 구성종목을 과거 시점에 소급하므로 생존편향이 있다.`));
children.push(para(`본 보고서의 TOPIX 수익률은 ${fmt(market.validMemberCount)}개 구성종목의 동일가중 평균이며 공식 TOPIX 프리플로트 시가가중 수익률이 아니다. 원천 시트 라벨은 ${market.sourceSheet} / ${market.sourceIndexLabel}이므로, 공식 지수 수준과 비교할 때 유니버스와 가중치 차이를 확인해야 한다.`));
children.push(para(`커버리지 ${ratio(market.overall.coverage)}, 기업행위 의심 제외 ${fmt(market.excludedCount)}개. 사용 세션: ${market.sessionDates.join(", ")}.`, { run: { color: C.gray, size: 16 } }));
children.push(para(`원자료: ${market.sourceWorkbook}`, { run: { color: C.gray, size: 15 } }));

const doc = new Document({
  creator: "Codex",
  title: `TOPIX 섹터·산업 1D 데일리 ${market.asOf}`,
  styles: {
    default: { document: { run: { font: "Malgun Gothic", size: 18, color: C.ink }, paragraph: { spacing: { line: 260 } } } },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838, orientation: PageOrientation.LANDSCAPE },
        margin: { top: 600, bottom: 600, left: 600, right: 600 },
      },
    },
    headers: { default: new Header({ children: [para(`TOPIX · Sector & Industry · 1D · ${market.asOf}`, { alignment: AlignmentType.RIGHT, run: { color: C.gray, size: 14 } })] }) },
    footers: { default: new Footer({ children: [para("Bloomberg BQuant 구성종목 가격 기반 · 투자 판단용 공식 지수 산출물이 아님", { alignment: AlignmentType.CENTER, run: { color: C.gray, size: 13 } })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outputPath, buffer);
  console.log(outputPath);
});
