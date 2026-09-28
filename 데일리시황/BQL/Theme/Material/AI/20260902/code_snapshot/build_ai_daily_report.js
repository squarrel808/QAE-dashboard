const fs = require('fs');
const path = require('path');
const {
  AlignmentType, BorderStyle, Document, ExternalHyperlink, Footer, Header,
  HeadingLevel, PageBreak, PageNumber, Packer, Paragraph, ShadingType,
  Table, TableCell, TableRow, TextRun, WidthType,
} = require('docx');

const ROOT = 'C:\\Users\\infomax\\Documents\\python\\BQL\\Theme\\output\\AI_Rotation';
const DATA_PATH = path.join(ROOT, 'US_AI_Value_Chain_Data_20260902.json');
const OUT_PATH = path.join(ROOT, '미국_AI_밸류체인_3개월_및_1일_분석_20260902.docx');
const data = JSON.parse(fs.readFileSync(DATA_PATH, 'utf8'));

const C={navy:'17365D',blue:'2F75B5',pale:'EAF2F8',line:'B4C7DC',gray:'666666',light:'F3F5F7',red:'C00000',green:'008000',amber:'9C6500',white:'FFFFFF',black:'111111'};
const pct=(v,d=1)=>v==null||!Number.isFinite(v)?'—':`${v>=0?'+':''}${(v*100).toFixed(d)}%`;
const pp=(v,d=1)=>v==null||!Number.isFinite(v)?'—':`${v>=0?'+':''}${(v*100).toFixed(d)}%p`;
const run=(text,o={})=>new TextRun({text:String(text),font:'Malgun Gothic',size:o.size||18,bold:!!o.bold,italics:!!o.italics,color:o.color||C.black});
const p=(text,o={})=>new Paragraph({alignment:o.align||AlignmentType.LEFT,spacing:{before:o.before||0,after:o.after??90,line:o.line||276},keepNext:!!o.keepNext,children:[run(text,o)]});
const h=(text,level=HeadingLevel.HEADING_1)=>new Paragraph({text,heading:level,keepNext:true,spacing:{before:180,after:90}});
const pageBreak=()=>new Paragraph({children:[new PageBreak()]});
function tagged(text){let color=C.black;if(text.startsWith('[FACT]'))color=C.navy;if(text.startsWith('[RISK]'))color=C.red;if(text.startsWith('[OPEN QUESTION]'))color=C.amber;return p(text,{color});}
function cell(text,width,o={}){return new TableCell({width:{size:width,type:WidthType.DXA},shading:o.fill?{fill:o.fill,type:ShadingType.CLEAR}:undefined,margins:{top:55,bottom:55,left:65,right:65},children:[new Paragraph({alignment:o.align||AlignmentType.LEFT,children:[run(text,{size:o.size||14,bold:o.bold,color:o.color})]})]});}
function mkTable(rows,widths){return new Table({width:{size:widths.reduce((a,b)=>a+b,0),type:WidthType.DXA},columnWidths:widths,rows,borders:{top:{style:BorderStyle.SINGLE,size:4,color:C.line},bottom:{style:BorderStyle.SINGLE,size:4,color:C.line},left:{style:BorderStyle.SINGLE,size:4,color:C.line},right:{style:BorderStyle.SINGLE,size:4,color:C.line},insideHorizontal:{style:BorderStyle.SINGLE,size:2,color:'D9E2F3'},insideVertical:{style:BorderStyle.SINGLE,size:2,color:'D9E2F3'}}});}
function placeholder(title,message){return new Paragraph({spacing:{before:110,after:140},border:{left:{style:BorderStyle.SINGLE,size:18,color:C.blue}},shading:{fill:C.pale,type:ShadingType.CLEAR},children:[run(`[그래프 삽입 위치] ${title}`,{bold:true,color:C.blue}),run(` — ${message}`,{color:C.gray})]});}
function linkParagraph(id,title,publisher,date,url){return new Paragraph({spacing:{after:70},children:[run(`${id} · ${title} · ${publisher} · ${date} · `,{bold:true,color:C.navy,size:15}),new ExternalHyperlink({link:url,children:[new TextRun({text:'원문',font:'Malgun Gothic',size:15,color:C.blue,underline:{}})]})]});}
function contributionList(items){return items.map(x=>`${x.ticker} ${pp(x.contribution)}`).join(' / ');}
function stageTable(stages){
  const widths=[2100,720,800,800,800,800,800,820,720];
  const headers=['밸류체인','종목수','1D','월1','월2','월3','3M','3M MDD','1D breadth'];
  const rows=[new TableRow({tableHeader:true,children:headers.map((x,i)=>cell(x,widths[i],{fill:C.navy,color:C.white,bold:true,align:AlignmentType.CENTER}))})];
  stages.forEach(s=>rows.push(new TableRow({children:[
    cell(s.name,widths[0]),cell(s.members,widths[1],{align:AlignmentType.CENTER}),
    cell(pct(s.return1d),widths[2],{align:AlignmentType.RIGHT,color:s.return1d<0?C.red:C.green}),
    cell(pct(s.month1),widths[3],{align:AlignmentType.RIGHT}),cell(pct(s.month2),widths[4],{align:AlignmentType.RIGHT}),cell(pct(s.month3),widths[5],{align:AlignmentType.RIGHT}),
    cell(pct(s.return3m),widths[6],{align:AlignmentType.RIGHT,color:s.return3m<0?C.red:C.green}),cell(pct(s.maxDrawdown3m),widths[7],{align:AlignmentType.RIGHT}),cell(pct(s.breadth1d),widths[8],{align:AlignmentType.RIGHT}),
  ]})));
  return mkTable(rows,widths);
}
function rankTable(stages,key,title){
  const sorted=[...stages].sort((a,b)=>b[key]-a[key]);
  const widths=[620,2800,1050,1000,1000];
  const rows=[new TableRow({tableHeader:true,children:['순위','밸류체인',title,'1D breadth','3M MDD'].map((x,i)=>cell(x,widths[i],{fill:C.navy,color:C.white,bold:true,align:AlignmentType.CENTER}))})];
  sorted.forEach((s,i)=>rows.push(new TableRow({children:[cell(i+1,widths[0],{align:AlignmentType.CENTER}),cell(s.name,widths[1]),cell(pct(s[key]),widths[2],{align:AlignmentType.RIGHT,color:s[key]<0?C.red:C.green}),cell(pct(s.breadth1d),widths[3],{align:AlignmentType.RIGHT}),cell(pct(s.maxDrawdown3m),widths[4],{align:AlignmentType.RIGHT})]})));
  return mkTable(rows,widths);
}
function membersFor(stageKey){return data.stocks.filter(x=>x.stageKey===stageKey).map(x=>x.ticker).join(', ');}

