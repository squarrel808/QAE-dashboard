
'use strict';const DATA=JSON.parse(document.getElementById('data').textContent);const $=id=>document.getElementById(id);let country='US',theme='growth',selected=null;const labels={reaction:'발표 후 직접 코멘트',preview:'발표 전 직접 전망',candidate:'지표·지역 원문 후보',inferred:'기존 뷰 기반 AI 해석',basis:'상위 거시 배경만 있음',uncovered:'근거 미확보'};const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const num=x=>x===null||x===undefined?'—':new Intl.NumberFormat('ko-KR',{maximumFractionDigits:5}).format(x);const tag=(s)=>`<span class="tag ${s}">${labels[s]}</span>`;
function sourceRange(e){const c=(e.source_column_range||DATA.meta.source_column_range||'B:K').split(':');return `${c[0]}${e.source_row}:${c[1]}${e.source_row}`}
function sourceUrl(e){return location.protocol==='http:'?'/source/'+e.doc_id+'#page='+e.page:e.url}
function refs(items){const map=new Map;items.forEach(i=>(i.evidence||[]).forEach(e=>map.set(e.doc_id+':'+e.page+e.quote,e)));return `<details><summary>원문 근거 ${map.size}개</summary>${[...map.values()].map(e=>`<p><a href="${esc(sourceUrl(e))}" target="_blank" rel="noopener">${esc(e.title)}</a><br>${esc(e.published)} · PDF ${e.page}쪽</p><blockquote>${esc(e.quote)}</blockquote>`).join('')}</details>`}
const timingLabel={after_release_candidate:'발표 후 후보',same_day_timing_unverified:'발표 당일·시각 미확인',pre_release_candidate:'발표 전 후보'};
labels.related='관련 지표 분석 · 범위 제한';
labels.needs_recheck='수치 변경 · 재검토';
function sourceLine(items){
  const map=new Map;items.forEach(i=>(i.evidence||[]).forEach(x=>map.set(x.doc_id+':'+x.page,x)));
  return `<div class="muted">${[...map.values()].map(x=>`<a href="${esc(sourceUrl(x))}" target="_blank" rel="noopener">${esc(x.title)}</a> · ${esc(x.published)} · ${x.page}쪽`).join('<br>')}</div>`;
}
function candidateCards(houses){
  const count=houses.reduce((n,h)=>n+(h.search_candidates||[]).length,0);
  if(!count)return '';
  return `<details class="foot"><summary>추가 검색 후보 ${count}건 — 미검토</summary><p class="muted">아래는 채택된 코멘트가 아닌 추가 검토용 자료입니다.</p>${houses.filter(h=>(h.search_candidates||[]).length).map(h=>`<b>${esc(h.house)}</b>${h.search_candidates.map(c=>`<details><summary>${esc(c.title)} · ${esc(c.published)} · ${c.page}쪽</summary><p class="muted">${esc(timingLabel[c.timing]||c.timing)} · <a href="${esc(c.url)}" target="_blank" rel="noopener">원문 열기</a></p><blockquote>${esc(c.excerpt)}</blockquote></details>`).join('')}`).join('')}</details>`;
}
function renderHouse(h,state){
  const c=h.commentary;
  if(state==='needs_recheck')return h.direct.length||h.forecasts.length?`<details><summary>${esc(h.house)} 과거 코멘트 — 현재 수치에 적용하지 않음</summary>${h.direct.map(d=>`<p>${esc(d.summary)}</p>`).join('')}${refs([...h.direct,...h.forecasts])}</details>`:'';
  if(c)return `<article class="card"><h3>${esc(h.house)} ${tag(c.kind)}</h3><p><b>IB 요약</b> ${esc(c.summary)}</p><div class="basis"><b>지표 코멘트 · AI</b><br>${esc(c.comment)}</div>${c.limitation?`<p class="muted">유의: ${esc(c.limitation)}</p>`:''}${sourceLine([c])}${refs([c])}</article>`;
  if(!h.direct.length&&!h.forecasts.length)return '';
  return `<article class="card"><h3>${esc(h.house)} ${tag(h.status)}</h3>${h.direct.map(d=>`<p><b>${d.kind==='reaction'?'IB 사후 요약':'IB 사전 전망'}</b> ${esc(d.summary)}</p>${d.limitation?`<p class="muted">유의: ${esc(d.limitation)}</p>`:''}`).join('')}${h.forecasts.map(f=>`<p>사전 수치 전망 ${num(f.value)} ${esc(f.unit)} · ${esc(f.reference_period)} (${esc(f.as_of)})</p>`).join('')}${sourceLine([...h.direct,...h.forecasts])}${refs([...h.direct,...h.forecasts])}</article>`;
}
function renderDetail(e){
  if(!e){$('detail').innerHTML='<div class="empty">지표를 선택하면 요약과 코멘트가 표시됩니다.</div>';return}
  selected=e.id;const c=e.commentary,r=e.raw;
  let html=`<div class="muted">${esc(e.country_label)} / ${esc(DATA.themes[e.theme])} / ${esc(e.date)} ${esc(e.time)}</div><h2>${esc(e.event)}</h2><div class="muted">대상 기간 ${esc(e.period)} · 단위 ${esc((e.currency||'')+(e.scale||'지수'))}</div><div class="factline">${esc(e.facts)}</div>`;
  if(c)html+=`<section class="event-summary"><h3>${esc(c.headline)}</h3><p>${esc(c.summary)}</p><p class="next-check"><b>다음 확인</b> ${esc(c.watch)}</p><div class="muted">지표 종합 해석은 AI 초안 · 검토 ${esc(c.reviewed_on)} · 아래 IB 원문 요약과 구분</div></section>`;
  else html+=`<p class="muted">${e.commentary_status==='needs_recheck'?'수치가 바뀌어 기존 해석을 숨겼습니다. 최신 값으로 재검토가 필요합니다.':e.actual===null?'아직 실제값이 없어 발표 후 해석은 작성하지 않았습니다.':'이 항목은 원문 검토 코멘트가 아직 없습니다.'}</p>`;
  html+=e.houses.map(h=>renderHouse(h,e.commentary_status)).join('');
  const missing=e.houses.filter(h=>!h.commentary&&!h.direct.length&&!h.forecasts.length).map(h=>h.house);
  if(missing.length)html+=`<p class="muted">채택할 지표별 IB 근거 미확보: ${missing.map(esc).join(' · ')}. 검토 범위 내 상태이며, 보고서 전체에 언급이 없다는 뜻은 아닙니다.</p>`;
  if(c)html+=`<details><summary>검토 범위와 공백</summary><p class="muted">${esc(c.review_log)}</p></details>`;
  html+=candidateCards(e.houses);
  const withBases=e.houses.filter(h=>h.bases.length);
  if(withBases.length)html+=`<details class="foot"><summary>상위 거시 배경 — 이번 지표 직접 코멘트 아님</summary>${withBases.map(h=>`<h4>${esc(h.house)}</h4>${h.bases.map(b=>`<p>${esc(b.summary)} <span class="muted">${esc(b.effective_date)}</span></p>`).join('')}${refs(h.bases)}`).join('')}</details>`;
  html+=`<details><summary>원본 ${esc(e.source_sheet)} ${sourceRange(e)}</summary><p class="muted">${esc(e.classification_note)}</p><table class="source-table">${(e.source_columns||DATA.columns).map(col=>`<tr><td>${esc(col.letter)} ${esc(col.label)}</td><td>${esc(r[col.letter]??'빈 셀')}</td></tr>`).join('')}</table></details>`;
  $('detail').innerHTML=html;
}
function render(){
  const month=$('month').value,q=$('search').value.trim().toLowerCase();
  const base=DATA.events.filter(e=>e.country_code===country&&e.release_month===month);
  const shown=base.filter(e=>($('releaseState').value==='all'||(e.available_at_request??e.actual!==null))&&e.theme===theme&&(!q||[e.event,e.period,e.commentary?.headline||''].some(t=>t.toLowerCase().includes(q))));
  const reported=base.filter(e=>e.actual!==null).length,reviewed=base.filter(e=>e.commentary).length;
  const direct=base.filter(e=>e.houses.some(h=>h.status==='reaction')).length;
  $('metrics').innerHTML=[['선택 월 지표',base.length],['실제값 수록',reported],['요약·해석 완료',reviewed],['IB 사후 코멘트 지표',direct]].map(([l,v])=>`<div class="metric"><span class="muted">${l}</span><b>${v}</b></div>`).join('');
  $('countryTitle').textContent=DATA.countries.find(c=>c.code===country).label+' · '+month;
  $('countries').innerHTML=DATA.countries.map(c=>`<button class="${c.code===country?'active':''}" data-country="${c.code}" aria-pressed="${c.code===country}">${esc(c.label)}</button>`).join('');
  $('themes').innerHTML=Object.entries(DATA.themes).map(([k,l])=>`<button data-theme="${k}" class="${theme===k?'active':''}" aria-pressed="${theme===k}">${esc(l)} <span class="muted">${base.filter(e=>e.theme===k).length}</span></button>`).join('');
  if(!shown.some(e=>e.id===selected))selected=shown[0]?.id??null;
  $('rows').innerHTML=shown.map(e=>{
    const nr=e.houses.filter(h=>h.status==='reaction').length,np=e.houses.filter(h=>h.status==='preview').length;
    const nh=e.houses.filter(h=>h.commentary).length;
    const badge=e.commentary?`<span class="tag reaction">요약 완료</span>${nh?`<br><span class="muted">IB ${nh}곳</span>`:''}`:e.commentary_status==='needs_recheck'?'<span class="tag">수치 변경·재검토</span>':nr?`<span class="tag reaction">사후 ${nr}</span>`:np?`<span class="tag preview">사전 ${np}</span>`:'<span class="tag">검토 대기</span>';
    return `<tr data-id="${e.id}" tabindex="0" aria-label="${esc(e.event)} 요약 보기" class="${e.id===selected?'selected':''}"><td>${e.date.slice(5)}</td><td>${esc(e.time)}</td><td>${esc(e.event)}${e.record_origin==='history'?'<small class="row-headline">과거 기록</small>':''}${e.commentary?`<small class="row-headline">${esc(e.commentary.headline)}</small>`:''}</td><td>${esc(e.period)}</td><td>${num(e.survey)}</td><td><b>${num(e.actual)}</b></td><td>${num(e.prior)}</td><td>${num(e.revised)}</td><td>${esc((e.currency||'')+(e.scale??'지수'))}</td><td>${badge}</td></tr>`;
  }).join('');
  $('empty').hidden=shown.length>0;renderDetail(shown.find(e=>e.id===selected));
}
$('month').innerHTML=DATA.meta.months.map(m=>`<option>${m}</option>`).join('');
$('month').value=DATA.meta.months.at(-1);
$('subtitle').textContent=`누적 ${DATA.meta.start} ~ ${DATA.meta.end} · ${DATA.meta.country_count}개 지역 · ${DATA.meta.authored_event_count||0}개 지표 요약`;
$('periodNote').textContent=`최신 원본 ${DATA.meta.latest_calendar_start||DATA.meta.start} ~ ${DATA.meta.latest_calendar_end||DATA.meta.end} · 과거 기록 ${DATA.meta.history_event_count||0}건 · 코멘트 검토 ${DATA.meta.commentary_reviewed_on||'미검토'}`;
$('method').innerHTML=`<p>${esc(DATA.meta.time_note)}</p><p>${esc(DATA.meta.monthly_note)}</p><p>원본 ${esc(DATA.meta.workbook_name)} · 파일 수정 ${esc(DATA.meta.workbook_modified)} · 데이터 기준 ${esc(DATA.meta.as_of)}</p><p>지표별 요약은 실제값·예상·수정 종전값을 비교한 AI 해석 초안입니다. IB 요약은 해당 보고서 전체 페이지를 읽어 작성하고, 발표 전 전망·발표 후 반응·범위가 다른 관련 분석을 구분합니다. AI 코멘트는 IB의 새 발언이나 사용자 승인 판단이 아닙니다.</p><p>출처 제목·발행일·페이지는 요약 아래에 표시하며 긴 인용과 검색 후보는 접어 두었습니다. 숫자가 바뀌면 저장된 해석을 그대로 재사용하지 않습니다. 근거 미확보는 전체 보고서에 언급이 없다는 뜻이 아닙니다.</p><p>${DATA.meta.authored_event_count||0}개 지표 해석 · ${DATA.meta.authored_house_count||0}개 IB 요약·코멘트. 보고서 최신 발행일 ${esc(DATA.meta.source_date_max)}. k=천, m=백만, b=십억, t=조이며 통화기호는 원본에 명시된 경우만 표시합니다. 빈 실제값을 0으로 채우지 않습니다.</p>`;
$('countries').addEventListener('click',e=>{const b=e.target.closest('[data-country]');if(b){country=b.dataset.country;selected=null;render()}});
$('themes').addEventListener('click',e=>{const b=e.target.closest('[data-theme]');if(b){theme=b.dataset.theme;selected=null;render()}});
$('rows').addEventListener('click',e=>{const r=e.target.closest('[data-id]');if(r){selected=r.dataset.id;render()}});
$('rows').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){const r=e.target.closest('[data-id]');if(r){e.preventDefault();selected=r.dataset.id;render()}}});
$('releaseState').addEventListener('change',render);$('month').addEventListener('change',render);$('search').addEventListener('input',render);render();

