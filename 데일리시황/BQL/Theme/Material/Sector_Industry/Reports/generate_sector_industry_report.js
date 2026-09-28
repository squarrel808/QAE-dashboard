"use strict";

const fs = require("fs");
const path = require("path");
const sharp = require("sharp");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  Header,
  HeadingLevel,
  ImageRun,
  PageBreak,
  PageNumber,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} = require("docx");


function parseArgs() {
  const args = {};
  for (let i = 2; i < process.argv.length; i += 1) {
    if (process.argv[i].startsWith("--")) args[process.argv[i].slice(2)] = process.argv[++i];
  }
  return args;
}


const cli = parseArgs();
if (!cli.data || !cli.market) {
  throw new Error("Usage: node generate_sector_industry_report.js --data <json> --market <STOXX600|TOPIX> [--output-dir <dir>]");
}

const inputPath = path.resolve(cli.data);
const payload = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const marketKey = String(cli.market).toUpperCase();
const market = payload.markets.find((row) => row.key === marketKey);
if (!market) throw new Error(`Market ${marketKey} not found in ${inputPath}`);

const dateTag = market.asOf.replaceAll("-", "");
const themeRoot = path.resolve(__dirname, "..", "..", "..");
const outputRoot = path.resolve(
  cli["output-dir"] || path.join(themeRoot, "output", dateTag, "Sector_Industry")
);
const outputDir = path.join(outputRoot, market.key);
fs.mkdirSync(outputDir, { recursive: true });
const outputPath = path.join(outputDir, `${market.key}_섹터_산업_5D_보고서_${dateTag}.docx`);

const C = {
  navy: "17365D",
  blue: "2F75B5",
  pale: "EAF2F8",
  line: "B4C7DC",
  gray: "666666",
  red: "C00000",
  green: "008000",
  amber: "9C6500",
  white: "FFFFFF",
  black: "111111",
  alternate: "F6F9FC",
};

const pct = (value, decimals = 1) => value == null || !Number.isFinite(value)
  ? "—"
  : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(decimals)}%`;
const pp = (value, decimals = 1) => value == null || !Number.isFinite(value)
  ? "—"
  : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(decimals)}%p`;
const ratio = (value, decimals = 0) => value == null || !Number.isFinite(value)
  ? "—"
  : `${(value * 100).toFixed(decimals)}%`;
const fmt = (value) => new Intl.NumberFormat("ko-KR").format(value);


function textRun(text, options = {}) {
  return new TextRun({
    text: String(text),
    font: "Malgun Gothic",
    size: options.size || 19,
    bold: Boolean(options.bold),
    italics: Boolean(options.italics),
    color: options.color || C.black,
  });
}


function paragraph(text, options = {}) {
  return new Paragraph({
    alignment: options.align || AlignmentType.LEFT,
    spacing: {
      before: options.before || 0,
      after: options.after == null ? 105 : options.after,
      line: options.line || 286,
    },
    keepNext: Boolean(options.keepNext),
    children: [textRun(text, options)],
  });
}


function rich(parts, options = {}) {
  return new Paragraph({
    alignment: options.align || AlignmentType.LEFT,
    spacing: {
      before: options.before || 0,
      after: options.after == null ? 100 : options.after,
      line: options.line || 286,
    },
    keepNext: Boolean(options.keepNext),
    children: parts.map((part) => textRun(part.text, part)),
  });
}


function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    text,
    heading: level,
    keepNext: true,
    spacing: { before: level === HeadingLevel.HEADING_1 ? 220 : 170, after: 100 },
  });
}


function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}


function tableCell(text, width, options = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    shading: options.fill ? { fill: options.fill, type: ShadingType.CLEAR } : undefined,
    margins: {
      top: options.pad || 75,
      bottom: options.pad || 75,
      left: 80,
      right: 80,
    },
    children: [
      new Paragraph({
        alignment: options.align || AlignmentType.LEFT,
        spacing: { before: 0, after: 0, line: 235 },
        children: [
          textRun(text, {
            size: options.size || 16,
            bold: options.bold,
            color: options.color,
          }),
        ],
      }),
    ],
  });
}


