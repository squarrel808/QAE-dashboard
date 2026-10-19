# -*- coding: utf-8 -*-
"""
build_earnings_calendar.py — 기업실적 발표 달력 생성기
------------------------------------------------------
입력 : ____Rawdata___/실적발표*.txt — 최신 수정 파일만 사용, 엑셀 폴백 없음
출력 : earnings_dashboard.html (월 달력 형태, 날짜 칸에 기업 표시)

실행 : python build_earnings_calendar.py
"""
import os
import json
import re
from html import escape
import datetime as dt
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW_DIR = Path(os.environ.get("QAE_RAWDATA_DIR") or BASE.parent / "____Rawdata___")
OUT = BASE / "earnings_dashboard.html"


def select_source():
    files = [p for p in RAW_DIR.glob("실적발표*.txt") if p.is_file() and not p.name.startswith("~$")]
    if not files:
        raise FileNotFoundError(f"실적발표*.txt 원본이 없습니다: {RAW_DIR}")
    return max(files, key=lambda p: (p.stat().st_mtime_ns, p.name))


def parse_events(text):
    # The supplied export can have every cell/row concatenated with no delimiter.
    header = "CompanyTickerMarket Cap (USD)Expected Report Date"
    compact = re.sub(r"\s+", "", text.lstrip("\ufeff"))
    if not compact.startswith(re.sub(r"\s+", "", header)):
        raise ValueError("실적발표 TXT 열 제목을 확인하세요.")
    body = re.sub(r"^\s*Company\s*Ticker\s*Market\s*Cap\s*\(USD\)\s*Expected\s*Report\s*Date", "", text.lstrip("\ufeff"))
    pattern = re.compile(r"(?P<label>.+?)(?P<cap>\d{1,3}(?:,\d{3})+)\s*(?P<date>\d{4}-\d{2}-\d{2})", re.S)
    events, cursor, seen = [], 0, set()
    for match in pattern.finditer(body):
        if body[cursor:match.start()].strip():
            raise ValueError("해석하지 못한 원본 행이 있습니다.")
        label = match['label'].strip()
        split = re.fullmatch(r"(.*?)([A-Z][A-Z0-9/.-]*)", label, re.S)
        if not split:
            raise ValueError(f"기업명/티커를 분리할 수 없습니다: {label}")
        name, ticker = split.groups()
        if not name and len(ticker) % 2 == 0 and ticker[:len(ticker)//2] == ticker[len(ticker)//2:]:
            name = ticker[:len(ticker)//2]
            ticker = name
        elif ticker.startswith('PLC') and name.endswith(' '):
            name += 'PLC'
            ticker = ticker[3:]
        if not name.strip() or not ticker:
            raise ValueError(f"기업명/티커가 모호합니다: {label}")
        date = dt.date.fromisoformat(match['date']).isoformat()
        if ticker in seen:
            raise ValueError(f"중복 티커: {ticker}")
        seen.add(ticker)
        events.append(dict(date=date, time="시간 미제공", name=name.strip(), ticker=ticker,
                           period="예상 발표일", mcap=int(match['cap'].replace(',', ''))))
        cursor = match.end()
    if body[cursor:].strip() or not events:
        raise ValueError("원본 전체를 읽지 못했습니다. 기존 달력을 유지합니다.")
    events.sort(key=lambda e: (e['date'], -e['mcap'], e['ticker']))
    return events


def load_events(source=None):
    source = Path(source) if source else select_source()
    content = source.read_bytes()
    for encoding in ('utf-8-sig', 'utf-16', 'cp949'):
        try:
            text = content.decode(encoding)
            return parse_events(text)
        except UnicodeError:
            continue
    raise ValueError("TXT 인코딩을 읽을 수 없습니다.")


TEMPLATE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Earnings Calendar</title>
<style>
:root{--ink:#1a1c1f;--muted:#9aa0a6;--line:#e8e8e6;--head:#f4f3f1;--badge:#6e1f1f;}
*{box-sizing:border-box}
body{margin:0;background:#f7f6f3;color:var(--ink);font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;}
.wrap{max-width:1150px;margin:0 auto;padding:26px 20px 70px;}
header.top{display:flex;align-items:flex-end;justify-content:space-between;border-bottom:2px solid var(--ink);padding-bottom:12px;margin-bottom:16px;}
.brand{font-family:Georgia,serif;font-size:24px;font-weight:700;}
.brand small{display:block;font-family:sans-serif;font-size:11px;font-weight:600;letter-spacing:.18em;color:var(--muted);margin-top:4px;}
.gen{font-size:11px;color:var(--muted);}.source{font-size:12px;color:#60656b;line-height:1.7;}
.monthbar{display:flex;align-items:center;gap:10px;margin-bottom:12px;}
.mbtn{background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px 13px;cursor:pointer;font-size:14px;font-weight:700;}
.mbtn:hover{background:var(--head);}
.mtitle{font-size:18px;font-weight:800;min-width:130px;text-align:center;}
.cal{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;}
.dow,.week{display:grid;grid-template-columns:repeat(7,1fr);}
.dow div{padding:8px 0;text-align:center;font-size:11px;font-weight:700;color:var(--muted);background:var(--head);border-bottom:1px solid var(--line);}
.day{height:150px;overflow:hidden;border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:6px 6px 8px;position:relative;}
.day:nth-child(7n){border-right:none;}
.day.out{background:#fbfaf8;color:#c9c9c6;}
.day.today{background:#fdf6ee;}
.dnum{font-size:12px;font-weight:700;margin-bottom:4px;}
.day.today .dnum{color:var(--badge);}
.chip{display:block;height:19px;line-height:15px;font-size:11px;font-weight:600;background:var(--head);border:1px solid var(--line);border-radius:5px;padding:1px 5px;margin-bottom:3px;cursor:default;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.chip.past{opacity:.45;}
.more{font-size:10px;color:var(--badge);font-weight:700;cursor:pointer;}
.day.sel{outline:2px solid var(--badge);outline-offset:-2px;}
.detail{margin-top:14px;background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px;display:none;}
.detail.on{display:block;}
.detail h3{margin:0 0 8px;font-size:14px;}
.detail table{width:100%;border-collapse:collapse;font-size:13px;}
.detail td{padding:5px 8px;border-bottom:1px solid var(--line);}
.detail td.t{color:var(--muted);white-space:nowrap;width:60px;font-variant-numeric:tabular-nums;}
.detail td.p{color:var(--muted);width:100px;white-space:nowrap;}
</style></head><body><div class="wrap">
<header class="top">
  <div class="brand">Earnings Calendar<small>기업실적 발표 일정</small></div>
  <div class="gen">화면 생성 __GEN__ · 총 __CNT__건</div>
</header>
<p class="source">원본 __SOURCE__ · 원본 수정 __MODIFIED__<br>예상 발표일 · 날짜는 원본 그대로 표시하며 시간·시간대는 제공되지 않았습니다.</p>
<div class="monthbar">
  <button class="mbtn" onclick="mv(-1)">&#8592;</button>
  <div class="mtitle" id="mtitle"></div>
  <button class="mbtn" onclick="mv(1)">&#8594;</button>
</div>
<div class="cal"><div class="dow"><div>월</div><div>화</div><div>수</div><div>목</div><div>금</div><div>토</div><div>일</div></div><div id="grid"></div></div>
<div class="detail" id="detail"></div>
<script>
const EVENTS = __DATA__;
const esc = v => String(v).replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const byDate = {};
EVENTS.forEach(e=>{ (byDate[e.date] = byDate[e.date]||[]).push(e); });
const months = [...new Set(EVENTS.map(e=>e.date.slice(0,7)))].sort();
const todayStr = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
let cur = months.includes(todayStr.slice(0,7)) ? todayStr.slice(0,7) : months[0];

function mv(d){
  const [y,m] = cur.split('-').map(Number);
  const nd = new Date(y, m-1+d, 1);
  cur = nd.getFullYear()+'-'+String(nd.getMonth()+1).padStart(2,'0');
  render();
}
function render(){
  const [y,m] = cur.split('-').map(Number);
  document.getElementById('mtitle').textContent = y+'년 '+m+'월';
  const first = new Date(y, m-1, 1);
  const start = new Date(first); start.setDate(1 - ((first.getDay()+6)%7)); // 월요일 시작
  let html='';
  for(let w=0; w<6; w++){
    html+='<div class="week">';
    for(let i=0;i<7;i++){
      const d = new Date(start); d.setDate(start.getDate()+w*7+i);
      const ds = d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
      const out = (d.getMonth()+1)!==m;
      const evs = byDate[ds]||[];
      let cls='day'+(out?' out':'')+(ds===todayStr?' today':'');
      let inner='<div class="dnum">'+d.getDate()+'</div>';
      const MAX=4;
      evs.slice(0,MAX).forEach(e=>{
        inner+='<span class="chip'+(ds<todayStr?' past':'')+'" title="'+esc(e.name)+' ('+e.time+', '+e.period+')">'+esc(e.name)+'</span>';
      });
      if(evs.length>MAX) inner+='<span class="more">+'+(evs.length-MAX)+' more</span>';
      html+='<div class="'+cls+'" data-d="'+ds+'" onclick="pick(this)">'+inner+'</div>';
    }
    html+='</div>';
  }
  document.getElementById('grid').innerHTML=html;
  document.getElementById('detail').className='detail';
}
function pick(el){
  const ds = el.getAttribute('data-d');
  const evs = byDate[ds]||[];
  document.querySelectorAll('.day.sel').forEach(x=>x.classList.remove('sel'));
  if(!evs.length){ document.getElementById('detail').className='detail'; return; }
  el.classList.add('sel');
  let h='<h3>'+ds+' · '+evs.length+'건</h3><table>';
  evs.forEach(e=>{ h+='<tr><td class="t">'+e.time+'</td><td><b>'+esc(e.name)+'</b> <span style="color:#9aa0a6">'+esc(e.ticker)+'</span></td><td class="p">'+e.period+'</td></tr>'; });
  h+='</table>';
  const dv=document.getElementById('detail'); dv.innerHTML=h; dv.className='detail on';
}
render();
</script></div></body></html>
"""


def main():
    source = select_source()
    events = load_events(source)
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(events, ensure_ascii=False).replace("<", "\\u003c"))
            .replace("__SOURCE__", escape(source.name))
            .replace("__MODIFIED__", dt.datetime.fromtimestamp(source.stat().st_mtime, dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"))
            .replace("__GEN__", dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"))
            .replace("__CNT__", str(len(events))))
    OUT.with_suffix(".tmp").write_text(html, encoding="utf-8")
    OUT.with_suffix(".tmp").replace(OUT)
    print(f"[saved] {OUT} ({len(events)} events)")


if __name__ == "__main__":
    main()
