const fs = require('fs');
const path = require('path');
const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel,
  PageBreak, PageNumber, Packer, Paragraph, ShadingType, Table, TableCell,
  TableRow, TextRun, WidthType,
} = require('docx');

function parseArgs() {
  const result = {};
  for (let i = 2; i < process.argv.length; i += 1) {
    if (process.argv[i].startsWith('--')) result[process.argv[i].slice(2)] = process.argv[++i];
  }
  return result;
}

const cli = parseArgs();
if (!cli.data || !cli.period) {
  throw new Error('Usage: node generate_ai_period_report.js --data <json> --period <1D|1W|1M3M> [--output-dir <dir>]');
}
const period = String(cli.period).toUpperCase();
if (!['1D', '1W', '1M3M'].includes(period)) throw new Error(`Unsupported period: ${period}`);
const data = JSON.parse(fs.readFileSync(path.resolve(cli.data), 'utf8'));
const asOfTag = data.meta.asOf.replaceAll('-','');
const outputRoot = path.resolve(
  cli['output-dir'] || path.join(__dirname, '..', '..', 'output', asOfTag, 'AI')
);

const C = {navy:'17365D',blue:'2F75B5',pale:'EAF2F8',line:'B4C7DC',gray:'666666',red:'C00000',green:'008000',amber:'9C6500',white:'FFFFFF',black:'111111'};
const pct = (v,d=1) => v == null || !Number.isFinite(v) ? '—' : `${v>=0?'+':''}${(v*100).toFixed(d)}%`;
const pp = (v,d=1) => v == null || !Number.isFinite(v) ? '—' : `${v>=0?'+':''}${(v*100).toFixed(d)}%p`;
const fmt = v => new Intl.NumberFormat('ko-KR').format(v);
const tr = (text,o={}) => new TextRun({text:String(text),font:'Malgun Gothic',size:o.size||18,bold:!!o.bold,italics:!!o.italics,color:o.color||C.black});
const p = (text,o={}) => new Paragraph({alignment:o.align||AlignmentType.LEFT,spacing:{before:o.before||0,after:o.after??90,line:o.line||276},keepNext:!!o.keepNext,children:[tr(text,o)]});
const h = (text,level=HeadingLevel.HEADING_1) => new Paragraph({text,heading:level,keepNext:true,spacing:{before:180,after:90}});
const pageBreak = () => new Paragraph({children:[new PageBreak()]});
function rich(parts,o={}){return new Paragraph({spacing:{after:o.after??85,line:276},keepNext:!!o.keepNext,children:parts.map(x=>tr(x.text,x))});}
function cell(text,width,o={}){return new TableCell({width:{size:width,type:WidthType.DXA},shading:o.fill?{fill:o.fill,type:ShadingType.CLEAR}:undefined,margins:{top:o.pad||45,bottom:o.pad||45,left:55,right:55},children:[new Paragraph({alignment:o.align||AlignmentType.LEFT,children:[tr(text,{size:o.size||13,bold:o.bold,color:o.color})]})]});}
function mkTable(rows,widths){return new Table({width:{size:widths.reduce((a,b)=>a+b,0),type:WidthType.DXA},columnWidths:widths,rows,borders:{top:{style:BorderStyle.SINGLE,size:4,color:C.line},bottom:{style:BorderStyle.SINGLE,size:4,color:C.line},left:{style:BorderStyle.SINGLE,size:4,color:C.line},right:{style:BorderStyle.SINGLE,size:4,color:C.line},insideHorizontal:{style:BorderStyle.SINGLE,size:2,color:'D9E2F3'},insideVertical:{style:BorderStyle.SINGLE,size:2,color:'D9E2F3'}}});}
function callout(title,text){return new Paragraph({spacing:{before:80,after:110},border:{left:{style:BorderStyle.SINGLE,size:18,color:C.blue}},shading:{fill:C.pale,type:ShadingType.CLEAR},children:[tr(`${title}  `,{bold:true,color:C.blue}),tr(text)]});}
function state(short,medium){if(short>=0&&medium>=0)return'리더십 유지';if(short>=0&&medium<0)return'반등 전환';if(short<0&&medium>=0)return'최근 조정';return'약세 지속';}
function contribution(items){return items.map(x=>`${x.ticker} ${pp(x.contribution)}`).join(' / ');}