function makeTable(rows, widths) {
  return new Table({
    width: { size: widths.reduce((sum, value) => sum + value, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: C.line },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: C.line },
      left: { style: BorderStyle.SINGLE, size: 4, color: C.line },
      right: { style: BorderStyle.SINGLE, size: 4, color: C.line },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "D9D9D9" },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "D9D9D9" },
    },
  });
}


function headerRow(headers, widths, size = 15) {
  return new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: headers.map((header, idx) => tableCell(header, widths[idx], {
      fill: C.navy,
      color: C.white,
      bold: true,
      align: AlignmentType.CENTER,
      size,
    })),
  });
}


function callout(title, text) {
  return new Paragraph({
    spacing: { before: 90, after: 130, line: 286 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: C.blue } },
    shading: { fill: C.pale, type: ShadingType.CLEAR },
    indent: { left: 150, right: 90 },
    children: [
      textRun(`${title}  `, { bold: true, color: C.blue }),
      textRun(text),
    ],
  });
}


function caption(text) {
  return paragraph(text, { align: AlignmentType.CENTER, size: 15, color: C.gray, after: 150 });
}


async function imageBlock(imagePath, maxWidth = 690, maxHeight = 430) {
  if (!imagePath || !fs.existsSync(imagePath)) return [];
  const metadata = await sharp(imagePath).metadata();
  const width = metadata.width || 1800;
  const height = metadata.height || 900;
  const scale = Math.min(maxWidth / width, maxHeight / height);
  const targetWidth = Math.max(1, Math.round(width * scale));
  const targetHeight = Math.max(1, Math.round(height * scale));
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 60, after: 55 },
      children: [
        new ImageRun({
          data: fs.readFileSync(imagePath),
          type: "png",
          transformation: { width: targetWidth, height: targetHeight },
          altText: { title: path.basename(imagePath), description: path.basename(imagePath), name: path.basename(imagePath) },
        }),
      ],
    }),
  ];
}


function sectorOverviewTable() {
  const widths = [2100, 600, 700, 920, 920, 920, 920, 920, 1100];
  const headers = ["섹터", "N", "산업그룹", "5D 평균", "중앙값", "상승 비율", "분산", "시장 대비", "판정"];
  const rows = [headerRow(headers, widths, 14)];
  market.sectors.forEach((sector, idx) => {
    const fill = idx % 2 ? C.alternate : undefined;
    rows.push(new TableRow({
      cantSplit: true,
      children: [
        tableCell(sector.sector, widths[0], { size: 15, bold: true, fill }),
        tableCell(sector.validMembers, widths[1], { size: 15, align: AlignmentType.CENTER, fill }),
        tableCell(sector.industryCount, widths[2], { size: 15, align: AlignmentType.CENTER, fill }),
        tableCell(pct(sector.return5d), widths[3], { size: 15, align: AlignmentType.RIGHT, color: sector.return5d < 0 ? C.red : C.green, fill }),
        tableCell(pct(sector.median5d), widths[4], { size: 15, align: AlignmentType.RIGHT, fill }),
        tableCell(ratio(sector.breadth5d), widths[5], { size: 15, align: AlignmentType.RIGHT, fill }),
        tableCell(pct(sector.dispersion5d), widths[6], { size: 15, align: AlignmentType.RIGHT, fill }),
        tableCell(pp(sector.excessVsMarket), widths[7], { size: 15, align: AlignmentType.RIGHT, fill }),
        tableCell(sector.state, widths[8], { size: 14, align: AlignmentType.CENTER, fill }),
      ],
    }));
  });
  return makeTable(rows, widths);
}


function industryTable(sector) {
  const widths = [3000, 650, 1050, 1050, 1050, 1250];
  const headers = ["GICS Industry Group", "N", "5D 평균", "중앙값", "상승 비율", "섹터 대비"];
  const rows = [headerRow(headers, widths, 15)];
  const industries = market.industries
    .filter((row) => row.sector === sector.sector)
    .sort((a, b) => b.return5d - a.return5d);
  industries.forEach((industry, idx) => {
    const fill = idx % 2 ? C.alternate : undefined;
    rows.push(new TableRow({
      cantSplit: true,
      children: [
        tableCell(industry.industry, widths[0], { size: 16, bold: true, fill }),
        tableCell(industry.validMembers, widths[1], { size: 16, align: AlignmentType.CENTER, fill }),
        tableCell(pct(industry.return5d), widths[2], { size: 16, align: AlignmentType.RIGHT, color: industry.return5d < 0 ? C.red : C.green, fill }),
        tableCell(pct(industry.median5d), widths[3], { size: 16, align: AlignmentType.RIGHT, fill }),
        tableCell(ratio(industry.breadth5d), widths[4], { size: 16, align: AlignmentType.RIGHT, fill }),
        tableCell(pp(industry.return5d - sector.return5d), widths[5], { size: 16, align: AlignmentType.RIGHT, fill }),
      ],
    }));
  });
  return makeTable(rows, widths);
}


