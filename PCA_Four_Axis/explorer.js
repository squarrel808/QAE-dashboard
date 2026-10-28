// Country overview, paired-date cycle plots, dual heatmaps and input drilldown.
const regionColors={US:'#378ADD',UK:'#BA7517',FR:'#D4537E',DE:'#7E6BC9',CA:'#1D9E75',JP:'#c65f51',AU:'#46b0c9'};
let drillObserver=null;
const selectedCountries=()=>cc==='ALL'?Object.keys(D.countries):[cc];
const finite=v=>typeof v==='number'&&Number.isFinite(v);
function seriesFor(c,version,measure='headline'){
  const v=D.countries[c].versions[version];return {dates:v.dates,values:measure==='headline'?v.headline:v.blocks[measure],latest:v.latest};
}
function atMonth(c,version,month,measure='headline'){
  const s=seriesFor(c,version,measure),i=s.dates.indexOf(month);
  return month>s.latest||i<0?null:s.values[i];
}
function countryControls(){
  $('countries').innerHTML=[['ALL','전체'],...Object.entries(D.names)].map(([k,n])=>`<button data-c="${k}" aria-pressed="${k===cc}" class="${k===cc?'active':''}">${n}</button>`).join('');
  $('countries').querySelectorAll('button').forEach(b=>b.onclick=()=>{cc=b.dataset.c;render()});
}
function renderOverview(){
  const countries=selectedCountries(),dates=D.countries[countries[0]].versions[mode].dates;
  $('cards').innerHTML=countries.map(c=>{const v=D.countries[c].versions[mode];return `<div class="card"><h3 style="color:${regionColors[c]}">${D.names[c]}</h3><div class="value">${fmt(v.latest_value)}</div><div class="sub">${mode==='YoY'?'Level · 주 PCA':'Momentum · PCA 차분'} · ${v.latest}<br>${D.indicators.filter(r=>r.country===c).length}개 지표</div></div>`}).join('');
  $('title').textContent='전체 국가 · '+(mode==='YoY'?'Level · 주 PCA':'Momentum · PCA 3M/3M 차분');
  $('mainchart').innerHTML=plot(dates,countries.map(c=>({name:D.names[c],v:D.countries[c].versions[mode].headline,c:regionColors[c]})));
  $('latest').textContent='각 국가는 자체 최신 유효월까지 표시 · 아래 국가 이름을 선택하면 기여분 막대와 개별 부문을 볼 수 있습니다.';
  $('blockcharts').innerHTML=axes.map(a=>`<section class="panel"><h2>${a}</h2>${plot(dates,countries.map(c=>({name:D.names[c],v:D.countries[c].versions[mode].blocks[a],c:regionColors[c]})))}<p class="sub">${countries.map(c=>`<span style="color:${regionColors[c]}">${D.names[c]}</span>`).join(' · ')}</p></section>`).join('');
}
function render(){
  if(cc==='ALL')renderOverview();else renderSingle();
  $('cards').classList.toggle('overview',cc==='ALL');countryControls();
  $('yoy').classList.toggle('active',mode==='YoY');$('momentum').classList.toggle('active',mode==='Momentum');
  inputs();renderCycle();renderHeatMaps();renderDrilldown();
}
function inputs(){
  const rows=D.indicators.filter(r=>(cc==='ALL'||r.country===cc)&&($('axis').value==='all'||r.axis===$('axis').value)&&[r.label,r.pk,D.names[r.country]].join(' ').toLowerCase().includes($('search').value.toLowerCase()));
  $('count').textContent=rows.length+'개 표시 · 경제적 부호와 최신 주 PCA 로딩 · Momentum의 별도 로딩 없음';
  $('inputs').innerHTML='<table><thead><tr><th>국가</th><th>축</th><th>지표 / Haver</th><th>방향</th><th>주 PCA 로딩</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${D.names[r.country]}</td><td>${r.axis}</td><td>${esc(r.label)}<br><code>${esc(r.pk)}</code>${r.proxy?' · 대리지표':''}</td><td>${r.direction>0?'+':'−'}</td><td>${fmt(r.signed_loading,3)}</td></tr>`).join('')+'</tbody></table>';
}
function renderCycle(){
  const month=$('cycleDate').value,measure=$('cycleMeasure').value,n=+$('cycleTrail').value;
  const paths=selectedCountries().map(c=>{
    const dates=seriesFor(c,'YoY').dates.filter(d=>d<=month).slice(-n);
    return {c,points:dates.map(d=>({d,x:atMonth(c,'YoY',d,measure),y:atMonth(c,'Momentum',d,measure)}))};
  });
  const points=paths.flatMap(p=>p.points).filter(p=>finite(p.x)&&finite(p.y));
  const xmax=Math.max(.25,...points.map(p=>Math.abs(p.x)))*1.25,ymax=Math.max(.1,...points.map(p=>Math.abs(p.y)))*1.3;
  const W=1040,H=500,L=85,R=85,T=40,B=60,x=v=>L+(v+xmax)/(2*xmax)*(W-L-R),y=v=>T+(ymax-v)/(2*ymax)*(H-T-B);
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Level 가로축 Momentum 세로축 사분면"><defs>${paths.map(p=>`<marker id="arr-${p.c}" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="${regionColors[p.c]}"/></marker>`).join('')}</defs>`;
  svg+=`<rect x="${x(0)}" y="${T}" width="${x(xmax)-x(0)}" height="${y(0)-T}" fill="#eef7f2"/><rect x="${L}" y="${T}" width="${x(0)-L}" height="${y(0)-T}" fill="#edf5fc"/><rect x="${L}" y="${y(0)}" width="${x(0)-L}" height="${y(-ymax)-y(0)}" fill="#fcf1ef"/><rect x="${x(0)}" y="${y(0)}" width="${x(xmax)-x(0)}" height="${y(-ymax)-y(0)}" fill="#fcf7ed"/>`;
  for(let i=-2;i<=2;i++){
    const xv=xmax*i/2,yv=ymax*i/2;
    svg+=`<line x1="${x(xv)}" x2="${x(xv)}" y1="${T}" y2="${H-B}" stroke="${i===0?'#92a4b5':'#dfe7ee'}" ${i===0?'stroke-dasharray="4 4"':''}/><text x="${x(xv)}" y="${H-B+23}" text-anchor="middle">${fmt(xv,2)}</text><line x1="${L}" x2="${W-R}" y1="${y(yv)}" y2="${y(yv)}" stroke="${i===0?'#92a4b5':'#dfe7ee'}" ${i===0?'stroke-dasharray="4 4"':''}/><text x="${L-12}" y="${y(yv)+4}" text-anchor="end">${fmt(yv,2)}</text>`;
  }
  svg+=`<text x="${L+12}" y="${T+20}">평균 이하 · 개선</text><text x="${W-R-12}" y="${T+20}" text-anchor="end">평균 이상 · 개선</text><text x="${L+12}" y="${H-B-14}">평균 이하 · 둔화</text><text x="${W-R-12}" y="${H-B-14}" text-anchor="end">평균 이상 · 둔화</text><text x="${W/2}" y="${H-10}" text-anchor="middle">Level · 주 PCA 점수 →</text><text transform="translate(22 ${H/2}) rotate(-90)" text-anchor="middle">Momentum · PCA 3M/3M 차분 →</text>`;
  const legends=[];
  paths.forEach((p,j)=>{
    let segment=[];const flush=()=>{if(segment.length>1)svg+=`<path d="${segment.map((v,i)=>(i?'L':'M')+x(v.x)+','+y(v.y)).join(' ')}" stroke="${regionColors[p.c]}" stroke-opacity=".65" stroke-width="1.8" fill="none" marker-end="url(#arr-${p.c})"/>`;segment=[]};
    p.points.forEach(pt=>{if(!finite(pt.x)||!finite(pt.y)){flush();return}segment.push(pt)});flush();
    p.points.forEach((pt,i)=>{if(!finite(pt.x)||!finite(pt.y))return;const current=pt.d===month;svg+=`<circle data-country="${p.c}" data-month="${pt.d}" data-level="${pt.x}" data-momentum="${pt.y}" cx="${x(pt.x)}" cy="${y(pt.y)}" r="${current?6:2.6}" fill="${regionColors[p.c]}" opacity="${current?1:.25+.55*i/Math.max(1,p.points.length-1)}" ${current?'stroke="white" stroke-width="1.6"':''}><title>${D.names[p.c]} · ${pt.d}\nLevel ${fmt(pt.x,3)} · Momentum ${fmt(pt.y,3)}</title></circle>`;if(current)svg+=`<text x="${x(pt.x)+10}" y="${y(pt.y)-10+(j%2)*24}" fill="${regionColors[p.c]}">${D.names[p.c]}</text>`});
    const last=p.points.find(pt=>pt.d===month),valid=last&&finite(last.x)&&finite(last.y);
    legends.push(`<span class="cycle-item" style="color:${regionColors[p.c]}">● ${D.names[p.c]} · ${month} · ${valid?`Level ${fmt(last.x,2)} / Mom ${fmt(last.y,2)}`:'자료 없음'}</span>`);
  });
  $('cycleChart').innerHTML=svg+'</svg>';$('cycleLegend').innerHTML=legends.join('');
}
function renderHeatMaps(){
  const month=$('cycleDate').value,n=+$('heatWindow').value,measure=$('cycleMeasure').value;
  const dates=seriesFor('US','YoY').dates.filter(d=>d<=month).slice(-n);
  const rows=cc==='ALL'?selectedCountries().map(c=>({c,measure,label:D.names[c]})):[{c:cc,measure:'headline',label:'Growth'},...axes.map(a=>({c:cc,measure:a,label:a}))];
  $('heatCaption').textContent=cc==='ALL'?`전체 국가 · ${measure==='headline'?'Growth':measure} · 기준 ${month}`:`${D.names[cc]} · 종합·부문별 · 기준 ${month}`;
  for(const [version,id] of [['YoY','heatLevel'],['Momentum','heatMomentum']]){
    const values=rows.map(r=>dates.map(d=>atMonth(r.c,version,d,r.measure))),max=Math.max(.01,...values.flat().filter(finite).map(Math.abs));
    $(id).innerHTML=`<p class="sub">색상 범위 −${fmt(max,2)} ~ +${fmt(max,2)} · 0 중심</p><table><thead><tr><th>${cc==='ALL'?'국가':'부문'}</th>${dates.map(d=>`<th>${d.slice(2)}</th>`).join('')}</tr></thead><tbody>`+rows.map((r,j)=>'<tr><th>'+r.label+'</th>'+values[j].map((v,i)=>finite(v)?`<td data-month="${dates[i]}" data-country="${r.c}" data-value="${v}" title="${r.label} · ${dates[i]}: ${fmt(v,3)}" style="background:rgba(${v>=0?'37,136,117':'198,95,81'},${.06+.62*Math.min(1,Math.abs(v)/max)})">${fmt(v)}</td>`:`<td style="background:#f1f3f5" title="${dates[i]} 자료 없음">—</td>`).join('')+'</tr>').join('')+'</tbody></table>';
  }
}
function miniChart(dates,values,label){
  const good=values.filter(finite);if(!good.length)return '<p class="sub">표시 구간 자료 없음</p>';
  let lo=Math.min(...good),hi=Math.max(...good),pad=Math.max((hi-lo)*.12,Math.abs(hi)*.01,.001);lo-=pad;hi+=pad;
  const W=360,H=145,L=42,R=8,T=8,B=22,x=i=>L+i*(W-L-R)/Math.max(1,dates.length-1),y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)} 추이">`;
  for(let j=0;j<3;j++){let v=lo+(hi-lo)*j/2;svg+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e6edf3"/><text x="${L-5}" y="${y(v)+3}" text-anchor="end">${Math.abs(v)>10000?v.toExponential(1):fmt(v,1)}</text>`}
  if(lo<=0&&hi>=0)svg+=`<line x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}" stroke="#a3b0bd" stroke-dasharray="3 3"/>`;
  let path='',open=false;values.forEach((v,i)=>{if(!finite(v)){open=false;return}path+=(open?'L':'M')+x(i)+','+y(v);open=true});
  svg+=`<path d="${path}" fill="none" stroke="#6e1f1f" stroke-width="1.3"/>`;
  for(const i of [...new Set([0,Math.floor(dates.length/2),dates.length-1])])svg+=`<text x="${x(i)}" y="${H-5}" text-anchor="middle">${dates[i]}</text>`;
  values.forEach((v,i)=>{if(finite(v))svg+=`<circle cx="${x(i)}" cy="${y(v)}" r="3.2" fill="transparent"><title>${dates[i]} · ${fmt(v,3)}</title></circle>`});
  return svg+'</svg>';
}
function renderDrilldown(){
  if(drillObserver)drillObserver.disconnect();
  const query=$('drillSearch').value.toLowerCase(),axis=$('drillAxis').value,view=$('drillView').value;
  const rows=D.indicators.filter(r=>(cc==='ALL'||r.country===cc)&&(axis==='all'||r.axis===axis)&&[r.label,r.pk,D.names[r.country]].join(' ').toLowerCase().includes(query));
  $('drillCount').textContent=`${cc==='ALL'?'전체 국가':D.names[cc]} · ${rows.length}개 지표 · ${view==='raw'?'변환 전 원자료 · 단위는 지표명 참조':'주 PCA에 사용한 전처리 z-score · 경제적 방향 반영'} · 상단 기간 선택 적용`;
  $('drillCharts').innerHTML=rows.map((r,i)=>{
    const data=D.input_series[r.country],all=data.series[r.pk][view],last=all.findLastIndex(finite),updated=finite(all[data.dates.indexOf(data.latest_raw)]);
    return `<div class="mini-card" data-i="${i}"><div class="mini-name" title="${esc(r.label)}">${cc==='ALL'?D.names[r.country]+' · ':''}${esc(r.label)}</div><div class="mini-updated">${updated?'updated':''}</div><div class="mini-value">${r.axis} · ${esc(r.pk)} · ${last<0?'자료 없음':data.dates[last]+' / '+fmt(all[last],3)}</div><div class="mini-plot"></div></div>`;
  }).join('');
  const draw=card=>{
    const r=rows[+card.dataset.i],data=D.input_series[r.country],all=data.series[r.pk][view];
    const end=all.findLastIndex(finite)+1,start=Math.max(0,end-(+$('range').value));
    card.querySelector('.mini-plot').innerHTML=miniChart(data.dates.slice(start,end),all.slice(start,end),r.label);
  };
  if('IntersectionObserver' in window){drillObserver=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){draw(e.target);drillObserver.unobserve(e.target)}}),{rootMargin:'500px'});$('drillCharts').querySelectorAll('.mini-card').forEach(c=>drillObserver.observe(c))}
  else $('drillCharts').querySelectorAll('.mini-card').forEach(draw);
}
// Analysis controls share an explicit reference month; never combine two dates.
const cycleMonths=[...new Set(Object.entries(D.countries).flatMap(([c,v])=>v.versions.YoY.dates.filter(d=>finite(atMonth(c,'YoY',d)))))].sort();
$('cycleDate').innerHTML=cycleMonths.slice().reverse().map(d=>`<option>${d}</option>`).join('');
for(const id of ['cycleDate','cycleMeasure'])$(id).onchange=()=>{renderCycle();renderHeatMaps()};
$('cycleTrail').onchange=renderCycle;$('heatWindow').onchange=renderHeatMaps;
$('drillAxis').onchange=renderDrilldown;$('drillView').onchange=renderDrilldown;$('drillSearch').oninput=renderDrilldown;
