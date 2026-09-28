const fs = require('fs');
const path = require('path');
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  Footer,
  HeadingLevel,
  ImageRun,
  PageBreak,
  PageNumber,
  PageOrientation,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require('docx');

const dataPath = process.argv[2] || path.join(__dirname, 'output', 'Market_10D_Enriched_latest.json');
const chartDir = path.join(__dirname, 'output', 'charts');
const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
const tag = data.meta?.tag || String(data.meta?.asOf || '').replaceAll('-', '');
const outPath = process.argv[3] || path.join(__dirname, 'output', `SPX_CSI300_STOXX600_최근10거래일_Top10_Down10_${tag}.docx`);

const C = {
  navy: '102A43', blue: '2F6BDE', teal: '0FA3A3', red: 'D84A4A', gray: '62748A',
  light: 'F3F6FA', white: 'FFFFFF', green: '0B6E4F', greenLight: 'E8F5EE',
  amber: '9A6700', amberLight: 'FFF4D6', border: 'DCE3EC', black: '172B4D'
};

function run(text, opts = {}) {
  return new TextRun({ text, font: opts.font || 'Malgun Gothic', size: opts.size || 19,
    bold: opts.bold, italics: opts.italics, color: opts.color || C.navy });
}

function p(text, opts = {}) {
  const children = [];
  const tag = text.match(/^\[(DATA|FACT|INFERENCE|RISK|OPEN QUESTION)\]\s*/);
  if (tag) {
    const label = `[${tag[1]}] `;
    const color = tag[1] === 'FACT' ? C.green : tag[1] === 'INFERENCE' ? C.blue : tag[1] === 'DATA' ? C.teal : C.amber;
    children.push(run(label, { bold: true, color, size: opts.size || 18 }));
    children.push(run(text.slice(tag[0].length), { size: opts.size || 18, color: opts.color || C.navy }));
  } else {
    children.push(run(text, { size: opts.size || 18, bold: opts.bold, color: opts.color || C.navy, italics: opts.italics }));
  }
  return new Paragraph({
    children,
    bullet: opts.bullet ? { level: 0 } : undefined,
    alignment: opts.alignment,
    spacing: { before: opts.before || 0, after: opts.after ?? 95, line: opts.line || 270 },
    keepNext: opts.keepNext,
  });
}

function heading(text, level = 1) {
  const levelMap = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2, 3: HeadingLevel.HEADING_3 };
  const colors = { 1: C.navy, 2: C.blue, 3: C.teal };
  return new Paragraph({
    heading: levelMap[level],
    children: [run(text, { bold: true, color: colors[level], size: level === 1 ? 32 : level === 2 ? 25 : 21 })],
    spacing: { before: level === 1 ? 220 : 150, after: 110 },
    keepNext: true,
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function borders(color = C.border) {
  return {
    top: { style: BorderStyle.SINGLE, size: 3, color },
    bottom: { style: BorderStyle.SINGLE, size: 3, color },
    left: { style: BorderStyle.SINGLE, size: 3, color },
    right: { style: BorderStyle.SINGLE, size: 3, color },
  };
}

function cell(text, width, opts = {}) {
  const children = opts.children || [new Paragraph({
    children: [run(text, { size: opts.size || 15, bold: opts.bold, color: opts.color || C.navy })],
    alignment: opts.alignment,
    spacing: { after: 0, line: 210 },
  })];
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 65, bottom: 65, left: 75, right: 75 },
    borders: borders(),
    verticalAlign: 'center',
    children,
  });
}

function evidenceCell(type, width) {
  const fact = type === 'FACT';
  return cell(type, width, {
    size: 14, bold: true, alignment: AlignmentType.CENTER,
    color: fact ? C.green : C.amber,
    fill: fact ? C.greenLight : C.amberLight,
  });
}