const spx=data.benchmarks.SPX_share_weight_proxy;
const ndx=data.benchmarks.NDX_share_weight_proxy;
const stages=[...data.stages].sort((a,b)=>b.return3m-a.return3m);
const best=stages[0], worst=stages[stages.length-1];
const positive3m=stages.filter(s=>s.return3m>0).length;
const positive1d=stages.filter(s=>s.return1d>0).length;

const sources=[
  ['M1','BQuant_Master.xlsx','사용자 제공 Bloomberg BQuant 원자료','2026-09-03 갱신','로컬 파일'],
  ['S1','Wall Street rises as tech stocks climb','Associated Press','2026-09-02','https://apnews.com/article/27b78c349725ac744c96a6b8b8167bae'],
  ['S2','Salesforce FY27 Q2 earnings','Salesforce','2026-08-26','https://www.salesforce.com/news/press-releases/2026/08/26/fy27-q2-earnings/'],
  ['S3','NVIDIA fiscal Q2 2027 results','NVIDIA','2026','https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Second-Quarter-Fiscal-2027/default.aspx'],
  ['S4','Palo Alto Networks fiscal Q4 and FY2026 results','Palo Alto Networks','2026-09-01','https://investors.paloaltonetworks.com/news-releases/news-release-details/palo-alto-networks-reports-fiscal-fourth-quarter-and-fiscal-10'],
  ['S5','Marvell fiscal Q2 2027 results','Marvell Technology','2026-08-27','https://investor.marvell.com/news-events/press-releases/detail/1031/marvell-technology-inc-reports-second-quarter-of-fiscal-year-2027-financial-results'],
  ['S6','Amphenol two-for-one stock split','Amphenol','2026','https://investor.amphenol.com/news-and-events/news-details/2026/Amphenol-Announces-Two-for-One-Stock-Split-and-Third-Quarter-2026-Dividend/default.aspx'],
];

