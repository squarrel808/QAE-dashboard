const fs=require('fs'), vm=require('vm'), assert=require('assert');
const nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{value:id==='releaseState'?'actual':'',textContent:'',innerHTML:'',addEventListener(){},scrollIntoView(){this.scrolled=true}});return nodes.get(id)}
node('data').textContent=fs.readFileSync(__dirname+'/data.json','utf8');
const context=vm.createContext({document:{getElementById:node},location:{protocol:'file:'},Intl,Date,console});
vm.runInContext(fs.readFileSync(__dirname+'/page.js','utf8'),context);
vm.runInContext(`
$('recentDate').value='2026-09-21';renderRecent();
if(recentUpdates(DATA.events,'2026-09-21').length!==17)throw Error('Expected 17 recent reviews');
const real=recentUpdates(DATA.events,'2026-09-21');
if(!real.every(x=>x.interpreted&&!x.released))throw Error('Old numerical release mislabelled as new');
const base={...DATA.events.find(e=>e.actual!==null),available_at_request:true,commentary:null};
const cases=[{...base,id:'edge',date:'2026-09-19'},{...base,id:'outside',date:'2026-09-18'},
{...base,id:'future',date:'2026-09-22'},{...base,id:'missing',date:'2026-09-20',actual:null},
{...base,id:'review',date:'2026-09-01',commentary:{reviewed_on:'2026-09-20'}}];
if(recentUpdates(cases,'2026-09-21').map(x=>x.e.id).join(',')!=='review,edge')throw Error('Date boundary or actual filter failed');
const before=$('recentList').innerHTML;
country='JP';theme='inflation';$('search').value='does-not-exist';render();
if($('recentList').innerHTML!==before)throw Error('Recent feed affected by filters');
openRecent(real[0].e.id);
if(selected!==real[0].e.id||!$('detail').scrolled||$('search').value!=='')throw Error('Detail navigation failed');
$('recentDate').value='2026-10-21';renderRecent();
if(!$('recentList').innerHTML.includes('없습니다'))throw Error('Empty state failed');
`,context);
assert(node('recentList').innerHTML);
console.log('PASS: real 17-item rendering, 3-day boundaries, no future/missing actuals, filter independence, detail navigation, empty state');