function rankTable(rows, title, positive) {
  const widths = [650, 3200, 1150, 1250, 8700];
  const header = new TableRow({
    tableHeader: true,
    children: ['순위', '종목 / 섹터', '10D', '근거', '성과 요인 / 부각 테마'].map((t, i) => cell(t, widths[i], {
      fill: C.navy, color: C.white, bold: true, size: 15, alignment: AlignmentType.CENTER,
    }))
  });
  const body = rows.map((r, idx) => {
    const nameBlock = [
      new Paragraph({ children: [run(`${r.ticker} · ${r.name}`, { size: 15, bold: true })], spacing: { after: 35, line: 205 } }),
      new Paragraph({ children: [run(`${r.sector} / ${r.industry}`, { size: 13, color: C.gray })], spacing: { after: 0, line: 190 } }),
    ];
    const reasonBlock = [
      new Paragraph({ children: [run(r.theme, { size: 14, bold: true, color: positive ? C.blue : C.red })], spacing: { after: 35, line: 200 } }),
      new Paragraph({ children: [run(r.reason, { size: 14 })], spacing: { after: 0, line: 215 } }),
    ];
    return new TableRow({
      cantSplit: true,
      children: [
        cell(String(r.rank), widths[0], { alignment: AlignmentType.CENTER, size: 15, bold: true, fill: idx % 2 ? C.light : C.white }),
        cell('', widths[1], { children: nameBlock, fill: idx % 2 ? C.light : C.white }),
        cell(`${r.return >= 0 ? '+' : ''}${(r.return * 100).toFixed(1)}%`, widths[2], { alignment: AlignmentType.CENTER, size: 15, bold: true, color: positive ? C.blue : C.red, fill: idx % 2 ? C.light : C.white }),
        evidenceCell(r.reason_type, widths[3]),
        cell('', widths[4], { children: reasonBlock, fill: idx % 2 ? C.light : C.white }),
      ],
    });
  });
  return [
    heading(title, 2),
    new Table({ width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths, rows: [header, ...body] }),
  ];
}

function marketSection(key) {
  const m = data.markets[key];
  const top = m.rows.filter(r => r.direction === 'BEST');
  const bottom = m.rows.filter(r => r.direction === 'WORST');
  const chartPath = path.join(chartDir, `${key}_10d_rankings.png`);
  const imgWidth = 880;
  const imgHeight = Math.round(imgWidth * 1116 / 2430);
  const factTop = top.filter(r => r.reason_type === 'FACT').length;
  const factBottom = bottom.filter(r => r.reason_type === 'FACT').length;
  return [
    pageBreak(),
    heading(m.label, 1),
    p(`${m.start} → ${m.latest} · ${m.constituents}개 구성종목 · 배당 미포함 현지통화 가격수익률`, { color: C.gray, size: 17 }),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ data: fs.readFileSync(chartPath), transformation: { width: imgWidth, height: imgHeight }, type: 'png' })], spacing: { before: 70, after: 90 } }),
    p(`[DATA] ${m.summary}`, { size: 18 }),
    p(`[DATA] 현재 분석창에서 직접 확인된 과거 기업별 촉매가 연결된 항목은 상위 ${factTop}개, 하위 ${factBottom}개다. [DATA] 항목은 가격 순위만 자동 갱신된 것이므로 최신 공시·뉴스를 확인하기 전에는 원인을 단정하지 않는다.`, { size: 17 }),
    pageBreak(),
    ...rankTable(top, `${m.short} Best 10`, true),
    pageBreak(),
    ...rankTable(bottom, `${m.short} Worst 10`, false),
  ];
}

function sourceParagraph(code, src) {
  return new Paragraph({
    children: [
      run(`${code} · ${src.name}: `, { size: 16, bold: true }),
      new ExternalHyperlink({ link: src.url, children: [run(src.url, { size: 16, color: C.blue })] }),
    ],
    spacing: { after: 80, line: 240 },
  });
}

const marketKeys = Object.keys(data.markets);
const periodText = marketKeys
  .map(key => `${data.markets[key].short} ${data.markets[key].start}→${data.markets[key].latest}`)
  .join(' · ');

