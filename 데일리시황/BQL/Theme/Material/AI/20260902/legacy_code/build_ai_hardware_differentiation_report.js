const fs = require('fs');
const path = require('path');
const {
  AlignmentType, BorderStyle, Document, ExternalHyperlink, Footer, HeadingLevel,
  ImageRun, PageBreak, PageNumber, PageOrientation, Packer, Paragraph, ShadingType,
  Table, TableCell, TableRow, TextRun, WidthType,
} = require('docx');

const outPath = 'C:\\Users\\USER\\Downloads\\유로존\\AI_하드웨어_차별화_메모리_장비_EC_전력_20260902.docx';
const chartPath = path.resolve('research_tmp/ai_hardware_split_10d.png');
const C = { navy:'102A43', blue:'2F6BDE', teal:'0FA3A3', red:'D84A4A', amber:'EAAA00', gray:'62748A', light:'F3F6FA', white:'FFFFFF', green:'0B6E4F', border:'DCE3EC' };

const sources = [
  ['S1', 'SK hynix 2Q26 results', 'https://news.skhynix.com/en/q2-2026-business-results/'],
  ['S2', 'Micron FY26 Q3 results', 'https://investors.micron.com/news/press-release/2026/Micron-Technology-Inc--Reports-Record-Results-for-the-Third-Quarter-of-Fiscal-2026/default.aspx'],
  ['S3', 'TSMC 2Q26 results', 'https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-07/a80d7933be643644081584087731f73b22ea5a2c/2Q26%20EarningsRelease.pdf'],
  ['S4', 'ASML 2Q26 results', 'https://www.asml.com/en/news/press-releases/2026/q2-2026-financial-results'],
  ['S5', 'Applied Materials FY26 Q3 results', 'https://ir.appliedmaterials.com/news-releases/news-release-details/applied-materials-announces-third-quarter-2026-results'],
  ['S6', 'Schneider Electric 1H26 results', 'https://www.se.com/ww/en/about-us/investor-relations/financial-results/'],
  ['S7', 'GE Vernova 2Q26 results', 'https://www.gevernova.com/news/press-releases/ge-vernova-reports-second-quarter-2026-financial-results-raises-2026-financial'],
  ['S8', 'Siemens Energy Q3 FY26 results', 'https://www.siemensenergy.com/global/en/home/investor-relations.html'],
  ['S9', 'Comfort Systems USA 2Q26 results', 'https://www.sec.gov/Archives/edgar/data/1035983/000110465926086255/fix-20260723xex99d1.htm'],
  ['S10', 'Comfort Systems USA 2Q26 10-Q', 'https://www.sec.gov/Archives/edgar/data/1035983/000110465926086258/fix-20260630x10q.htm'],
  ['S11', 'AI hardware earnings vs expectations', 'https://www.morningstar.com/stocks/why-great-earnings-havent-been-good-enough-ai-hardware-stocks'],
  ['S12', 'BQuant price and constituent data', 'Local file: Bquant_All_19_Grouped_Raw_Updated_20260901.xlsx'],
];

