const fs = require('fs');
const path = require('path');
const {
  AlignmentType, BorderStyle, Document, ExternalHyperlink, Footer, Header,
  HeadingLevel, PageBreak, PageNumber, Packer, Paragraph, ShadingType,
  Table, TableCell, TableRow, TextRun, WidthType,
} = require('docx');

const ROOT = 'C:\\Users\\infomax\\Documents\\python\\BQL\\Theme\\output\\Top10_Down10';
const DATA_PATH = path.join(ROOT, 'US_China_Eurozone_Top10_Data_20260902.json');
const OUT_PATH = path.join(ROOT, '미국_중국_유로존_1D_10D_Best_Worst_20260902.docx');
const data = JSON.parse(fs.readFileSync(DATA_PATH, 'utf8'));

const C = {
  navy: '17365D', blue: '2F75B5', pale: 'EAF2F8', line: 'B4C7DC',
  gray: '666666', lightGray: 'F3F5F7', red: 'C00000', green: '008000',
  amber: '9C6500', white: 'FFFFFF', black: '111111',
};
const marketLabel = {SPX: '미국 · S&P 500', SHSZ300: '중국 · CSI 300', SX5E: '유로존 · EURO STOXX 50'};
const markets = Object.fromEntries(data.markets.map(m => [m.code, m]));
const pct = (v, d=1) => v == null || !Number.isFinite(v) ? '—' : `${v >= 0 ? '+' : ''}${(v*100).toFixed(d)}%`;
const ptile = v => v == null ? '—' : `${Math.round(v*100)}`;
const shortTicker = x => String(x.ticker || '').split(' ')[0];
const fmtNum = v => new Intl.NumberFormat('ko-KR').format(v);