const children=[];
children.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:760,after:200},children:[run('미국 AI 밸류체인',{size:38,bold:true,color:C.navy})]}));
children.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:190},children:[run('최근 3개월 로테이션 및 최근 1거래일 분석',{size:30,bold:true,color:C.blue})]}));
children.push(p(`기준일 ${data.meta.asOf} · ${data.meta.members}종목 · 12개 밸류체인`,{align:AlignmentType.CENTER,size:20,color:C.gray}));
children.push(p('S&P 500 현행 구성종목 내 Expanded(Core + Adjacent) 분류 · 주식수 가중 집계가격',{align:AlignmentType.CENTER,size:18,color:C.gray}));
children.push(p('[FACT] 최신 BQuant 원자료를 자동 병합한 뒤 기업행위 연속성 검사를 거쳐 계산했다.',{before:700,color:C.navy}));
children.push(p('[RISK] 테마 분류와 주식수 가중 집계가격은 분석용 프록시이며 거래가능 지수·ETF의 공식 수익률이 아니다.',{color:C.red}));
children.push(pageBreak());

children.push(h('Executive Summary'));
children.push(tagged(`[FACT] 3개월(${data.meta.start3m}→${data.meta.asOf}) 동안 12개 밸류체인 중 플러스는 ${positive3m}개뿐이다. ${best.name}가 ${pct(best.return3m)}로 유일한 플러스였고, ${worst.name}가 ${pct(worst.return3m)}로 최하위였다. [M1]`));
children.push(tagged(`[FACT] 같은 구간 S&P 500 구성종목 주식수 가중 집계가격 프록시는 ${pct(spx.return3mShareWeightProxy)}, NASDAQ 100 프록시는 ${pct(ndx.return3mShareWeightProxy)}였다. 따라서 ${best.name}의 상대수익률은 각각 ${pp(best.return3m-spx.return3mShareWeightProxy)}, ${pp(best.return3m-ndx.return3mShareWeightProxy)}다.`));
children.push(tagged(`[FACT] 최근 1일에는 12개 중 ${positive1d}개가 상승했다. 하드웨어·전력 일부가 소폭 반등했지만 ${stages.filter(s=>s.return1d<0).sort((a,b)=>a.return1d-b.return1d).slice(0,3).map(s=>`${s.name} ${pct(s.return1d)}`).join(', ')}는 약했다.`));
children.push(tagged('[INFERENCE] 3개월 흐름은 “AI 전체의 동반 상승”이 아니라 소프트웨어·데이터의 회복과 하드웨어/인프라 체인의 디레이팅이 병존한 내부 로테이션이다. 최근 1일의 일부 하드웨어 반등은 추세 전환을 확정하기에 규모와 breadth가 아직 작다.'));
children.push(tagged('[RISK] S&P 500과 NASDAQ 100 비교치는 ETF(SPY·QQQ)가 아니라 현재 구성종목의 주식수 가중 집계가격 프록시다. 배당·자유유통비율·지수 캡을 포함한 공식 지수와 차이가 날 수 있다.'));
children.push(placeholder('AI 밸류체인 3M 수익률 순위','S&P 500 및 NASDAQ 100 프록시 기준선을 함께 표시'));

