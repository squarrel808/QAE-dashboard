const fs=require('fs');
const path=require('path');
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,HeadingLevel,WidthType,ShadingType,BorderStyle,Footer,PageNumber,ExternalHyperlink,AlignmentType}=require('docx');
const dir=path.basename(__dirname)==='code'?path.dirname(__dirname):path.join(__dirname,'daily_20260907');
const data=JSON.parse(fs.readFileSync(path.join(dir,'report_blocks.json'),'utf8'));
const FONT='Malgun Gothic',WIDTH=10380;
const run=(text,opt={})=>new TextRun({text:String(text),font:FONT,size:21,...opt});
const para=(text,opt={})=>new Paragraph({children:[run(text)],spacing:{after:150,line:310},...opt});
function widths(b){
 if(b.heads[1]==='밸류체인 역할')return [1850,3530,820,820,820,820,1720].map((x,i)=>i===6?1720-0:x); // normalize below
 if(b.heads[0]==='순위')return [520,1580,3300,1580,1700,1700];
 if(b.heads[0]==='하위 묶음')return [2700,5400,2280];
 if(b.heads[0]==='단계')return [3000,780,1200,1200,1200,1200,1800];
 return b.heads.map((_,i)=>i===0?2500:(WIDTH-2500)/(b.heads.length-1));
}
function makeTable(b){
 let ws=widths(b),total=ws.reduce((a,c)=>a+c,0);ws=ws.map(x=>Math.floor(x*WIDTH/total));ws[ws.length-1]+=WIDTH-ws.reduce((a,c)=>a+c,0);
 const row=(values,header,index)=>new TableRow({tableHeader:header,cantSplit:true,children:values.map((v,c)=>new TableCell({width:{size:ws[c],type:WidthType.DXA},margins:{top:80,bottom:80,left:80,right:80},shading:{fill:header?'17365D':index%2?'F0F4F8':'FFFFFF',type:ShadingType.CLEAR},children:[new Paragraph({spacing:{after:0,line:255},children:[run(v,{size:18,bold:header,color:header?'FFFFFF':String(v).startsWith('-')?'B43148':String(v).startsWith('+')?'087664':'20334A'})]})]}))});
 return new Table({width:{size:WIDTH,type:WidthType.DXA},columnWidths:ws,rows:[row(b.heads,true,0),...b.rows.map((r,i)=>row(r,false,i))],borders:{top:{style:BorderStyle.SINGLE,size:4,color:'DBE4ED'},bottom:{style:BorderStyle.SINGLE,size:4,color:'DBE4ED'},left:{style:BorderStyle.NONE,size:0},right:{style:BorderStyle.NONE,size:0},insideHorizontal:{style:BorderStyle.SINGLE,size:3,color:'DBE4ED'},insideVertical:{style:BorderStyle.NONE,size:0}}});
}
(async()=>{
for(const report of data.reports){
 const children=[para('DAILY EQUITY RESEARCH · 2026.09.07',{children:[run('DAILY EQUITY RESEARCH · 2026.09.07',{color:'197C87',bold:true,size:20})]}),new Paragraph({heading:HeadingLevel.TITLE,children:[run(report.title,{size:38,bold:true,color:'17365D'})],spacing:{after:160}}),para(report.subtitle),para('가격 기준 2026.09.04 종가 | 작성 2026.09.07 | 사용자 제공 BQuant 데이터',{children:[run('가격 기준 2026.09.04 종가 | 작성 2026.09.07 | 사용자 제공 BQuant 데이터',{size:18,color:'64758B'})]})];
 for(const b of report.blocks){
  if(b.appendix)continue;
  if(b.type==='h')children.push(new Paragraph({heading:HeadingLevel.HEADING_1,children:[run(b.text,{size:28,bold:true,color:'17365D'})],keepNext:true,spacing:{before:320,after:150}}));
  if(b.type==='p'){
   children.push(para(b.text));
   if(b.refs?.length)children.push(new Paragraph({spacing:{after:120},children:b.refs.flatMap(k=>[new ExternalHyperlink({link:data.sources[k][1],children:[run(data.sources[k][0],{size:16,color:'28699C',underline:{}})]}),run('  ',{size:16})])}));
  }
  if(b.type==='table')children.push(new Paragraph({keepNext:true,spacing:{before:170,after:80},children:[run(b.title,{bold:true,size:21,color:'17365D'})]}),makeTable(b),para('',{spacing:{after:60}}));
 }
 if(report.slug.startsWith('Daily_'))children.push(para('1D·10거래일별 Top/Bottom 100 전체 12개 표는 함께 제공한 HTML 하단과 Daily_Tables_20260907.xlsx에 수록했다. 이 문서는 본문용 상·하위 10개 및 모든 섹터 설명을 싣는다.'));
 const footer=new Footer({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:[run('2026.09.07 · 가격 2026.09.04  |  ',{size:16,color:'64758B'}),new TextRun({children:[PageNumber.CURRENT],font:FONT,size:16})]})]});
 const doc=new Document({
  creator:'Research',title:report.title,
  styles:{default:{document:{run:{font:FONT,size:21},paragraph:{spacing:{after:150,line:310}}}}},
  sections:[{properties:{page:{size:{width:11906,height:16838},margin:{top:850,bottom:850,left:763,right:763}}},footers:{default:footer},children}]
 });
 fs.writeFileSync(path.join(dir,report.slug+'.docx'),await Packer.toBuffer(doc));
 console.log('DOCX '+report.slug);
}
})();