const cfg = {
  '1D': {title:'최근 1거래일',key:'return1d',breadth:'breadth1d',top:'top1d',bottom:'bottom1d',start:data.meta.previous,bench:'return1dShareWeightProxy'},
  '1W': {title:'최근 1주',key:'return1w',breadth:'breadth1w',top:'top1w',bottom:'bottom1w',start:data.meta.start1w,bench:'return1wShareWeightProxy'},
  '1M3M': {title:'최근 1개월·3개월',key:'return3m',breadth:'breadth1m',top:'top3m',bottom:'bottom3m',start:data.meta.start3m,bench:'return3mShareWeightProxy'},
}[period];
const outDir = outputRoot;
fs.mkdirSync(outDir,{recursive:true});
const outPath = path.join(outDir,`미국_AI_밸류체인_${period}_보고서_${asOfTag}.docx`);
const spx=data.benchmarks.SPX_share_weight_proxy;
const ndx=data.benchmarks.NDX_share_weight_proxy;

function contextTable(){
  const widths=[1940,500,740,740,740,740,720,760,760];
  const headers=['밸류체인','N','1D','1W','1M','3M','1M breadth','3M MDD','3M S&P 대비'];
  const rows=[new TableRow({tableHeader:true,children:headers.map((x,i)=>cell(x,widths[i],{fill:C.navy,color:C.white,bold:true,align:AlignmentType.CENTER,size:12}))})];
  const sorted=[...data.stages].sort((a,b)=>b[cfg.key]-a[cfg.key]);
  sorted.forEach(s=>rows.push(new TableRow({children:[
    cell(s.name,widths[0],{size:12}),cell(s.members,widths[1],{align:AlignmentType.CENTER,size:12}),
    cell(pct(s.return1d),widths[2],{align:AlignmentType.RIGHT,size:12,color:s.return1d<0?C.red:C.green}),
    cell(pct(s.return1w),widths[3],{align:AlignmentType.RIGHT,size:12,color:s.return1w<0?C.red:C.green}),
    cell(pct(s.return1m),widths[4],{align:AlignmentType.RIGHT,size:12,color:s.return1m<0?C.red:C.green}),
    cell(pct(s.return3m),widths[5],{align:AlignmentType.RIGHT,size:12,color:s.return3m<0?C.red:C.green}),
    cell(pct(s.breadth1m),widths[6],{align:AlignmentType.RIGHT,size:12}),cell(pct(s.maxDrawdown3m),widths[7],{align:AlignmentType.RIGHT,size:12}),
    cell(pp(s.return3m-spx.return3mShareWeightProxy),widths[8],{align:AlignmentType.RIGHT,size:12}),
  ]})));
  return mkTable(rows,widths);
}

function monthlyTable(){
  const widths=[2080,900,900,900,900,900,1200];
  const headers=['밸류체인','월1','월2','월3','1M','3M','판정'];
  const rows=[new TableRow({tableHeader:true,children:headers.map((x,i)=>cell(x,widths[i],{fill:C.navy,color:C.white,bold:true,align:AlignmentType.CENTER}))})];
  [...data.stages].sort((a,b)=>b.return3m-a.return3m).forEach(s=>rows.push(new TableRow({children:[
    cell(s.name,widths[0]),cell(pct(s.month1),widths[1],{align:AlignmentType.RIGHT}),cell(pct(s.month2),widths[2],{align:AlignmentType.RIGHT}),cell(pct(s.month3),widths[3],{align:AlignmentType.RIGHT}),
    cell(pct(s.return1m),widths[4],{align:AlignmentType.RIGHT}),cell(pct(s.return3m),widths[5],{align:AlignmentType.RIGHT}),cell(state(s.return1m,s.return3m),widths[6],{align:AlignmentType.CENTER}),
  ]})));
  return mkTable(rows,widths);
}