function stockRankingTable(sector) {
  const widths = [1500, 1050, 1430, 700, 1500, 1050, 1430, 700];
  const headers = ["상승 종목", "Ticker", "산업", "5D", "하락 종목", "Ticker", "산업", "5D"];
  const rows = [headerRow(headers, widths, 13)];
  const rowCount = Math.max(sector.topGainers.length, sector.bottomLosers.length);
  for (let idx = 0; idx < rowCount; idx += 1) {
    const top = sector.topGainers[idx];
    const bottom = sector.bottomLosers[idx];
    const fill = idx % 2 ? C.alternate : undefined;
    rows.push(new TableRow({
      cantSplit: true,
      children: [
        tableCell(top ? top.name : "", widths[0], { size: 14, bold: Boolean(top), fill }),
        tableCell(top ? top.ticker : "", widths[1], { size: 13, align: AlignmentType.CENTER, fill }),
        tableCell(top ? top.industry : "", widths[2], { size: 13, fill }),
        tableCell(top ? pct(top.return5d) : "", widths[3], { size: 14, align: AlignmentType.RIGHT, color: C.green, fill }),
        tableCell(bottom ? bottom.name : "", widths[4], { size: 14, bold: Boolean(bottom), fill }),
        tableCell(bottom ? bottom.ticker : "", widths[5], { size: 13, align: AlignmentType.CENTER, fill }),
        tableCell(bottom ? bottom.industry : "", widths[6], { size: 13, fill }),
        tableCell(bottom ? pct(bottom.return5d) : "", widths[7], { size: 14, align: AlignmentType.RIGHT, color: C.red, fill }),
      ],
    }));
  }
  return makeTable(rows, widths);
}


function sectorInterpretation(sector) {
  const broad = sector.breadth5d >= 0.5;
  const above = sector.excessVsMarket >= 0;
  const dispersion = sector.dispersion5d || 0;
  const marketDispersion = market.overall.dispersion5d || 0;
  let core;
  if (above && broad) core = "시장 대비 초과수익과 과반 상승 breadth가 함께 나타나 섹터 내부 확산이 확인된다.";
  else if (above && !broad) core = "섹터 평균은 시장을 웃돌지만 상승 종목이 과반에 못 미쳐 일부 대형 움직임에 집중됐을 가능성이 높다.";
  else if (!above && broad) core = "상승 종목은 과반이지만 평균수익률은 시장에 못 미쳐 방어적 성격의 완만한 확산에 가깝다.";
  else core = "평균수익률과 breadth가 모두 약해 섹터 전반의 매도 압력이 우세했다.";
  const dispersionText = dispersion > marketDispersion
    ? " 종목 간 수익률 분산도 시장 전체보다 커 개별 종목 선택의 영향이 컸다."
    : " 종목 간 분산은 시장 전체보다 낮아 방향성이 비교적 고르게 나타났다.";
  return core + dispersionText;
}