function run(text, opts={}) {
  return new TextRun({
    text: String(text), font: 'Malgun Gothic', size: opts.size || 18,
    bold: !!opts.bold, italics: !!opts.italics, color: opts.color || C.black,
  });
}
function p(text, opts={}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.LEFT,
    spacing: {before: opts.before || 0, after: opts.after ?? 90, line: opts.line || 276},
    keepNext: !!opts.keepNext,
    children: [run(text, opts)],
  });
}
function h(text, level=HeadingLevel.HEADING_1) {
  return new Paragraph({text, heading: level, keepNext: true, spacing: {before: 180, after: 90}});
}
function pageBreak() { return new Paragraph({children: [new PageBreak()]}); }
function tagged(text) {
  let color = C.black;
  if (text.startsWith('[FACT]')) color = C.navy;
  if (text.startsWith('[RISK]')) color = C.red;
  if (text.startsWith('[OPEN QUESTION]')) color = C.amber;
  return p(text, {color});
}
function cell(text, width, opts={}) {
  return new TableCell({
    width: {size: width, type: WidthType.DXA},
    shading: opts.fill ? {fill: opts.fill, type: ShadingType.CLEAR} : undefined,
    margins: {top: 55, bottom: 55, left: 65, right: 65},
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      children: [run(text, {size: opts.size || 14, bold: opts.bold, color: opts.color})],
    })],
  });
}
function table(rows, widths) {
  return new Table({
    width: {size: widths.reduce((a,b)=>a+b,0), type: WidthType.DXA},
    columnWidths: widths,
    rows,
    borders: {
      top: {style: BorderStyle.SINGLE, size: 4, color: C.line},
      bottom: {style: BorderStyle.SINGLE, size: 4, color: C.line},
      left: {style: BorderStyle.SINGLE, size: 4, color: C.line},
      right: {style: BorderStyle.SINGLE, size: 4, color: C.line},
      insideHorizontal: {style: BorderStyle.SINGLE, size: 2, color: 'D9E2F3'},
      insideVertical: {style: BorderStyle.SINGLE, size: 2, color: 'D9E2F3'},
    },
  });
}
function placeholder(title, message) {
  return new Paragraph({
    spacing: {before: 110, after: 140},
    border: {left: {style: BorderStyle.SINGLE, size: 18, color: C.blue}},
    shading: {fill: C.pale, type: ShadingType.CLEAR},
    children: [run(`[그래프 삽입 위치] ${title}`, {bold: true, color: C.blue}), run(` — ${message}`, {color: C.gray})],
  });
}
function rankPairTable(best, worst, period) {
  const widths = [430, 1800, 700, 700, 680, 430, 1800, 700, 700, 680];
  const head = ['#', `${period} Best`, period, '상대순위', '10D MDD', '#', `${period} Worst`, period, '상대순위', '10D MDD'];
  const rows = [new TableRow({tableHeader: true, children: head.map((x,i)=>cell(x,widths[i],{fill:C.navy,color:C.white,bold:true,align:AlignmentType.CENTER}))})];
  for (let i=0; i<10; i++) {
    const b=best[i], w=worst[i];
    const key = period === '1D' ? 'return1d' : 'return10d';
    const pk = period === '1D' ? 'percentile1d' : 'percentile10d';
    rows.push(new TableRow({children: [
      cell(i+1,widths[0],{align:AlignmentType.CENTER}),
      cell(`${shortTicker(b)} · ${b.name}`,widths[1]),
      cell(pct(b[key]),widths[2],{align:AlignmentType.RIGHT,color:C.green}),
      cell(ptile(b[pk]),widths[3],{align:AlignmentType.CENTER}),
      cell(pct(b.maxDrawdown10d),widths[4],{align:AlignmentType.RIGHT}),
      cell(i+1,widths[5],{align:AlignmentType.CENTER}),
      cell(`${shortTicker(w)} · ${w.name}`,widths[6]),
      cell(pct(w[key]),widths[7],{align:AlignmentType.RIGHT,color:C.red}),
      cell(ptile(w[pk]),widths[8],{align:AlignmentType.CENTER}),
      cell(pct(w.maxDrawdown10d),widths[9],{align:AlignmentType.RIGHT}),
    ]}));
  }
  return table(rows,widths);
}
function sectorCount(items) {
  const c={}; for (const x of items) c[x.sector]=(c[x.sector]||0)+1;
  return Object.entries(c).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${k} ${v}`).join(', ');
}
function linkParagraph(id, title, publisher, date, url) {
  return new Paragraph({spacing:{after:70},children:[
    run(`${id} · ${title} · ${publisher} · ${date} · `,{bold:true,color:C.navy,size:15}),
    new ExternalHyperlink({link:url,children:[new TextRun({text:'원문',font:'Malgun Gothic',size:15,color:C.blue,underline:{}})]}),
  ]});
}

const eventNotes = {
  SPX: [
    '[FACT] 미국 1D 상위는 CHTR +6.1%, RDDT +6.0%, SWKS +4.9%였고 하위는 PCG -8.1%, PANW -7.9%, EIX -6.5%였다. [M1]',
    '[FACT] Palo Alto Networks는 직전 발표에서 매출 +34%, NGS ARR +63%를 기록했다. [S3] [INFERENCE] 강한 숫자에도 -7.9% 하락한 점은 실적의 절대 수준보다 기대치·마진·인수 통합 부담이 가격을 좌우한 sell-the-news 반응에 가깝다.',
    '[FACT] 캘리포니아 유틸리티는 산불 책임 법안과 투자·재무 부담 이슈로 동반 약세가 보도됐다. [S6] [INFERENCE] PCG·EIX 하락은 순수한 경기·금리 신호보다 주별 정책 리스크의 영향이 크다.',
    '[FACT] 10D 상위 CRM은 +24.0%였다. Salesforce는 cRPO +14%(constant currency)와 상향된 매출 가이던스를 발표했다. [S2] [INFERENCE] AI 소프트웨어에서 실제 계약·백로그가 확인된 종목으로 선별적 재평가가 진행됐다.',
    '[FACT] 10D 하위에는 MRVL -13.6%, AMAT -11.9%가 포함됐다. Marvell은 매출 +37%, 데이터센터 +46%와 상향 가이던스를 발표했다. [S4] [INFERENCE] 펀더멘털 악화라기보다 높은 사전 기대와 하드웨어 혼잡도 조정 가능성이 더 크다.',
  ],
  SHSZ300: [
    '[FACT] 중국 1D 상위는 Mango Excellent Media +20.0%, Gujing Gongjiu +10.0%, PICC +6.2%였고 하위는 Ruijie Networks -6.3%, Shengyi Technology -5.9%, ACM Research Shanghai -5.6%였다. [M1]',
    '[FACT] 9월 1일 중국 본토 시장에서는 기술주가 약했고 농업·보험이 상대적으로 강했다. [S7] [INFERENCE] 상·하위 구성이 시장 전체 방향보다 AI 응용 콘텐츠 대 네트워크·PCB·장비의 내부 로테이션을 보여준다.',
    '[FACT] Mango의 AI 장편 콘텐츠 공개가 현지 언론에 보도됐다. [S8] [INFERENCE] 응용 계층의 가시적 제품 촉매가 가격제한폭 상승과 결합했지만, 단일 세션 반응의 지속성은 별도 확인이 필요하다.',
    '[FACT] 10D 최하위 Sungrow는 -24.3%였다. 상반기 이익 감소와 주가 급락이 보도됐다. [S9] [INFERENCE] 신재생·전력장비는 정책 테마보다 실적·마진이 우선되는 국면으로 이동했다.',
  ],
  SX5E: [
    '[FACT] 유로존 1D 상위는 Adyen +2.6%, ING +2.6%, argenx +2.1%였고 하위는 Volkswagen -3.6%, Wolters Kluwer -3.2%, Enel -2.7%였다. [M1]',
    '[FACT] 10D 상위 DBK +7.1%, ING +4.9%로 은행이 선두였다. Deutsche Bank는 2분기 세후이익 19억 유로, ING는 세전이익 +23%, 수수료수입 +14%, ROTE 17%를 발표했다. [S10][S11]',
    '[INFERENCE] 유로존의 단기 리더십은 광범위한 경기민감주 상승보다 실적이 확인된 은행에 집중됐다. 반면 Siemens Energy·Vinci·Rheinmetall 등 정책·인프라 기대 수혜주는 10D 하위권으로, 기대 선반영 이후의 차익실현이 관찰된다.',
    '[FACT] Siemens Energy는 3분기 실적과 전망을 공식 발표했다. [S12] [RISK] 10D 약세를 공식 숫자 하나로 단정할 수 없으며 금리·포지셔닝·사전 기대를 함께 봐야 한다.',
  ],
};

const sources = [
  ['M1','BQuant_Master.xlsx','사용자 제공 Bloomberg BQuant 원자료','2026-09-03 갱신','로컬 파일'],
  ['S1','Wall Street rises as tech stocks climb','Associated Press','2026-09-02','https://apnews.com/article/27b78c349725ac744c96a6b8b8167bae'],
  ['S2','Salesforce FY27 Q2 earnings','Salesforce','2026-08-26','https://www.salesforce.com/news/press-releases/2026/08/26/fy27-q2-earnings/'],
  ['S3','Palo Alto Networks fiscal Q4 and FY2026 results','Palo Alto Networks','2026-09-01','https://investors.paloaltonetworks.com/news-releases/news-release-details/palo-alto-networks-reports-fiscal-fourth-quarter-and-fiscal-10'],
  ['S4','Marvell fiscal Q2 2027 results','Marvell Technology','2026-08-27','https://investor.marvell.com/news-events/press-releases/detail/1031/marvell-technology-inc-reports-second-quarter-of-fiscal-year-2027-financial-results'],
  ['S5','Deere fiscal Q3 2026 results','U.S. SEC / Deere','2026-08-20','https://www.sec.gov/Archives/edgar/data/315189/000110465926098904/de-20260820xex99d1.htm'],
  ['S6','California utility stocks slide on wildfire legislation','S&P Global Market Intelligence','2026-08','https://www.spglobal.com/market-intelligence/en/news-insights/articles/2026/8/california-utility-stocks-slide-on-wildfire-legislation-105564049'],
  ['S7','China stocks mixed as technology weakens','Xinhua','2026-09-01','https://english.news.cn/20260901/119ce8fae4a045dabc740004d3c2b1ee/c.html'],
  ['S8','Mango launches AI long-form drama','National Business Daily','2026-09-01','https://www.nbd.com.cn/articles/2026-09-01/4568303.html'],
  ['S9','Sungrow shares slump as profit tumbles','Bloomberg via Yahoo Finance','2026-08','https://finance.yahoo.com/energy/articles/sungrow-shares-slump-profit-tumbles-042904091.html'],
  ['S10','Deutsche Bank Q2 2026 results','Deutsche Bank','2026-07-29','https://www.deutsche-bank.eu/news/detail/20260729-deutsche-bank-reports-second-quarter-2026-results?language_id=1'],
  ['S11','ING Q2 2026 results','ING','2026-08','https://ing.com/news/press-releases/2q2026-ing-press-release.html'],
  ['S12','Siemens Energy Q3 FY2026 results','Siemens Energy','2026','https://www.siemens-energy.com/global/en/home/press-releases/third-quarter-results-fy-2026.html'],
  ['S13','Amphenol two-for-one stock split','Amphenol','2026','https://investor.amphenol.com/news-and-events/news-details/2026/Amphenol-Announces-Two-for-One-Stock-Split-and-Third-Quarter-2026-Dividend/default.aspx'],
];

const children=[];
children.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:760,after:200},children:[run('미국·중국·유로존',{size:36,bold:true,color:C.navy})]}));
children.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:190},children:[run('최근 1D / 10D Best & Worst 종목 분석',{size:30,bold:true,color:C.blue})]}));
children.push(p('기준일: 미국·유로존 2026-09-02 / 중국 2026-09-01',{align:AlignmentType.CENTER,size:20,color:C.gray}));
children.push(p('현지통화 단순 가격수익률 · 배당 제외 · current-constituent 방식',{align:AlignmentType.CENTER,size:18,color:C.gray}));
children.push(p('[FACT] 최신 BQuant 원자료를 자동 병합한 뒤 실제 거래일을 식별해 계산했다.',{before:700,color:C.navy}));
children.push(p('[RISK] 본 문서는 단기 가격 모니터링 자료이며 투자권유가 아니다. 1일 수익률은 이벤트·수급·기업행위에 민감하다.',{color:C.red}));
children.push(pageBreak());

children.push(h('Executive Summary'));
for (const code of ['SPX','SHSZ300','SX5E']) {
  const m=markets[code];
  children.push(tagged(`[FACT] ${marketLabel[code]}: 1D 주식수 가중 집계가격 프록시 ${pct(m.marketReturn1dProxy)}, 10D ${pct(m.marketReturn10dProxy)}, 1D 상승/하락 ${m.advancers}/${m.decliners}개.`));
}
children.push(tagged('[INFERENCE] 미국은 소프트웨어 실적 확인과 개별 규제 이벤트가 동시에 작동했고, 중국은 AI 응용 콘텐츠와 하드웨어 사이의 분화가 컸다. 유로존은 은행의 실적 기반 강세가 유지됐지만 정책·인프라 수혜주의 차익실현이 나타났다.'));
children.push(tagged('[RISK] 세 시장의 1D·10D 수익률은 현지통화 기준이어서 원화 투자자의 환효과를 포함하지 않는다. 공식 지수 수익률이 아니라 최신 구성종목의 주식수 가중 집계가격 프록시다.'));
children.push(placeholder('세 시장 1D·10D 대표 수익률과 상승/하락 종목 수','시장 방향과 종목 확산도를 동시에 비교'));

children.push(h('Methodology & Data QA'));
for (const m of data.markets) {
  children.push(tagged(`[FACT] ${m.code}: ${m.start}→${m.end}의 10개 실제 수익률 구간(11개 종가), 직전일 ${m.previous}, 원 구성 ${fmtNum(m.sourceMembers)}개, 유효 순위 ${fmtNum(m.members)}개, 교집합 결측 제외 ${m.missingIntersection}개, 종료일 반복가격 ${m.repeatedLatestPrices}개.`));
}
children.push(tagged('[FACT] 1D=종료일/직전 실제 거래일-1, 10D=종료일/10거래일 전-1이다. 최대낙폭은 11개 실제 종가의 누적고점 대비 최저 하락률이다.'));
children.push(tagged('[FACT] APH의 2대1 주식분할로 과거 구간에 조정·비조정 가격이 혼재된 흔적을 확인했다. 원본은 보존하고 보고서 계산용 복사본에서만 분할 연속성을 복원했다. [S13]'));
children.push(tagged('[ASSUMPTION] 현재 구성종목을 과거 시점에도 소급 적용하므로 편입·편출과 상장폐지 종목을 반영하지 못하는 생존편향이 있다.'));
children.push(tagged('[RISK] 주식수 가중 집계가격 프록시는 자유유통비율, 지수 캡, 배당, divisor, 공식 기업행위 조정이 반영된 지수 총수익률과 다를 수 있다.'));
children.push(pageBreak());

for (const code of ['SPX','SHSZ300','SX5E']) {
  const m=markets[code];
  children.push(h(marketLabel[code]));
  children.push(tagged(`[FACT] 1D ${m.previous}→${m.end}: ${pct(m.marketReturn1dProxy)}. 상위 섹터 구성은 ${sectorCount(m.best1d)}, 하위는 ${sectorCount(m.worst1d)}.`));
  children.push(rankPairTable(m.best1d,m.worst1d,'1D'));
  children.push(placeholder(`${marketLabel[code]} 1D Best/Worst 10`,`수익률 0선을 중심으로 양·음수 막대를 분리`));
  children.push(pageBreak());
  children.push(h(`${marketLabel[code]} · 10D 추세 점검`));
  children.push(tagged(`[FACT] 10D ${m.start}→${m.end}: ${pct(m.marketReturn10dProxy)}. 상위 섹터 구성은 ${sectorCount(m.best10d)}, 하위는 ${sectorCount(m.worst10d)}.`));
  children.push(rankPairTable(m.best10d,m.worst10d,'10D'));
  children.push(placeholder(`${marketLabel[code]} 10D Best/Worst 10`,`10D 수익률과 기간 중 최대낙폭을 함께 표시`));
  children.push(pageBreak());
  children.push(h(`${marketLabel[code]} · 가격 변동 해석`));
  for (const note of eventNotes[code]) children.push(tagged(note));
  children.push(tagged('[OPEN QUESTION] 다음 세션에도 상대강도가 이어지는지, 거래량·실적추정치·공식 공시가 가격 신호를 사후 확인하는지 점검한다.'));
  if (code !== 'SX5E') children.push(pageBreak());
}

children.push(pageBreak());
children.push(h('교차시장 투자 시사점'));
children.push(h('1. AI: 전체 베타보다 계층 선택',HeadingLevel.HEADING_2));
children.push(tagged('[INFERENCE] 미국에서는 Salesforce·NVIDIA가 강한 반면 사이버보안과 일부 반도체 장비는 약했다. 중국도 Mango의 AI 콘텐츠 강세와 네트워크·반도체 장비 약세가 공존했다. “AI 매수/매도”보다 응용·플랫폼·하드웨어의 이익 가시성과 혼잡도를 분리해야 한다.'));
children.push(h('2. 정책·인프라: 발표보다 손익 전환',HeadingLevel.HEADING_2));
children.push(tagged('[INFERENCE] 미국 유틸리티의 규제 부담, 중국 신재생 장비의 이익 둔화, 유럽 정책 수혜주의 차익실현은 정책 테마가 실제 수주·마진·현금흐름으로 전환되는 속도를 시장이 다시 평가하고 있음을 시사한다.'));
children.push(h('3. 가치·금융: 유럽 은행의 실적 확인',HeadingLevel.HEADING_2));
children.push(tagged('[FACT] DBK와 ING가 유로존 10D 상위권을 차지했고, 양사 모두 최근 실적에서 이익·수수료·수익성 개선을 확인했다. [S10][S11] [INFERENCE] 단순 저P/E가 아니라 EPS와 자본수익률이 동반되는 가치주가 유리했다.'));
children.push(h('4. 포트폴리오 적용',HeadingLevel.HEADING_2));
children.push(tagged('[INFERENCE] 단기 상위 종목은 추세 강화와 낙폭과대 반등을 구분하고, 10D 최대낙폭이 큰 종목은 포지션 크기를 보수적으로 설정한다. 국가 간 비교 시에는 현지통화 수익률에 별도로 원화 환산 효과를 더해야 한다.'));
children.push(placeholder('AI / 정책·인프라 / 가치·금융 교차시장 매트릭스','가격 방향, 실적 근거, 지속 가능성을 3축으로 정리'));

children.push(pageBreak());
children.push(h('Sources'));
children.push(p('시장 데이터는 사용자 제공 BQuant 파일을 사용했다. 외부 자료는 가격 원인의 확인·반증에만 사용했고, 직접 근거가 부족한 경우 추론 또는 미확인으로 남겼다.',{color:C.gray}));
for (const s of sources) {
  if (s[4] === '로컬 파일') children.push(p(`${s[0]} · ${s[1]} · ${s[2]} · ${s[3]} · 로컬 원자료`,{size:15,color:C.navy}));
  else children.push(linkParagraph(...s));
}

const doc = new Document({
  creator: 'OpenAI Codex',
  title: '미국·중국·유로존 최근 1D / 10D Best & Worst 종목 분석',
  description: 'Bloomberg BQuant constituent return monitor',
  styles: {
    default: {document: {run: {font: 'Malgun Gothic', size: 18}, paragraph: {spacing: {line: 276}}}},
    paragraphStyles: [
      {id:'Heading1',name:'Heading 1',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:28,bold:true,color:C.navy},paragraph:{spacing:{before:220,after:110},outlineLevel:0}},
      {id:'Heading2',name:'Heading 2',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:22,bold:true,color:C.blue},paragraph:{spacing:{before:170,after:80},outlineLevel:1}},
      {id:'Heading3',name:'Heading 3',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:19,bold:true,color:C.navy},paragraph:{spacing:{before:140,after:70},outlineLevel:2}},
    ],
  },
  sections: [{
    properties: {page: {size: {width: 16838, height: 11906, orientation: 'landscape'}, margin: {top: 650, right: 680, bottom: 650, left: 680}}},
    headers: {default: new Header({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:[run('Daily Cross-Market Monitor · 2026-09-02',{size:13,color:C.gray})]})]})},
    footers: {default: new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[run('Confidential · ',{size:13,color:C.gray}),new TextRun({children:[PageNumber.CURRENT],font:'Malgun Gothic',size:13,color:C.gray})]})]})},
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT_PATH, buf);
  console.log(OUT_PATH);
});