function stageDetail(stage){
  const current=stage[cfg.key];
  const benchmark=spx[cfg.bench];
  const stageStocks=data.stocks.filter(x=>x.stageKey===stage.key).sort((a,b)=>b[cfg.key]-a[cfg.key]);
  const top=stageStocks.slice(0,2).map(x=>`${x.ticker} ${pct(x[cfg.key])}`).join(', ');
  const bottom=stageStocks.slice(-2).reverse().map(x=>`${x.ticker} ${pct(x[cfg.key])}`).join(', ');
  const assessment=state(period==='1M3M'?stage.return1m:current,stage.return3m);
  return [
    h(`${stage.name} · ${assessment}`,HeadingLevel.HEADING_2),
    rich([{text:'역할  ',bold:true,color:C.blue},{text:stage.description}]),
    rich([{text:'성과  ',bold:true,color:C.blue},{text:`1D ${pct(stage.return1d)}, 1W ${pct(stage.return1w)}, 1M ${pct(stage.return1m)}, 3M ${pct(stage.return3m)}. 3M S&P 대비 ${pp(stage.return3m-spx.return3mShareWeightProxy)}, 최대낙폭 ${pct(stage.maxDrawdown3m)}.`}]),
    rich([{text:'내부 확산  ',bold:true,color:C.blue},{text:`1D 상승종목 ${pct(stage.breadth1d)}, 1W ${pct(stage.breadth1w)}, 1M ${pct(stage.breadth1m)}. ${cfg.title} 상위는 ${top}, 하위는 ${bottom}.`}]),
    rich([{text:'기여 종목  ',bold:true,color:C.blue},{text:`상위 ${contribution(stage[cfg.top])}. 하위 ${contribution(stage[cfg.bottom])}.`}]),
    rich([{text:'해석  ',bold:true,color:C.blue},{text:assessment==='리더십 유지'?'중기 상승과 최근 강세가 겹친다. 종목 breadth가 유지되면 리더십 신뢰도가 높아진다.':assessment==='반등 전환'?'중기 약세 속 반등이다. 다음 구간에서 S&P 대비 상대수익과 breadth가 재차 개선되는지 확인해야 한다.':assessment==='최근 조정'?'중기 리더가 최근 조정을 받는 구간이다. 실적 훼손인지 차익실현인지 종목별로 구분할 필요가 있다.':'중기와 최근 흐름이 모두 약하다. 소수 반등 종목보다 체인 전체의 추정치·주문 회복이 필요하다.'}]),
    p(`구성: ${stageStocks.map(x=>x.ticker).join(', ')}`,{size:14,color:C.gray,after:150}),
  ];
}

function stockUniverseTable(){
  const widths=[1120,700,1400,620,620,620,620,620,2980];
  const headers=['밸류체인','Ticker','회사','구분','1D','1W','1M','3M','AI 밸류체인 내 역할'];
  const rows=[new TableRow({tableHeader:true,children:headers.map((x,i)=>cell(x,widths[i],{fill:C.navy,color:C.white,bold:true,align:AlignmentType.CENTER,size:11}))})];
  const order=Object.fromEntries(data.stages.map((s,i)=>[s.key,i]));
  [...data.stocks].sort((a,b)=>order[a.stageKey]-order[b.stageKey]||a.ticker.localeCompare(b.ticker)).forEach(x=>rows.push(new TableRow({children:[
    cell(data.stages.find(s=>s.key===x.stageKey).short||x.stage,widths[0],{size:10}),cell(x.ticker,widths[1],{size:10,bold:true}),cell(x.name,widths[2],{size:10}),cell(x.confidence==='Core'?'핵심':'인접',widths[3],{size:10,align:AlignmentType.CENTER}),
    cell(pct(x.return1d),widths[4],{size:10,align:AlignmentType.RIGHT}),cell(pct(x.return1w),widths[5],{size:10,align:AlignmentType.RIGHT}),cell(pct(x.return1m),widths[6],{size:10,align:AlignmentType.RIGHT}),cell(pct(x.return3m),widths[7],{size:10,align:AlignmentType.RIGHT}),cell(x.rationale,widths[8],{size:10}),
  ]})));
  return mkTable(rows,widths);
}

const sorted=[...data.stages].sort((a,b)=>b[cfg.key]-a[cfg.key]);
const leaders=sorted.slice(0,3);
const laggards=sorted.slice(-3).reverse();
const positive=sorted.filter(s=>s[cfg.key]>0).length;
const children=[];

