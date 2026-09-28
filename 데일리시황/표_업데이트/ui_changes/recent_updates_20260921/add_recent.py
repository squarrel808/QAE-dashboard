import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = '''
.recent-updates{margin:0 0 24px}.recent-updates .panelhead{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}.recent-list{padding:0 20px}.recent-item{padding:18px 0;border-bottom:1px solid var(--line)}.recent-item:last-child{border-bottom:0}.recent-item h3{font-size:16px;margin:8px 0}.recent-item p{font-size:13px;line-height:1.85;margin:7px 0;max-width:1100px}.recent-meta{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.recent-open{border:1px solid var(--green);background:white;color:var(--green);padding:7px 12px;border-radius:6px;margin-top:6px}.recent-facts{font-size:12px;color:var(--muted);line-height:1.8}.recent-controls{display:flex;gap:7px;align-items:center;font-size:13px}
'''
HTML = '''
<section class="panel recent-updates" aria-labelledby="recentTitle">
<div class="panelhead"><div><h2 id="recentTitle">최근 3일 업데이트 <span id="recentCount" class="tag"></span></h2><div id="recentNote" class="muted"></div><div class="muted">모든 국가·지표 종류 · 최근 발표 또는 IB 해석 갱신 · 아래 필터와 무관하게 표시</div></div><div class="recent-controls"><label for="recentDate">기준일</label><input id="recentDate" type="date"></div></div>
<div id="recentList" class="recent-list"></div>
</section>
'''
JS = '''
function recentUpdates(events,end){
  if(!/^\\d{4}-\\d{2}-\\d{2}$/.test(end))return [];
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
'''

baseline = json.loads((HERE/'baseline.json').read_text(encoding='utf-8'))
for name, digest in baseline.items():
    p = Path(name)
    assert hashlib.sha256(p.read_bytes()).hexdigest() == digest, 'Concurrent modification: '+name
for name in baseline:
    p = Path(name); text = p.read_text(encoding='utf-8')
    assert 'id="recentList"' not in text
    text = text.replace('</style>', CSS+'</style>', 1)
    text = text.replace('<div class="controls"><label for="month">', HTML+'<div class="controls"><label for="month">', 1)
    text = text.replace('</script></body>', JS+'</script></body>', 1)
    assert 'id="recentList"' in text and 'function recentUpdates' in text
    p.write_text(text, encoding='utf-8')
print('Updated maintained template and current published WECO page')