function run(text, opts={}) { return new TextRun({ text, font:opts.font||'Malgun Gothic', size:opts.size||19, bold:opts.bold, italics:opts.italics, color:opts.color||C.navy }); }
function p(text, opts={}) {
  const m = text.match(/^\[(FACT|INFERENCE|SPECULATION|RISK|OPEN QUESTION)\]\s*/);
  const children=[];
  if (m) {
    const color = m[1]==='FACT'?C.green:m[1]==='INFERENCE'?C.blue:C.amber;
    children.push(run(`[${m[1]}] `,{bold:true,color,size:opts.size||18}));
    children.push(run(text.slice(m[0].length),{size:opts.size||18,color:opts.color||C.navy}));
  } else children.push(run(text,{size:opts.size||18,bold:opts.bold,color:opts.color||C.navy,italics:opts.italics}));
  return new Paragraph({children,bullet:opts.bullet?{level:0}:undefined,alignment:opts.alignment,spacing:{after:opts.after??95,line:opts.line||270},keepNext:opts.keepNext});
}
function h(text, level=1) { return new Paragraph({heading:level===1?HeadingLevel.HEADING_1:level===2?HeadingLevel.HEADING_2:HeadingLevel.HEADING_3,children:[run(text,{bold:true,size:level===1?32:level===2?25:21,color:level===1?C.navy:level===2?C.blue:C.teal})],spacing:{before:level===1?210:140,after:100},keepNext:true}); }
function br() { return new Paragraph({children:[new PageBreak()]}); }
function borders(){ return {top:{style:BorderStyle.SINGLE,size:3,color:C.border},bottom:{style:BorderStyle.SINGLE,size:3,color:C.border},left:{style:BorderStyle.SINGLE,size:3,color:C.border},right:{style:BorderStyle.SINGLE,size:3,color:C.border}}; }
function cell(text,width,opts={}){ return new TableCell({width:{size:width,type:WidthType.DXA},shading:opts.fill?{fill:opts.fill,type:ShadingType.CLEAR}:undefined,margins:{top:70,bottom:70,left:75,right:75},borders:borders(),children:[new Paragraph({children:[run(text,{size:opts.size||15,bold:opts.bold,color:opts.color||C.navy})],alignment:opts.alignment,spacing:{after:0,line:215}})]}); }
function table(headers, rows, widths){ return new Table({width:{size:widths.reduce((a,b)=>a+b,0),type:WidthType.DXA},columnWidths:widths,rows:[new TableRow({tableHeader:true,children:headers.map((x,i)=>cell(x,widths[i],{fill:C.navy,color:C.white,bold:true,alignment:AlignmentType.CENTER}))}),...rows.map((r,ri)=>new TableRow({cantSplit:true,children:r.map((x,i)=>cell(x,widths[i],{fill:ri%2?C.light:C.white,size:i===0?15:14,bold:i===0}))}))]}); }

const selectedReturns = [
  ['Siemens','+1.9%','EU diversified'],['Schneider Electric','-1.2%','EU diversified'],['ABB','-2.7%','EU diversified'],['Micron','-5.2%','Memory'],['ASML','-6.0%','Semi equipment'],['Siemens Energy','-8.7%','Power'],['Vertiv','-11.5%','Power/cooling'],['Lam Research','-12.3%','Semi equipment'],['Applied Materials','-14.4%','Semi equipment'],['KLA','-14.7%','Semi equipment'],['EMCOR','-14.8%','E&C'],['Quanta Services','-16.0%','E&C'],['GE Vernova','-16.7%','Power'],['Comfort Systems','-17.8%','E&C'],['Teradyne','-21.1%','Test equipment'],
];