function recentUpdates(events,end){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(end))return [];
  const start=new Date(end+'T00:00:00Z');if(Number.isNaN(start.getTime()))return [];
  start.setUTCDate(start.getUTCDate()-2);const first=start.toISOString().slice(0,10);
  return events.filter(e=>e.actual!==null&&e.actual!==undefined&&(e.available_at_request??true)&&e.date<=end).map(e=>{
    const review=e.commentary?.reviewed_on||'';
    const released=e.date>=first&&e.date<=end, interpreted=review>=first&&review<=end;
    return {e,released,interpreted,updated:[released?e.date:'',interpreted?review:''].sort().at(-1)};
  }).filter(x=>x.released||x.interpreted).sort((a,b)=>b.updated.localeCompare(a.updated)||b.e.date.localeCompare(a.e.date)||a.e.country_label.localeCompare(b.e.country_label)||a.e.event.localeCompare(b.e.event));
}
function renderRecent(){
  const end=$('recentDate').value,items=recentUpdates(DATA.events,end);
  const start=new Date(end+'T00:00:00Z');if(Number.isNaN(start.getTime()))return;
  start.setUTCDate(start.getUTCDate()-2);
  $('recentCount').textContent=items.length+'개';
  $('recentNote').textContent=`${start.toISOString().slice(0,10)} ~ ${end} (한국시간, 기준일 포함 3일) · 화면 자료 기준 ${DATA.meta.as_of} · 해석 갱신은 수치 변경과 다릅니다.`;
  $('recentList').innerHTML=items.length?items.map(({e,released,interpreted})=>`<article class="recent-item"><div class="recent-meta"><b>${esc(e.country_label)}</b><span class="tag">${esc(DATA.themes[e.theme])}</span>${released?`<span class="tag preview">발표 ${esc(e.date)}</span>`:''}${interpreted?`<span class="tag reaction">해석 갱신 ${esc(e.commentary.reviewed_on)}</span>`:''}</div><h3>${esc(e.event)} · ${esc(e.period)}</h3><div class="recent-facts">발표 ${esc(e.date)} ${esc(e.time)} · ${esc(e.facts)}</div>${e.commentary?`<p><b>${esc(e.commentary.headline)}</b></p><p>${esc(e.commentary.summary)}</p><div class="muted">AI 해석 초안 · IB ${e.commentary.houses.map(h=>esc(h.house)).join(' · ')||'근거 미확보'}</div>`:'<p class="muted">새 실제값 수록 · 해석 검토 대기</p>'}<button class="recent-open" data-recent-id="${esc(e.id)}">IB별 코멘트·원문 보기 →</button></article>`).join(''):'<div class="empty">최근 3일에 발표되거나 해석이 갱신된 지표가 없습니다. 기준일을 바꾸면 이전 업데이트를 볼 수 있습니다.</div>';
}
function openRecent(id){
  const e=DATA.events.find(x=>x.id===id);if(!e)return;
  country=e.country_code;theme=e.theme;selected=e.id;
  $('month').value=e.release_month;$('search').value='';$('releaseState').value='actual';render();
  $('detail').scrollIntoView({behavior:'smooth',block:'start'});
}
$('recentDate').value=new Date(Date.now()+9*3600000).toISOString().slice(0,10);
$('recentDate').addEventListener('change',renderRecent);
$('recentList').addEventListener('click',ev=>{const b=ev.target.closest('[data-recent-id]');if(b)openRecent(b.dataset.recentId)});
renderRecent();
