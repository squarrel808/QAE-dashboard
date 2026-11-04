// Signed contributions are stacked separately above and below zero.
// The line is their algebraic sum, not the top of the positive stack.
function contributionChart(version) {
  let end=version.dates.length;
  while(end>0 && version.headline[end-1]==null) end--;
  const start=Math.max(0,end-Number($('range').value));
  const dates=version.dates.slice(start,end), headline=version.headline.slice(start,end);
  const parts=Object.fromEntries(axes.map(a=>[a,version.contributions[a].slice(start,end)]));
  if(!headline.some(v=>v!=null)) return '<p>자료 없음</p>';
  const totals=dates.map((_,i)=>{
    if(headline[i]==null || axes.some(a=>parts[a][i]==null)) return null;
    return {positive:axes.reduce((s,a)=>s+Math.max(0,parts[a][i]),0),
            negative:axes.reduce((s,a)=>s+Math.min(0,parts[a][i]),0)};
  });
  let lo=Math.min(0,...totals.filter(Boolean).map(t=>t.negative),...headline.filter(v=>v!=null));
  let hi=Math.max(0,...totals.filter(Boolean).map(t=>t.positive),...headline.filter(v=>v!=null));
  const pad=Math.max(.06,(hi-lo)*.12);lo-=pad;hi+=pad;
  const W=1200,H=340,L=52,R=18,T=18,B=35,step=(W-L-R)/Math.max(dates.length,1);
  const x=i=>L+(i+.5)*step,y=v=>T+(hi-v)/(hi-lo)*(H-T-B),width=step*.79;
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="네 부문 기여분 누적 막대와 Growth 종합지수 선">`;
  for(let j=0;j<5;j++){
    const v=lo+(hi-lo)*j/4;
    svg+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e6edf3"/><text x="${L-7}" y="${y(v)+4}" text-anchor="end">${fmt(v,2)}</text>`;
  }
  svg+=`<line x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}" stroke="#8ea1b2" stroke-dasharray="4 4"/>`;
  dates.forEach((date,i)=>{
    if(!totals[i]) return;
    let positive=0,negative=0;
    svg+=`<g class="month-stack" data-date="${date}"><title>${date}\n${axes.map(a=>a+': '+fmt(parts[a][i],3)).join('\n')}\nGrowth: ${fmt(headline[i],3)}</title>`;
    axes.forEach(a=>{
      const value=parts[a][i],base=value>=0?positive:negative,top=base+value;
      if(value>=0) positive=top; else negative=top;
      svg+=`<rect class="contribution-bar" data-axis="${a}" data-value="${value}" x="${x(i)-width/2}" y="${Math.min(y(base),y(top))}" width="${width}" height="${Math.abs(y(top)-y(base))}" fill="${colors[a]}"/>`;
    });
    svg+='</g>';
  });
  let path='',open=false;
  headline.forEach((v,i)=>{
    if(v==null){open=false;return;}
    path+=(open?'L':'M')+x(i)+','+y(v);open=true;
  });
  svg+=`<path class="growth-line" d="${path}" fill="none" stroke="#101820" stroke-width="1.8" pointer-events="none"/>`;
  const interval=Math.max(1,Math.ceil(dates.length/9));
  dates.forEach((date,i)=>{
    if(i===0 || i===dates.length-1 || (i%interval===0 && i<dates.length-interval/2))
      svg+=`<text x="${x(i)}" y="${H-9}" text-anchor="middle">${date}</text>`;
  });
  svg+='</svg>';
  return svg+'<div class="tools sub" style="justify-content:center">'+axes.map(a=>`<span><i style="display:inline-block;width:11px;height:11px;background:${colors[a]};margin-right:5px"></i>${a}${a==='Export'?' · 총수출 비중의 ½':''}</span>`).join('')+'<span style="color:#101820">━ Growth 종합지수</span></div>';
}