const body=[
  new Paragraph({children:[run('AI 하드웨어 내부 차별화',{size:48,bold:true})],spacing:{after:80}}),
  new Paragraph({children:[run('메모리 vs 파운드리·장비 vs E&C·전력',{size:34,bold:true,color:C.blue})],spacing:{after:180}}),
  p('왜 “가장 다운스트림인 수혜주”가 오히려 더 약했는가', {size:24,color:C.gray,after:260}),
  p('기준일 2026-09-02 · 최근 10거래일 BQuant 가격 · 최신 기업 실적·수주 교차검증',{size:18,color:C.gray}),
  br(),
  h('Executive Summary',1),
  p('[FACT] 최근 10거래일 Micron은 –5.2%로 절대 상승은 아니었다. 다만 AMAT –14.4%, KLA –14.7%, Lam –12.3%, Comfort Systems –17.8%, GE Vernova –16.7%보다 훨씬 잘 버텼다. “메모리 강세”는 절대 강세보다 상대적 방어로 보는 편이 정확하다. [S12]'),
  p('[INFERENCE] 메모리/HBM은 이미 출하·가격·마진으로 손익계산서에 반영되고 있다. 반면 장비는 고객 CAPEX의 두 번째 미분, E&C·전력은 수주가 매출·현금흐름으로 전환되는 데 시간이 걸리는 장기 프로젝트다.'),
  p('[FACT] 약한 주가가 수요 붕괴를 의미하지는 않는다. GE Vernova는 주문 +88%와 $176bn backlog, Comfort Systems는 매출 +50%와 $14.06bn backlog, Schneider는 Q2 유기적 매출 +17%, Siemens Energy는 기록적 주문을 발표했다. [S6][S7][S8][S9]'),
  p('[INFERENCE] 이번 차별화의 핵심은 펀더멘털 방향이 아니라 현금흐름의 시간이다. 당장 ASP와 마진이 오르는 메모리는 방어됐고, 수년 뒤 이익을 할인하는 프로젝트형 종목은 장기금리와 높은 기대치에 더 크게 맞았다.'),
  p('[INFERENCE] 유럽 수혜주라는 논리는 유효하지만, “유럽 상장”과 “유럽 재정 순수노출”은 다르다. Schneider의 성장 선도 지역은 북미와 중국·동아시아였고 Siemens Energy의 Q3 주문도 미국 수요가 주도했다. 이 종목들은 유럽 정책주이면서 동시에 글로벌 AI CAPEX·미국 금리주다. [S6][S8]'),

  br(),
  h('Key Findings · 가격이 말하는 것',1),
  new Paragraph({alignment:AlignmentType.CENTER,children:[new ImageRun({data:fs.readFileSync(chartPath),transformation:{width:700,height:477},type:'png'})],spacing:{after:60}}),
  p('[FACT] 유럽의 복합 전력·자동화 업체는 상대적으로 견조했다. Siemens +1.9%, Schneider –1.2%, ABB –2.7%인 반면 순수 전력·데이터센터 CAPEX 베타가 높은 Siemens Energy·GE Vernova·Vertiv는 –8.7%~-16.7%였다. [S12]'),
  p('[INFERENCE] 시장은 “AI 수혜 여부”보다 사업 포트폴리오의 분산, 현재 마진·FCF, 밸류에이션 부담을 구분했다. 순수 수혜주는 업사이드가 크지만 할인율·포지셔닝 충격도 더 크다.'),

  br(),
  h('Detailed Analysis 1 · 왜 메모리가 상대적으로 강했나',1),
  h('1. 가격이 오르면 매출과 마진에 즉시 반영된다',2),
  p('[FACT] SK hynix는 AI 서버용 HBM·DRAM·eSSD의 가격 상승과 고부가 제품 믹스로 2Q26 사상 최대 실적을 발표했고, HBM4 양산 출하와 약 10개 고객과의 장기계약을 언급했다. [S1]'),
  p('[FACT] Micron은 FY26 Q3 기록적 실적과 함께 다음 분기 매출 $50bn±$1bn, 비GAAP 매출총이익률 약 86%를 제시했고 HBM4의 대량 출하를 확인했다. [S2]'),
  p('[INFERENCE] HBM은 공급자가 제한되고 고객 인증이 필요하며, HBM 증설은 일반 DRAM 웨이퍼와 첨단 패키징 용량을 잠식한다. 공급 제약이 ASP와 마진으로 곧바로 연결되기 때문에 시장이 현재 이익을 평가하기 쉽다.'),
  h('2. 다만 “메모리 전체”가 안전한 것은 아니다',2),
  p('[RISK] Micron도 최근 10일 –5.2%였다. 메모리는 여전히 가격·재고·증설에 민감한 사이클 산업이다. 현재 높은 마진이 공급 증가와 고객 재고조정으로 꺾이면 이익 추정치가 가장 빠르게 내려갈 수 있다.'),
  p('[INFERENCE] 따라서 메모리 강세의 조건은 HBM 계약가격, 고객별 할당, 수율, 일반 DRAM 공급규율이 유지되는 것이다. “HBM 수요 증가”만으로는 부족하다.'),

  br(),
  h('Detailed Analysis 2 · 파운드리와 장비는 왜 약했나',1),
  h('1. 파운드리 펀더멘털이 나쁜 것은 아니다',2),
  p('[FACT] TSMC 2Q26 달러 매출은 전년 대비 33.7% 증가했고 첨단공정이 웨이퍼 매출의 77%를 차지했다. 다만 Q3 매출총이익률 가이던스 65~67%는 Q2 67.7%보다 낮고, 해외 팹의 마진 희석과 2nm 램프 비용이 공존한다. [S3]'),
  p('[INFERENCE] 파운드리는 AI 수요를 받지만 동시에 막대한 선행 CAPEX를 부담한다. 매출 증가가 곧바로 FCF와 ROIC 증가로 이어지지 않으며, AI 이외의 성숙공정 가동률도 함께 봐야 한다.'),
  h('2. 장비는 고객 CAPEX의 “두 번째 미분”이다',2),
  p('[FACT] ASML은 Q2 매출 €9.3bn, 매출총이익률 54%를 기록하고 2026년 매출 전망을 €43~45bn으로 높였다. Applied Materials도 FY26 Q3 매출 $9.12bn과 기록적 EPS를 발표했다. [S4][S5]'),
  p('[INFERENCE] 그런데 장비주는 현재 반도체 매출이 아니라 내년·후년 팹 증설 속도에 가격이 반응한다. 고객이 CAPEX를 늘려도 장비 발주·설치·매출인식 시점이 분기별로 흔들리고, 중국 수출규제와 중국 DUV 국산화 우려가 추가 할인요인이다.'),
  p('[INFERENCE] 좋은 실적에도 주가가 빠졌다는 것은 시장 기대가 실적보다 더 빨랐다는 의미다. 장비주의 반등 조건은 단순 AI 수요가 아니라 ASML bookings, EUV/High-NA 출하, TSMC·메모리 업체 CAPEX 상향이 다시 가속되는 것이다.'),

  br(),
  h('Detailed Analysis 3 · E&C·전력은 왜 더 약했나',1),
  h('1. 수주는 좋지만 현금흐름이 멀리 있다',2),
  p('[FACT] GE Vernova는 Q2 주문 $24.2bn(+88% organic), backlog $176bn, 데이터센터 주문은 연초 이후 $5bn 이상이라고 밝혔다. Siemens Energy도 Gas Services·Grid Technologies 중심으로 기록적 주문과 이익을 발표했다. [S7][S8]'),
  p('[FACT] Comfort Systems는 Q2 매출 +50%, EPS +92%, backlog $14.06bn을 기록했고 데이터센터 중심 기술 부문 수요를 성장 원인으로 설명했다. [S9][S10]'),
  p('[INFERENCE] 따라서 최근 하락은 주문 붕괴로 설명되지 않는다. 수주가 매출이 되기까지 설계·허가·장비조달·시공·계통연결을 거쳐야 하고, 이 과정의 이익은 수년 뒤 인식된다. 장기금리가 오르면 이 먼 현금흐름의 현재가치가 크게 줄어든다.'),
  h('2. backlog의 크기보다 질이 중요하다',2),
  p('[FACT] Comfort Systems의 10-Q는 고정가격 계약의 원가추정 오류, 인력·자재 부족, 프로젝트 지연·취소, backlog가 매출과 이익으로 전환되지 못할 위험을 명시한다. [S10]'),
  p('[INFERENCE] 전력기기는 생산능력 부족이 가격결정력을 주지만 동시에 매출 전환의 병목이다. E&C는 인력과 프로젝트 수행이 병목이다. 시장이 지금 확인하려는 것은 신규수주가 아니라 backlog margin, 전환율, 운전자본과 FCF다.'),
  h('3. 유럽 정책은 장기 하방이지 단기 가속장치가 아니다',2),
  p('[INFERENCE] 유럽의 전력망·방산·인프라 정책은 수요의 기간을 늘리고 하방을 지지한다. 그러나 정책 발표가 이미 알려진 뒤에는 예산집행, 입찰, 허가, 선수금, 장비 인도 순으로 실제 EPS에 도달해야 한다.'),
  p('[INFERENCE] AI는 데이터센터 주문을 앞당기는 가속장치지만 유럽 데이터센터 규모와 프로젝트 속도는 미국보다 작다. 그래서 유럽 상장 전력주는 유럽 재정만이 아니라 미국 hyperscaler CAPEX와 미국 장기금리에 더 민감할 수 있다.'),

  br(),
  h('상대선호와 모니터링',1),
  table(['구간','현재 해석','반등 확인 지표','리스크'],[
    ['HBM·메모리','현재 이익과 가격결정력이 가장 선명','HBM 계약가격·할당, 수율, DRAM ASP, 고객 재고','공급증설·가격 피크'],
    ['파운드리','수요 강하지만 CAPEX·해외팹 비용 동반','첨단공정 가동률, N2 수율, CAPEX, FCF','마진 희석·성숙공정 약세'],
    ['반도체 장비','장기 moat는 강하나 기대치와 중국 리스크 부담','ASML bookings, EUV/High-NA 출하, 고객 CAPEX 상향','수출규제·발주 변동성'],
    ['E&C','backlog는 강하지만 실행·인력·원가가 관건','유기적 book-to-bill, backlog margin, 현금전환','고정가 계약·취소·인력'],
    ['전력·냉각','수요는 구조적, 주가는 장기금리·멀티플 민감','주문→매출 전환, 장비 인도, FCF, 장기금리','capacity 병목·과도한 기대'],
    ['EU 복합 전력·자동화','현재 실적·포트폴리오 분산으로 상대방어','Energy Mgmt 성장, 마진, 북미·유럽 주문','글로벌 경기·통화'],
  ],[2100,4400,4800,3900]),
  h('투자 해석',2),
  p('[INFERENCE] 네가 본 유럽 전력·인프라 수혜 논리는 틀리지 않았다. 다만 지금은 테마 방향보다 가격과 시간축의 문제다. 정책은 duration을 제공하지만 주가 재가속에는 EPS 상향과 FCF 전환이 필요하다.'),
  p('[INFERENCE] 단기 안정성은 Schneider·Siemens·ABB 같은 복합 전력·자동화가 상대적으로 낫고, Siemens Energy·GE Vernova·FIX·PWR는 더 높은 업사이드와 더 큰 할인율 베타를 가진다.'),
  p('[SPECULATION] 주장: 전력·E&C를 버릴 구간이라기보다, 장기금리 안정과 backlog-to-revenue 전환이 확인될 때까지 순수 고베타보다 복합 사업자를 코어로 두고 순수 수혜주는 비중을 조절하는 접근이 합리적이다.'),

  h('Risks & Counterarguments',1),
  p('[RISK] 메모리가 현재 가장 잘 보여도 사이클 피크에서의 이익이 가장 과대평가될 수 있다. 장기 moat는 ASML·KLA 같은 장비업체가 더 강할 수 있다.'),
  p('[RISK] 금리가 빠르게 안정되고 hyperscaler CAPEX가 다시 상향되면 E&C·전력의 최근 조정은 짧은 포지션 정리로 끝나며 고베타 종목이 가장 빠르게 반등할 수 있다.'),
  p('[RISK] 유럽 정책 집행이 예상보다 빨라지거나 미국 전력 병목이 심화되면 장비 가격과 프로젝트 마진이 추가 상승할 수 있다.'),
  br(),
  h('Open Questions',1),
  p('[OPEN QUESTION] ASML의 다음 분기 bookings와 중국 매출 감소를 AI·메모리 발주가 얼마나 상쇄하는가?'),
  p('[OPEN QUESTION] Siemens Energy·GE Vernova의 대규모 backlog가 기존 예상보다 높은 마진과 FCF로 전환되는가?'),
  p('[OPEN QUESTION] 유럽 전력망 정책의 예산·입찰·선수금이 2027 EPS 추정치 상향으로 연결되는가?'),
  p('[OPEN QUESTION] HBM 가격과 일반 DRAM 가격의 동반 상승이 공급 증설 이후에도 유지되는가?'),

  br(),
  h('Sources',1),
  ...sources.map(([code,name,url])=>new Paragraph({children:url.startsWith('http')?[run(`${code} · ${name}: `,{size:16,bold:true}),new ExternalHyperlink({link:url,children:[run(url,{size:16,color:C.blue})]})]:[run(`${code} · ${name}: ${url}`,{size:16})],spacing:{after:80,line:235}})),
];