async function sectorDetail(sector, rank) {
  const blocks = [];
  blocks.push(pageBreak());
  blocks.push(heading(`${rank}. ${sector.sector} · ${sector.state}`));
  blocks.push(rich([
    { text: "성과  ", bold: true, color: C.blue },
    { text: `5거래일 동일가중 평균 ${pct(sector.return5d)}, 중앙값 ${pct(sector.median5d)}, 시장 대비 ${pp(sector.excessVsMarket)}다. 상승 종목 비율은 ${ratio(sector.breadth5d)}, 유효 표본은 ${fmt(sector.validMembers)}개다.` },
  ]));
  const topIndustry = sector.topIndustry;
  const bottomIndustry = sector.bottomIndustry;
  const industryStructure = sector.industryCount === 1 && topIndustry
    ? `${topIndustry.industry} 단일 산업그룹으로 구성돼 산업 간 상대비교는 하지 않는다. 해당 산업그룹의 수익률은 ${pct(topIndustry.return5d)}다.`
    : topIndustry && bottomIndustry
      ? `${sector.industryCount}개 산업그룹 중 ${topIndustry.industry}가 ${pct(topIndustry.return5d)}로 가장 강했고, ${bottomIndustry.industry}가 ${pct(bottomIndustry.return5d)}로 가장 약했다. 산업 간 스프레드는 ${pp(sector.industrySpread)}다.`
      : "유효 산업그룹 수가 부족해 산업 간 비교를 유보한다.";
  blocks.push(rich([
    { text: "산업 구조  ", bold: true, color: C.blue },
    { text: industryStructure },
  ]));
  blocks.push(rich([
    { text: "해석  ", bold: true, color: C.blue },
    { text: sectorInterpretation(sector) },
  ]));

  const chartPath = market.charts.sectorIndustries[sector.sector];
  blocks.push(...await imageBlock(chartPath, 675, 285));
  blocks.push(caption(`그림 ${rank + 3}. ${sector.sector} 산업그룹 최근 5거래일 성과`));
  blocks.push(industryTable(sector));
  blocks.push(paragraph("", { after: 40, size: 4 }));
  blocks.push(heading("상승 종목과 하락 종목", HeadingLevel.HEADING_2));
  blocks.push(paragraph(`섹터 내 유효 종목을 수익률 순으로 정렬해 상승 상위와 하락 하위를 각각 최대 ${payload.meta.topBottomLimit}개 표시했다.`, { size: 16, color: C.gray, after: 75 }));
  blocks.push(stockRankingTable(sector));
  return blocks;
}