children.push(h('핵심 결론'));
children.push(tagged('[FACT] AI 소프트웨어·데이터는 첫 달 -14.3% 이후 두 번째 달 +6.0%, 세 번째 달 +12.4%로 회복해 3개월 +2.2%를 기록했다. [M1]'));
children.push(tagged('[FACT] 네트워크·광통신, 엣지·Physical AI, AI 컴퓨팅·메모리, 파운드리·반도체 장비·EDA는 모두 3개월 두 자릿수 하락했다. [M1]'));
children.push(tagged('[INFERENCE] 시장은 AI CAPEX 총액 자체보다 매출 전환 속도, 주문의 지속성, 고객 집중도, 높은 사전 기대를 차별화하고 있다. 소프트웨어의 회복은 상용화 신호에, 하드웨어의 약세는 기대 선반영과 공급망별 병목 완화 우려에 민감하다.'));
children.push(tagged('[OPEN QUESTION] 향후 4주에 하드웨어 체인의 breadth가 50%를 넘고, 3개월 상대수익률 저점이 높아지는지 확인해야 순환적 반등을 구조적 리더십 변화로 판단할 수 있다.'));
children.push(pageBreak());

children.push(h('Methodology & Classification'));
children.push(tagged(`[FACT] 분석 기간은 3개월 ${data.meta.start3m}→${data.meta.asOf}, 최근 1일 ${data.meta.previous}→${data.meta.asOf}다. 월별 경계는 ${data.meta.monthBoundaries.join(' / ')}다.`));
children.push(tagged('[FACT] 각 체인의 집계가격은 Σ(종목가격×주식수)/Σ주식수로 계산한다. 현재 원자료에 주식수 필드가 없어 주식수는 시가총액/가격으로 역산한다. 3M MDD는 이 집계가격의 고점 대비 최대 하락률이다.'));
children.push(tagged('[FACT] 1D breadth는 해당 체인에서 당일 상승한 유효 종목 수를 전체 유효 종목 수로 나눈 비율이다.'));
children.push(tagged('[ASSUMPTION] Expanded 분류는 직접 AI 매출 노출(Core)과 전력·냉각·E&C·데이터센터 등 인접 인프라(Adjacent)를 함께 포함한다. 한 종목은 주된 경제적 노출 한 곳에만 배정했다.'));
children.push(tagged('[RISK] 최근 구성종목을 과거 3개월에 소급한 current-constituent 방식이므로 생존편향이 있다. 분류 경계가 다른 투자자의 정의와 다를 수 있다.'));
children.push(tagged('[FACT] APH는 2대1 주식분할 때문에 조정·비조정 가격이 섞인 구간을 보고서 계산용 복사본에서 정규화했다. 원본 파일은 변경하지 않았다. [S6]'));
children.push(stageTable(stages));
children.push(pageBreak());

children.push(h('3개월 강도 순위'));
children.push(rankTable(stages,'return3m','3M 수익률'));
children.push(placeholder('3개월 체인별 수익률·MDD','수익률 내림차순, MDD를 보조 마커로 표시'));
children.push(h('최근 1일 강도 순위'));
children.push(rankTable(stages,'return1d','1D 수익률'));
children.push(tagged('[INFERENCE] 1일 상승 체인이 다수더라도 3개월 누적 하락을 되돌리기에는 폭이 작다. 당일 신호는 방향 전환의 초기 후보로만 취급하고, breadth와 4주 상대강도의 후속 확인이 필요하다.'));
children.push(pageBreak());

children.push(h('월별 로테이션'));
const widths=[2100,900,900,900,900,900];
const rows=[new TableRow({tableHeader:true,children:['밸류체인','월1','월2','월3','3M','월별 패턴'].map((x,i)=>cell(x,widths[i],{fill:C.navy,color:C.white,bold:true,align:AlignmentType.CENTER}))})];
for(const s of stages){
  let pattern='혼조';
  if(s.month1<0&&s.month2>0&&s.month3>0)pattern='저점 후 회복';
  else if(s.month1<0&&s.month2<0&&s.month3>0)pattern='최근 반등';
  else if(s.month1>0&&s.month2<0&&s.month3<0)pattern='초기 강세 소멸';
  else if(s.month1<0&&s.month2<0&&s.month3<0)pattern='연속 약세';
  rows.push(new TableRow({children:[cell(s.name,widths[0]),cell(pct(s.month1),widths[1],{align:AlignmentType.RIGHT}),cell(pct(s.month2),widths[2],{align:AlignmentType.RIGHT}),cell(pct(s.month3),widths[3],{align:AlignmentType.RIGHT}),cell(pct(s.return3m),widths[4],{align:AlignmentType.RIGHT}),cell(pattern,widths[5],{align:AlignmentType.CENTER})]}));
}
children.push(mkTable(rows,widths));
children.push(tagged('[INFERENCE] 가장 중요한 변화는 소프트웨어·데이터가 첫 달 급락을 완전히 복구했고, 반대로 장비·네트워크의 회복이 제한적이었다는 점이다. 하이퍼스케일러는 세 번째 달 +3.0%였지만 3개월 누적 -11.2%로 아직 중립 이하의 흐름이다.'));
children.push(placeholder('월1·월2·월3 체인별 히트맵','행=밸류체인, 열=월 구간, 동일 색상축 사용'));
children.push(pageBreak());