const body = [
  new Paragraph({ children: [run('S&P 500·CSI 300·STOXX Europe 600', { size: 42, bold: true, color: C.navy })], spacing: { after: 80 } }),
  new Paragraph({ children: [run('최근 10거래일 Best / Worst 10', { size: 36, bold: true, color: C.blue })], spacing: { after: 170 } }),
  p('최신 BQuant 가격으로 자동 갱신되는 시장 내부 로테이션 모니터', { size: 24, color: C.gray, after: 280 }),
  p(`기준일 ${data.meta.asOf} · ${periodText} · 배당 미포함 현지통화 가격수익률`, { size: 18, color: C.gray }),
  pageBreak(),

  heading('Executive Summary', 1),
  p(`[DATA] 입력 파일에서 지수별 최신 유효 거래일을 찾고, 직전 값 반복일과 휴일을 제외한 최근 11개 종가 사이의 10거래일 수익률로 순위를 계산했다. ${periodText}.`),
  ...marketKeys.map(key => p(`[DATA] ${data.markets[key].label}: ${data.markets[key].summary}`)),
  p('[RISK] 순위와 섹터 집중도는 자동 갱신되지만 기업별 촉매는 자동 확정하지 않는다. [DATA]로 표시된 종목은 최신 공시·뉴스를 별도로 확인해야 한다.'),

  ...marketKeys.flatMap(key => marketSection(key)),

  pageBreak(),
  heading('Cross-market Read', 1),
  ...marketKeys.map(key => {
    const m = data.markets[key];
    return p(`[DATA] ${m.label} · ${m.theme}`);
  }),
  p('[INFERENCE] 여러 시장에서 같은 섹터가 동시에 상위 또는 하위에 집중될 때 공통 팩터 로테이션일 가능성이 높다. 단일 시장·단일 종목 움직임은 기업 이벤트 가능성을 우선 점검한다.'),
  p('[RISK] 10거래일은 이벤트, 숏커버, 유동성에 민감하다. 상위 종목을 구조적 승자로, 하위 종목을 펀더멘털 훼손으로 곧바로 해석하지 않는다.'),

  heading('Methodology', 1),
  p('[DATA] Universe는 S&P 500, CSI 300, STOXX Europe 600의 최신 BQuant 구성종목이다. 전체 상장주 순위가 아니다.'),
  p('[DATA] 전일과 당일 가격이 모두 유효한 구성종목 중 10%를 초과해 가격이 변한 날짜를 실제 거래일로 판정한다. 각 지수의 마지막 유효 거래일에서 10개 거래구간 전 종가를 시작값으로 쓴다.'),
  p('[DATA] 시작일과 종료일 가격이 모두 존재하고 시작가격이 양수인 종목만 포함한다. 수익률은 현지통화 단순 가격수익률이며 배당과 환율효과를 포함하지 않는다.'),
  p('[DATA] [FACT]와 [INFERENCE] 설명은 해당 분석창과 정확히 일치할 때만 과거 검증자료를 연결한다. 새로운 분석창은 [DATA] 상태로 생성되어 촉매 검증이 필요하다.'),

  heading('Next Checks', 1),
  p('[OPEN QUESTION] 상·하위 종목의 최신 실적 발표, 가이던스, 규제·정책, M&A, 자본조달 공시가 가격 변화를 직접 설명하는가?'),
  p('[OPEN QUESTION] 같은 섹터 종목이 여러 시장에서 함께 움직였는가, 아니면 한 시장의 특수 이벤트인가?'),
  p('[OPEN QUESTION] 10거래일 수익률이 EPS 추정치 변화와 동행하는가, 아니면 P/E·포지셔닝 변화가 주도했는가?'),

  pageBreak(),
  heading('Sources', 1),
  p('가격·구성종목: 사용자 제공 BQuant 원자료. 기업별 촉매를 검증한 분석창에서는 아래 출처가 함께 표시된다.', { color: C.gray }),
  ...(Object.keys(data.sources).length
    ? Object.entries(data.sources).map(([code, src]) => sourceParagraph(code, src))
    : [p('[DATA] 이번 자동 갱신본에는 최신 기업별 촉매 출처가 아직 연결되지 않았다.', { color: C.gray })]),
];

const doc = new Document({
  creator: 'OpenAI Codex',
  title: 'S&P 500·CSI 300·STOXX Europe 600 최근 10거래일 Top10·Down10 분석',
  description: 'BQuant 가격자료와 기업 공시·시장 보도를 결합한 최근 10거래일 성과 요인 분석',
  styles: {
    default: { document: { run: { font: 'Malgun Gothic', size: 19, color: C.navy }, paragraph: { spacing: { line: 270 } } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Malgun Gothic', size: 32, bold: true, color: C.navy },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Malgun Gothic', size: 25, bold: true, color: C.blue },
        paragraph: { spacing: { before: 170, after: 100 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Malgun Gothic', size: 21, bold: true, color: C.teal },
        paragraph: { spacing: { before: 140, after: 90 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838, orientation: PageOrientation.LANDSCAPE },
        margin: { top: 650, right: 650, bottom: 650, left: 650 },
      },
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        run('10D Market Leaders & Laggards  |  ', { size: 14, color: C.gray, font: 'Aptos' }),
        new TextRun({ children: [PageNumber.CURRENT], size: 14, color: C.gray, font: 'Aptos' }),
      ] })] }),
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log(outPath);
});