async function buildDocument() {
  const sectors = [...market.sectors];
  const leaders = sectors.slice(0, 3);
  const laggards = sectors.slice(-3).reverse();
  const industries = market.industries.filter((row) => row.return5d != null);
  const industryLeaders = industries.slice(0, 3);
  const industryLaggards = industries.slice(-3).reverse();
  const positiveSectors = sectors.filter((row) => row.return5d > 0).length;
  const broadSectors = sectors.filter((row) => row.breadth5d >= 0.5).length;
  const widest = [...sectors].sort((a, b) => b.dispersion5d - a.dispersion5d)[0];
  const strongest = leaders[0];
  const weakest = laggards[0];
  const children = [];

  children.push(new Paragraph({
    style: "Title",
    alignment: AlignmentType.CENTER,
    spacing: { before: 1420, after: 230 },
    children: [textRun(`${market.title} 섹터와 산업`, { size: 40, bold: true, color: C.navy })],
  }));
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 210 },
    children: [textRun("최근 5거래일 로테이션과 내부 확산", { size: 28, bold: true, color: C.blue })],
  }));
  children.push(paragraph(`${market.start5d}~${market.asOf} · ${fmt(market.memberCount)}개 원천 기준 구성종목 · ${fmt(sectors.length)}개 GICS 섹터`, {
    align: AlignmentType.CENTER,
    size: 19,
    color: C.gray,
  }));
  children.push(paragraph("섹터 성과 · 산업그룹 리더십 · 섹터별 상승·하락 종목", {
    align: AlignmentType.CENTER,
    size: 17,
    color: C.gray,
    before: 90,
  }));
  children.push(pageBreak());

  children.push(heading("Executive Summary"));
  children.push(rich([
    { text: "리더십  ", bold: true, color: C.blue },
    { text: `최근 5거래일 상위 섹터는 ${leaders.map((row) => `${row.sector} ${pct(row.return5d)}`).join(", ")}다. 하위는 ${laggards.map((row) => `${row.sector} ${pct(row.return5d)}`).join(", ")}다.` },
  ]));
  children.push(rich([
    { text: "시장 폭  ", bold: true, color: C.blue },
    { text: `전체 종목 동일가중 수익률은 ${pct(market.overall.return5d)}, 상승 종목 비율은 ${ratio(market.overall.breadth5d)}다. ${sectors.length}개 섹터 중 ${positiveSectors}개가 상승했고, ${broadSectors}개는 상승 종목이 과반이었다.` },
  ]));
  children.push(rich([
    { text: "산업 회전  ", bold: true, color: C.blue },
    { text: `산업그룹 상위는 ${industryLeaders.map((row) => `${row.industry} ${pct(row.return5d)}`).join(", ")}다. 하위는 ${industryLaggards.map((row) => `${row.industry} ${pct(row.return5d)}`).join(", ")}다.` },
  ]));
  children.push(rich([
    { text: "종목 선택  ", bold: true, color: C.blue },
    { text: `${widest.sector}의 5거래일 종목 수익률 분산이 ${pct(widest.dispersion5d)}로 가장 컸다. 같은 섹터 안에서도 산업과 종목 선택의 영향이 상대적으로 큰 구간이다.` },
  ]));
  children.push(callout("발표 핵심", `${strongest.sector}의 강세가 ${ratio(strongest.breadth5d)} breadth로 뒷받침되는지, ${weakest.sector}의 약세가 특정 산업그룹에 집중됐는지를 먼저 확인한다.`));

  children.push(heading("전체 섹터 성과표"));
  children.push(sectorOverviewTable());
  children.push(paragraph("정렬 기준은 최근 5거래일 동일가중 평균 수익률이다. 분산은 섹터 내 유효 종목 수익률의 표준편차, 시장 대비는 전체 유효 종목 동일가중 수익률과의 차이다.", { size: 15, color: C.gray, after: 100 }));
  children.push(pageBreak());

  children.push(heading("섹터 로테이션"));
  children.push(...await imageBlock(market.charts.sectorReturn, 690, 430));
  children.push(caption("그림 1. 섹터별 최근 5거래일 동일가중 평균 수익률"));
  children.push(...await imageBlock(market.charts.sectorBreadth, 690, 430));
  children.push(caption("그림 2. 섹터별 상승 종목 비율"));
  children.push(pageBreak());

  children.push(heading("Key Findings"));
  children.push(rich([
    { text: "1. 상위 섹터  ", bold: true, color: C.navy },
    { text: `${strongest.sector}가 ${pct(strongest.return5d)}로 선두이며 시장 대비 ${pp(strongest.excessVsMarket)}다. 내부 상승 breadth는 ${ratio(strongest.breadth5d)}로 ${strongest.state}으로 분류된다.` },
  ]));
  children.push(rich([
    { text: "2. 하위 섹터  ", bold: true, color: C.navy },
    { text: `${weakest.sector}는 ${pct(weakest.return5d)}로 최하위이며 시장 대비 ${pp(weakest.excessVsMarket)}다. 내부 상승 breadth는 ${ratio(weakest.breadth5d)}다.` },
  ]));
  children.push(rich([
    { text: "3. 섹터 간 스프레드  ", bold: true, color: C.navy },
    { text: `선두와 최하위 섹터의 수익률 차이는 ${pp(strongest.return5d - weakest.return5d)}다. 스프레드가 크면서 breadth까지 엇갈릴수록 단기 로테이션 신호가 선명하다.` },
  ]));
  children.push(rich([
    { text: "4. 해석 순서  ", bold: true, color: C.navy },
    { text: "섹터 평균의 방향, 상승 종목 비율, 산업그룹 간 스프레드, 개별 종목의 극단값 순으로 확인한다. 평균만 강하고 breadth가 약하면 소수 종목 주도로 해석한다." },
  ]));
  children.push(...await imageBlock(market.charts.industryRotation, 690, 430));
  children.push(caption("그림 3. GICS 산업그룹 상위 8개와 하위 8개"));

  children.push(heading("섹터별 상세", HeadingLevel.HEADING_1));
  children.push(paragraph("각 섹터에서 산업그룹 성과와 내부 확산을 먼저 보고, 상승·하락 종목은 각각 최대 8개만 표시한다.", { color: C.gray }));
  for (let idx = 0; idx < sectors.length; idx += 1) {
    children.push(...await sectorDetail(sectors[idx], idx + 1));
  }

  children.push(pageBreak());
  children.push(heading("활용 방법과 계산 정의"));
  children.push(heading("발표에서 먼저 볼 순서", HeadingLevel.HEADING_2));
  children.push(paragraph("① 전체 섹터 성과표에서 선두·최하위와 스프레드를 확인한다. ② 섹터 수익률 그림과 breadth 그림이 같은 방향인지 본다. ③ 산업그룹 그림에서 섹터 내부의 주도 산업을 찾는다. ④ 섹터별 상·하위 종목 표에서 평균이 한두 종목에 의해 왜곡됐는지 점검한다."));
  children.push(heading("기간 정의", HeadingLevel.HEADING_2));
  children.push(paragraph(`5D=${market.start5d} 종가 대비 ${market.asOf} 종가의 단순수익률이다. 유효 거래일 종가 여섯 개를 사용해 정확히 다섯 거래 세션의 변화를 측정했다. 사용한 종가는 ${market.sessionDates.join(", ")}다.`));
  children.push(heading("분류와 집계", HeadingLevel.HEADING_2));
  children.push(paragraph("분류는 원천 BQL의 GICS Sector와 GICS Industry Group을 사용한다. 섹터·산업 수익률은 유효 구성종목의 현지통화 가격수익률을 동일가중 산술평균한다. 유럽은 통화가 혼재하므로 환산되지 않은 시가총액 가중보다 동일가중 방식이 비교 가능성이 높다."));
  children.push(heading("데이터 주의사항", HeadingLevel.HEADING_2));
  const sourceNote = market.sourceMode === "historical_fallback"
    ? `현재 Master의 TOPIX 구간에는 실제 거래 종가가 충분하지 않아, 최소 여섯 개 유효 종가를 독립적으로 보유한 최신 역사 원천의 5거래일 구간을 사용했다. 따라서 TOPIX 보고서 기준일은 ${market.asOf}다.`
    : "Master의 최신 유효 거래일을 기준으로 계산했다.";
  children.push(paragraph(`현재 구성종목을 과거 구간에 소급하므로 생존편향이 있다. 배당과 환율 효과는 제외한다. 가격과 시가총액의 연속성이 크게 어긋나는 명백한 기업행위 의심치 ${fmt(market.excludedCount)}개는 집계와 순위에서 제외했다. ${sourceNote}`, { color: C.gray }));
  children.push(paragraph(`원자료: ${market.sourceWorkbook} · 시트: ${market.sourceSheet}`, { size: 15, color: C.gray }));
  children.push(paragraph(`계산 JSON: ${inputPath}`, { size: 15, color: C.gray }));

  const doc = new Document({
    creator: "OpenAI Codex",
    title: `${market.title} 섹터와 산업 최근 5거래일 보고서`,
    description: "BQuant sector and GICS industry group performance with sector-level top gainers and bottom losers",
    styles: {
      default: {
        document: { run: { font: "Malgun Gothic", size: 19 }, paragraph: { spacing: { line: 286 } } },
      },
      paragraphStyles: [
        {
          id: "Title",
          name: "Title",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { font: "Malgun Gothic", size: 40, bold: true, color: C.navy },
          paragraph: { alignment: AlignmentType.CENTER, spacing: { after: 220 } },
        },
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { font: "Malgun Gothic", size: 28, bold: true, color: C.navy },
          paragraph: { spacing: { before: 220, after: 110 }, outlineLevel: 0 },
        },
        {
          id: "Heading2",
          name: "Heading 2",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { font: "Malgun Gothic", size: 21, bold: true, color: C.blue },
          paragraph: { spacing: { before: 170, after: 80 }, outlineLevel: 1 },
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: 12240, height: 15840 },
            margin: { top: 650, right: 650, bottom: 650, left: 650, header: 320, footer: 320 },
          },
        },
        headers: {
          default: new Header({
            children: [new Paragraph({
              alignment: AlignmentType.RIGHT,
              children: [textRun(`${market.title} · Sector and Industry · 5D`, { size: 13, color: C.gray })],
            })],
          }),
        },
        footers: {
          default: new Footer({
            children: [new Paragraph({
              alignment: AlignmentType.RIGHT,
              children: [
                textRun(`${market.asOf}  |  `, { size: 13, color: C.gray }),
                new TextRun({ children: [PageNumber.CURRENT], font: "Malgun Gothic", size: 13, color: C.gray }),
              ],
            })],
          }),
        },
        children,
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log(outputPath);
}


buildDocument().catch((error) => {
  console.error(error);
  process.exit(1);
});