children.push(h('밸류체인별 상세'));
for(const s of stages){
  children.push(h(`${s.name} · ${s.members}종목`,HeadingLevel.HEADING_2));
  children.push(tagged(`[FACT] 1D ${pct(s.return1d)}, 3M ${pct(s.return3m)}, 3M MDD ${pct(s.maxDrawdown3m)}, 1D 상승 breadth ${pct(s.breadth1d)}.`));
  children.push(tagged(`[FACT] 1D 상위 기여: ${contributionList(s.top1d)}. 1D 하위 기여: ${contributionList(s.bottom1d)}.`));
  children.push(tagged(`[FACT] 3M 상위 기여: ${contributionList(s.top3m)}. 3M 하위 기여: ${contributionList(s.bottom3m)}.`));
  children.push(p(`구성종목: ${membersFor(s.key)}`,{size:15,color:C.gray}));
  let inference='단기 방향과 3개월 추세가 엇갈려 확인이 필요하다.';
  if(s.return3m>0&&s.return1d<0)inference='3개월 리더지만 최근 1일은 차익실현 성격이 나타났다.';
  else if(s.return3m<0&&s.return1d>0)inference='3개월 약세 속 기술적 반등 후보지만 추세 전환 확인이 필요하다.';
  else if(s.return3m<0&&s.return1d<0)inference='중기 약세가 최근 1일에도 이어져 상대강도 회복 신호가 부족하다.';
  children.push(tagged(`[INFERENCE] ${inference}`));
}
children.push(pageBreak());

children.push(h('펀더멘털 체크: 가격과 실적의 분리'));
children.push(tagged('[FACT] Salesforce는 cRPO +14%(constant currency), 상향된 매출 가이던스와 Agentforce 성장 지표를 발표했다. [S2] [INFERENCE] 소프트웨어 체인의 3개월 회복은 단순 멀티플 반등만이 아니라 계약·상용화 지표 확인과 연결된다.'));
children.push(tagged('[FACT] NVIDIA는 분기 매출 962억 달러(+106%), 데이터센터 매출 890억 달러(+117%)를 발표했다. [S3] [INFERENCE] 강한 실적에도 컴퓨팅·메모리 체인의 3개월 약세가 지속된 것은 절대 성장보다 사전 기대와 밸류에이션이 더 높았음을 시사한다.'));
children.push(tagged('[FACT] Marvell은 매출 +37%, 데이터센터 +46%와 상향 가이던스를 발표했다. [S5] [INFERENCE] 10D 약세와 병존한다는 점에서 AI 하드웨어는 beat 자체보다 주문 믹스·마진·기대치가 중요하다.'));
children.push(tagged('[FACT] Palo Alto Networks는 매출 +34%, NGS ARR +63%를 발표했지만 최근 1일 -7.9%였다. [S4] [INFERENCE] 사이버보안도 강한 구조적 성장과 단기 기대 조정이 동시에 가능하다.'));
children.push(tagged('[OPEN QUESTION] 다음 실적 시즌에는 CAPEX 증가율보다 AI 매출의 인식 시점, 백로그 전환, 총마진, 고객 집중도, FCF를 체인별로 비교해야 한다.'));
children.push(placeholder('가격 수익률 vs 실적·가이던스 확인 매트릭스','소프트웨어·컴퓨팅·네트워크·사이버보안의 가격/펀더멘털 괴리 표시'));