children.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:1450,after:220},children:[tr('미국 AI 밸류체인',{size:40,bold:true,color:C.navy})]}));
children.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:200},children:[tr(`${cfg.title} 로테이션과 시장 내러티브`,{size:28,bold:true,color:C.blue})]}));
children.push(p(`${cfg.start}~${data.meta.asOf} · S&P 500 ${fmt(data.meta.validMembers)}개 AI 관련 종목 · 12개 밸류체인`,{align:AlignmentType.CENTER,size:19,color:C.gray}));
children.push(p('전체 체인 성과 · 체인별 해설 · 전 종목 역할과 수익률',{align:AlignmentType.CENTER,size:17,color:C.gray,before:100}));
children.push(pageBreak());

children.push(h('Executive Summary'));
children.push(rich([{text:'리더십  ',bold:true,color:C.blue},{text:`${cfg.title} 상위는 ${leaders.map(s=>`${s.name} ${pct(s[cfg.key])}`).join(', ')}다. 하위는 ${laggards.map(s=>`${s.name} ${pct(s[cfg.key])}`).join(', ')}다.`}]));
children.push(rich([{text:'시장 폭  ',bold:true,color:C.blue},{text:`12개 체인 중 ${positive}개가 상승했다. S&P 500 구성종목 주식수 가중 집계가격 프록시는 ${pct(spx[cfg.bench])}, NASDAQ 100 프록시는 ${pct(ndx[cfg.bench])}다.`}]));
children.push(rich([{text:'로테이션 판단  ',bold:true,color:C.blue},{text:`중기 흐름까지 함께 보면 리더십 유지는 ${sorted.filter(s=>state(period==='1M3M'?s.return1m:s[cfg.key],s.return3m)==='리더십 유지').map(s=>s.name).join(', ')||'없음'}, 반등 전환은 ${sorted.filter(s=>state(period==='1M3M'?s.return1m:s[cfg.key],s.return3m)==='반등 전환').map(s=>s.name).join(', ')||'없음'}이다.`}]));
children.push(callout('발표 핵심',`AI 전체를 하나로 보지 말고, ${leaders[0].name}의 강세가 체인 전반으로 확산되는지와 ${laggards[0].name}의 약세가 실적 훼손인지 기대 조정인지 구분해야 한다.`));
children.push(h('전체 밸류체인 성과표'));
children.push(contextTable());
children.push(p('정렬 기준은 선택한 보고서 기간이다. 3M S&P 대비는 체인의 주식수 가중 집계가격 수익률에서 같은 방식의 S&P 500 프록시를 차감했다.',{size:13,color:C.gray}));
children.push(pageBreak());

children.push(h('Key Findings'));
children.push(rich([{text:'1. 상위 체인  ',bold:true,color:C.navy},{text:`${leaders[0].name}가 ${pct(leaders[0][cfg.key])}로 선두이며, 내부 상승 breadth는 ${pct(leaders[0][cfg.breadth])}다. 상위 기여는 ${contribution(leaders[0][cfg.top])}다.`}]));
children.push(rich([{text:'2. 하위 체인  ',bold:true,color:C.navy},{text:`${laggards[0].name}는 ${pct(laggards[0][cfg.key])}로 최하위이며 3개월 최대낙폭은 ${pct(laggards[0].maxDrawdown3m)}다. 하위 기여는 ${contribution(laggards[0][cfg.bottom])}다.`}]));
children.push(rich([{text:'3. 벤치마크 대비  ',bold:true,color:C.navy},{text:`선두 체인의 S&P 500 대비 초과수익은 ${pp(leaders[0][cfg.key]-spx[cfg.bench])}, 최하위 체인은 ${pp(laggards[0][cfg.key]-spx[cfg.bench])}다. 체인 간 스프레드는 ${pp(leaders[0][cfg.key]-laggards[0][cfg.key])}다.`}]));
children.push(rich([{text:'4. 투자 판단  ',bold:true,color:C.navy},{text:'수익률 방향만으로 결론내리지 않고 breadth, 상·하위 기여 집중도, 1개월과 3개월 방향의 일치 여부를 함께 본다. 하루·1주 반등은 중기 약세를 바로 뒤집는 신호가 아니다.'}]));
if(period==='1M3M'){
  children.push(h('월별 로테이션'));
  children.push(monthlyTable());
}
children.push(callout('다음 확인','상위 체인의 상승 종목 수가 늘고, S&P 500 대비 상대수익률이 다음 기간에도 플러스인지 확인한다.'));
children.push(pageBreak());

