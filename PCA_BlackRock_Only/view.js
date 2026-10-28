// Overrides of the shared PCA II presentation. Numerical series are untouched.
function latestPair(c,measure='headline'){
  return `<div class="latest-pair">${['YoY','Momentum'].map(ver=>{
    const v=D.countries[c].versions[ver],value=atMonth(c,ver,v.latest,measure);
    return `<div><small>${ver==='YoY'?'Level':'Momentum'}</small><span class="value" data-latest-country="${c}" data-latest-measure="${measure}" data-version="${ver}">${fmt(value,3)}</span><small>${v.latest}</small></div>`;
  }).join('')}</div>`;
}
function endpointSummary(countries,ver,measure='headline'){
  return '<div class="end-values">'+countries.map(c=>{const v=D.countries[c].versions[ver];return `<span style="color:${regionColors[c]}">${D.names[c]} ${fmt(atMonth(c,ver,v.latest,measure),3)} <small>(${v.latest})</small></span>`}).join('')+'</div>';
}
function renderSingle(){
  const c=D.countries[cc],level=c.versions.YoY,momentum=c.versions.Momentum;
  $('cards').innerHTML=axes.map(a=>`<div class="card"><h3 style="color:${colors[a]}">${a}</h3>${c.active_axes.includes(a)?latestPair(cc,a):'<p class="missing">참조 지표 없음 · 미편입</p>'}<div class="sub">${c.diagnostics[a].count}개 지표 · ${c.diagnostics[a].single?'단일지표 표준화':'직접 PCA'}<br>${a==='Export'?'총수출/GDP × ½':'GDP 비중'} ${fmt(c.weights[a]*100,1)}% ${c.missing_axes.includes(a)?'· 합산 제외':''}</div></div>`).join('');
  $('title').textContent=`${D.names[cc]} · Growth Level ${fmt(level.latest_value,3)} · ${level.latest}`;
  $('mainchart').innerHTML=contributionChart(level);
  $('momentumTitle').textContent=`${D.names[cc]} · Growth Momentum ${fmt(momentum.latest_value,3)} · ${momentum.latest}`;
  $('momentumChart').innerHTML=contributionChart(momentum);
  const coverage=c.missing_axes.length?` · ${c.missing_axes.join(', ')} 미편입 · 비중 재배분 없음`:'';
  $('latest').textContent=`${c.weight_year}년 연초 고정 가중치 · ${c.weight_quarter} · 막대는 부문 기여분, 검은 선은 합계${coverage}`;
  $('momentumLatest').textContent='완성된 Level PCA의 최근 3개월 평균 − 직전 3개월 평균 · 지수 포인트 차분'+coverage;
  $('blockcharts').innerHTML=axes.map(a=>`<section class="panel" data-sector="${a}"><h2 style="color:${colors[a]}">${a}</h2>${c.missing_axes.includes(a)?'<p class="missing">BlackRock 참조 목록에 해당 부문 지표가 없어 계산하지 않습니다.</p>':'<div class="metric-stack">'+['YoY','Momentum'].map(ver=>{
    const v=c.versions[ver],i=v.dates.indexOf(v.latest);
    return `<div data-block-version="${ver}"><div class="metric-head"><h3>${ver==='YoY'?'Level':'Momentum'}</h3><span class="metric-end">${v.latest} · ${fmt(v.blocks[a][i],3)}</span></div>${plot(v.dates,[{name:a,v:v.blocks[a],c:colors[a]}])}<p class="sub">종합지수 기여분 ${fmt(v.contributions[a][i],3)}</p></div>`;
  }).join('')+'</div>'}</section>`).join('');
}
function renderOverview(){
  const countries=selectedCountries(),dates=D.countries[countries[0]].versions.YoY.dates;
  $('cards').innerHTML=countries.map(c=>`<div class="card"><h3 style="color:${regionColors[c]}">${D.names[c]}</h3>${latestPair(c)}<div class="sub">${D.indicators.filter(r=>r.country===c).length}개 지표${D.countries[c].missing_axes.length?' · Housing 미편입':''}</div></div>`).join('');
  for(const [ver,chart,title] of [['YoY','mainchart','title'],['Momentum','momentumChart','momentumTitle']]){
    $(title).textContent='전체 국가 · Growth '+(ver==='YoY'?'Level':'Momentum');
    $(chart).innerHTML=plot(dates,countries.map(c=>({name:D.names[c],v:D.countries[c].versions[ver].headline,c:regionColors[c]})))+endpointSummary(countries,ver);
  }
  $('latest').textContent='각 국가의 최신 유효월과 끝값을 함께 표시합니다. 독일·일본은 Housing을 제외한 합계입니다.';
  $('momentumLatest').textContent='동일한 국가 지수의 최근 3개월 평균 − 직전 3개월 평균 · 위 Level과 같은 기간';
  renderSectorHeatmaps();
}
function renderSectorHeatmaps(){
  if(cc!=='ALL')return;
  const month=$('cycleDate').value,n=+$('sectorWindow').value,dates=seriesFor('US','YoY').dates.filter(d=>d<=month).slice(-n);
  $('blockcharts').innerHTML=axes.map(a=>`<section class="panel sector-heatmap" data-sector="${a}"><h2>${a}</h2><p class="sub">전체 국가 · 기준 ${month} · 최근 ${n}개월</p><div class="metric-stack">${['YoY','Momentum'].map(ver=>`<div data-sector-version="${ver}"><h3>${ver==='YoY'?'Level':'Momentum'}</h3><div class="scroll">${heatTable(dmMembers.map(c=>({c,measure:a,label:D.names[c]})),ver,dates)}</div></div>`).join('')}</div></section>`).join('');
  revealLatestCells();
}
function revealLatestCells(){
  requestAnimationFrame(()=>document.querySelectorAll('.sector-heatmap .scroll,.heat-pair .scroll').forEach(el=>{el.scrollLeft=el.scrollWidth-el.clientWidth}));
}
function renderWeights(){
  const year=+$('weightYear').value;
  $('weights').innerHTML=Object.entries(D.names).map(([k,n])=>{
    const c=D.countries[k],r=c.annual_weights.find(r=>r.year===year);
    if(!r)return `<tr><td>${n}</td><td colspan="6">연초 이용 가능 자료 없음</td></tr>`;
    return `<tr><td>${n}</td>`+axes.map(a=>`<td>${fmt(r.weights[a]*100,1)}%${c.missing_axes.includes(a)?' · 미편입':''}</td>`).join('')+`<td>${fmt(c.active_axes.reduce((sum,a)=>sum+r.weights[a],0)*100,1)}%</td><td>${r.quarter}</td></tr>`;
  }).join('');
}
function render(){
  if(cc==='ALL')renderOverview();else renderSingle();
  $('sectorControls').hidden=cc!=='ALL';
  $('cards').classList.toggle('overview',cc==='ALL');countryControls();
  inputs();renderCycle();renderHeatMaps();renderDrilldown();revealLatestCells();
}
// A single series gets an explicit end-point label; comparison charts have a
// separate six-country end-value strip to avoid overlapping labels.
function plot(dates,series){
  let end=dates.length;while(end>0&&series.every(s=>s.v[end-1]==null))end--;
  const start=Math.max(0,end-(+$('range').value)),ds=dates.slice(start,end),ss=series.map(s=>({...s,v:s.v.slice(start,end)}));
  const vv=ss.flatMap(s=>s.v.filter(finite));if(!vv.length)return '<p>자료 없음</p>';
  let lo=Math.min(0,...vv),hi=Math.max(0,...vv),pad=Math.max(.1,(hi-lo)*.12);lo-=pad;hi+=pad;
  const W=1200,H=235,L=55,R=90,T=16,B=30,x=i=>L+i*(W-L-R)/Math.max(ds.length-1,1),y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${series.map(s=>s.name).join(', ')} 시계열">`;
  for(let j=0;j<5;j++){const v=lo+(hi-lo)*j/4;svg+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e6edf3"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end">${fmt(v,1)}</text>`}
  svg+=`<line x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}" stroke="#8ea1b2" stroke-dasharray="4 4"/>`;
  ss.forEach(s=>{
    let path='',open=false;s.v.forEach((v,i)=>{if(!finite(v)){open=false;return}path+=(open?'L':'M')+x(i)+','+y(v);open=true});
    svg+=`<path d="${path}" fill="none" stroke="${s.c}" stroke-width="2.1"/>`;
    s.v.forEach((v,i)=>{if(finite(v))svg+=`<circle cx="${x(i)}" cy="${y(v)}" r="3" fill="transparent"><title>${ds[i]} ${s.name}: ${fmt(v,3)}</title></circle>`});
    const last=s.v.findLastIndex(finite);if(last>=0){svg+=`<circle cx="${x(last)}" cy="${y(s.v[last])}" r="3.5" fill="${s.c}"/>`;if(ss.length===1)svg+=`<text class="endpoint" data-value="${s.v[last]}" x="${x(last)+10}" y="${y(s.v[last])+4}">${fmt(s.v[last],3)}</text>`}
  });
  const interval=Math.max(1,Math.ceil(ds.length/8));ds.forEach((d,i)=>{if(i===0||i===ds.length-1||(i%interval===0&&i<ds.length-interval/2))svg+=`<text x="${x(i)}" y="${H-8}" text-anchor="middle">${d}</text>`});
  return svg+'</svg>';
}
// Retain vertical heatmaps and reveal their final month after filter changes.
for(const id of ['cycleDate','cycleMeasure'])$(id).onchange=()=>{renderCycle();renderHeatMaps();renderSectorHeatmaps();revealLatestCells()};
$('heatWindow').onchange=()=>{renderHeatMaps();revealLatestCells()};
window.addEventListener('resize',revealLatestCells);