children.push(pageBreak());
children.push(h('리스크 및 모니터링 대시보드'));
const monitorWidths=[2300,2500,2600];
const monitorRows=[new TableRow({tableHeader:true,children:['관찰 변수','강세 확인 조건','경고 신호'].map((x,i)=>cell(x,monitorWidths[i],{fill:C.navy,color:C.white,bold:true,align:AlignmentType.CENTER}))})];
[
  ['체인별 4주 상대강도','S&P 500 프록시 대비 2개 구간 연속 개선','하루 반등 후 상대저점 재하락'],
  ['상승 breadth','50% 이상 및 상·하위 종목 기여 분산','1~2개 대형 이벤트에 집중'],
  ['실적 추정치','매출·EPS 상향과 가격 상승 동행','가격만 반등하고 EPS 정체'],
  ['AI CAPEX 수익화','백로그→매출 전환 및 마진 방어','CAPEX 증가 대비 FCF·마진 악화'],
  ['기업행위 QA','가격·시총·분할 계수의 연속성','가격 2배/절반 변화와 시총 불일치'],
].forEach(r=>monitorRows.push(new TableRow({children:r.map((x,i)=>cell(x,monitorWidths[i]))})));
children.push(mkTable(monitorRows,monitorWidths));
children.push(tagged('[RISK] 주식수 가중 집계가격은 자유유통주식수·지수 divisor·공식 기업행위 조정을 반영한 공식 지수가 아니다. 단기 순위는 종목 구성과 주식수 변화에 민감하다.'));
children.push(tagged('[RISK] 가격수익률만 사용하므로 배당과 환율은 제외된다. 테마별 실적 추정치·밸류에이션 자료를 추가하면 가격 로테이션의 지속 가능성을 더 정확히 판단할 수 있다.'));
children.push(tagged('[RISK] 종목별 기여도는 구간 시작일 주식수×가격변화로 계산한 근사치다. 구간 중 주식수 변화 때문에 표시 기여도의 합이 체인 누적수익률과 정확히 일치하지 않을 수 있다.'));
children.push(tagged('[OPEN QUESTION] 데이터 업데이트 시 1D·1M·3M 순위, breadth, MDD, 벤치마크 대비 상대수익률이 함께 개선되는 체인을 우선 모니터링한다.'));

children.push(pageBreak());
children.push(h('Sources'));
children.push(p('시장 데이터는 사용자 제공 BQuant 파일을 사용했다. 외부 자료는 가격 신호와 실적·기업행위의 연결을 점검하는 데 사용했다.',{color:C.gray}));
for(const s of sources){if(s[4]==='로컬 파일')children.push(p(`${s[0]} · ${s[1]} · ${s[2]} · ${s[3]} · 로컬 원자료`,{size:15,color:C.navy}));else children.push(linkParagraph(...s));}

const doc=new Document({
  creator:'OpenAI Codex',title:'미국 AI 밸류체인 최근 3개월 및 1일 분석',description:'S&P 500 AI value-chain shares-weighted aggregate-price rotation report',
  styles:{default:{document:{run:{font:'Malgun Gothic',size:18},paragraph:{spacing:{line:276}}}},paragraphStyles:[
    {id:'Heading1',name:'Heading 1',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:28,bold:true,color:C.navy},paragraph:{spacing:{before:220,after:110},outlineLevel:0}},
    {id:'Heading2',name:'Heading 2',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:22,bold:true,color:C.blue},paragraph:{spacing:{before:170,after:80},outlineLevel:1}},
    {id:'Heading3',name:'Heading 3',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:19,bold:true,color:C.navy},paragraph:{spacing:{before:140,after:70},outlineLevel:2}},
  ]},
  sections:[{properties:{page:{size:{width:16838,height:11906,orientation:'landscape'},margin:{top:650,right:680,bottom:650,left:680}}},headers:{default:new Header({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:[run('US AI Value Chain · 2026-09-02',{size:13,color:C.gray})]})]})},footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[run('Confidential · ',{size:13,color:C.gray}),new TextRun({children:[PageNumber.CURRENT],font:'Malgun Gothic',size:13,color:C.gray})]})]})},children}],
});

Packer.toBuffer(doc).then(buf=>{fs.writeFileSync(OUT_PATH,buf);console.log(OUT_PATH);});