children.push(h('전체 밸류체인 해설'));
for(const stage of sorted) children.push(...stageDetail(stage));
children.push(pageBreak());

children.push(h('전 종목 수익률과 AI 밸류체인 내 역할'));
children.push(p('아래 표는 분석 대상 전 종목을 빠짐없이 수록한다. 핵심은 해당 체인에 직접 노출된 종목, 인접은 의미 있는 2차 수혜 종목이다.',{color:C.gray}));
children.push(stockUniverseTable());
children.push(pageBreak());

children.push(h('활용 방법과 계산 정의'));
children.push(h('발표에서 먼저 볼 순서',HeadingLevel.HEADING_2));
children.push(p('① 전체 성과표에서 선택 기간의 상·하위 체인과 스프레드를 확인한다. ② 체인 해설에서 breadth와 기여 종목을 확인한다. ③ 전 종목 표에서 체인 성과가 특정 종목 한두 개에 집중됐는지 점검한다. ④ 1개월과 3개월 방향이 같을 때만 중기 리더십으로 해석한다.'));
children.push(h('기간 정의',HeadingLevel.HEADING_2));
children.push(p(`1D=${data.meta.previous}→${data.meta.asOf}. 1W=${data.meta.start1w}→${data.meta.asOf}. 1M=${data.meta.start1m}→${data.meta.asOf}. 3M=${data.meta.start3m}→${data.meta.asOf}. 시작일은 목표일 이하의 가장 가까운 유효 거래일이다.`));
children.push(h('지수·기여도',HeadingLevel.HEADING_2));
children.push(p('밸류체인 집계가격은 Σ(종목가격×주식수)/Σ주식수로 계산하고 그 기간 변화율을 수익률로 사용한다. 현재 원자료에 주식수 필드가 없어 주식수는 시가총액/가격으로 역산한다. 종목 기여도는 구간 시작일 주식수×가격변화를 이용한 설명용 근사치다. 배당과 환율 효과는 제외한다.'));
children.push(h('데이터 주의사항',HeadingLevel.HEADING_2));
children.push(p('현재 S&P 500 구성종목을 과거에 소급하므로 생존편향이 있다. S&P 500·NASDAQ 100 비교치는 주식수 가중 구성종목 집계가격 프록시이며 공식 지수·ETF 총수익률이 아니다. 기업행위는 가격·시총 연속성으로 검사하고 원본 Master는 변경하지 않는다.',{color:C.gray}));
children.push(p(`원자료: ${data.meta.source || 'BQL\\Rawfile\\BQuant_Master.xlsx'} · 계산 JSON: ${path.resolve(cli.data)}`,{size:14,color:C.gray}));

const doc=new Document({
  creator:'OpenAI Codex',title:`미국 AI 밸류체인 ${cfg.title} 보고서`,description:'BQuant AI value-chain performance, sector commentary and full constituent appendix',
  styles:{default:{document:{run:{font:'Malgun Gothic',size:18},paragraph:{spacing:{line:276}}}},paragraphStyles:[
    {id:'Heading1',name:'Heading 1',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:28,bold:true,color:C.navy},paragraph:{spacing:{before:220,after:110},outlineLevel:0}},
    {id:'Heading2',name:'Heading 2',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Malgun Gothic',size:21,bold:true,color:C.blue},paragraph:{spacing:{before:160,after:70},outlineLevel:1}},
  ]},
  sections:[{properties:{page:{margin:{top:650,right:650,bottom:650,left:650}}},headers:{default:new Header({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:[tr(`US AI Value Chain · ${cfg.title}`,{size:13,color:C.gray})]})]})},footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:[tr(`${data.meta.asOf}  |  `,{size:13,color:C.gray}),new TextRun({children:[PageNumber.CURRENT],font:'Malgun Gothic',size:13,color:C.gray})]})]})},children}],
});

Packer.toBuffer(doc).then(buf=>{fs.writeFileSync(outPath,buf);console.log(outPath);});