const doc=new Document({creator:'OpenAI Codex',title:'AI 하드웨어 내부 차별화',description:'메모리, 파운드리·장비, E&C·전력의 최근 가격과 실적 차별화 분석',styles:{default:{document:{run:{font:'Malgun Gothic',size:19,color:C.navy},paragraph:{spacing:{line:270}}}},paragraphStyles:[{id:'Heading1',name:'Heading 1',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:32,bold:true,color:C.navy},paragraph:{spacing:{before:210,after:110},outlineLevel:0}},{id:'Heading2',name:'Heading 2',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:25,bold:true,color:C.blue},paragraph:{spacing:{before:150,after:95},outlineLevel:1}},{id:'Heading3',name:'Heading 3',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:21,bold:true,color:C.teal},paragraph:{spacing:{before:130,after:85},outlineLevel:2}}]},sections:[{properties:{page:{size:{width:11906,height:16838,orientation:PageOrientation.LANDSCAPE},margin:{top:650,right:650,bottom:650,left:650}}},footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:[run('AI Hardware Differentiation  |  ',{size:14,color:C.gray,font:'Aptos'}),new TextRun({children:[PageNumber.CURRENT],size:14,color:C.gray,font:'Aptos'})]})]})},children:body}]});

Packer.toBuffer(doc).then(buf=>{fs.writeFileSync(outPath,buf);console.log(outPath);});
