# -*- coding: utf-8 -*-
"""
build_earnings_calendar.py — 기업실적 발표 달력 생성기
------------------------------------------------------
입력 : 기업실적.xlsx (블룸버그 EVTS 내보내기 — Name / Ticker / Date 사용)
출력 : earnings_dashboard.html (월 달력 형태, 날짜 칸에 기업 표시)

실행 : python build_earnings_calendar.py
"""
import os
import json
import datetime as dt
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, "기업실적.xlsx")
MCAP = os.path.join(BASE, "marketcap.json")   # Bloomberg ticker → 시총(USD). 정렬용
OUT  = os.path.join(BASE, "earnings_dashboard.html")


def load_events():
    df = pd.read_excel(SRC)
    df.columns = [str(c).strip() for c in df.columns]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Name"]).sort_values("Date")

    mcap = {}
    if os.path.exists(MCAP):
        with open(MCAP, encoding="utf-8") as f:
            mcap = {k: v for k, v in json.load(f).items() if isinstance(v, (int, float))}

    events = []
    for _, r in df.iterrows():
        d = r["Date"]
        tkr = str(r.get("Ticker", "") or "").strip()
        events.append({
            "date":   d.strftime("%Y-%m-%d"),
            "time":   d.strftime("%H:%M"),
            "name":   str(r["Name"]).strip(),
            "ticker": tkr,
            "period": str(r.get("Period", "") or "").strip(),
            "mcap":   mcap.get(tkr, 0),
        })
    # 같은 날짜 안에서는 시총 큰 순서로 (달력 칸 위쪽 = 대형주)
    events.sort(key=lambda e: (e["date"], -e["mcap"], e["time"]))
    return events


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
.gen{font-size:11px;color:var(--muted);}
.monthbar{display:flex;align-items:center;gap:10px;margin-bottom:12px;}
.mbtn{background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px 13px;cursor:pointer;font-size:14px;font-weight:700;}
.mbtn:hover{background:var(--head);}
.mtitle{font-size:18px;font-weight:800;min-width:130px;text-align:center;}
.cal{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;}
.dow,.week{display:grid;grid-template-columns:repeat(7,1fr);}
.dow div{padding:8px 0;text-align:center;font-size:11px;font-weight:700;color:var(--muted);background:var(--head);border-bottom:1px solid var(--line);}
.day{height:124px;overflow:hidden;border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:6px 6px 8px;position:relative;}
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
.detail td.p{color:var(--muted);width:70px;}
</style></head><body><div class="wrap">
<header class="top">
  <div class="brand">Earnings Calendar<small>기업실적 발표 일정</small></div>
  <div class="gen">generated __GEN__ · 총 __CNT__건</div>
</header>
<div class="monthbar">
  <button class="mbtn" onclick="mv(-1)">&#8592;</button>
  <div class="mtitle" id="mtitle"></div>
  <button class="mbtn" onclick="mv(1)">&#8594;</button>
</div>
<div class="cal"><div class="dow"><div>월</div><div>화</div><div>수</div><div>목</div><div>금</div><div>토</div><div>일</div></div><div id="grid"></div></div>
<div class="detail" id="detail"></div>
<script>
const EVENTS = __DATA__;
const byDate = {};
EVENTS.forEach(e=>{ (byDate[e.date] = byDate[e.date]||[]).push(e); });
const months = [...new Set(EVENTS.map(e=>e.date.slice(0,7)))].sort();
const todayStr = new Date().toISOString().slice(0,10);
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
        inner+='<span class="chip'+(ds<todayStr?' past':'')+'" title="'+e.name+' ('+e.time+', '+e.period+')">'+e.name+'</span>';
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
  evs.forEach(e=>{ h+='<tr><td class="t">'+e.time+'</td><td><b>'+e.name+'</b> <span style="color:#9aa0a6">'+e.ticker+'</span></td><td class="p">'+e.period+'</td></tr>'; });
  h+='</table>';
  const dv=document.getElementById('detail'); dv.innerHTML=h; dv.className='detail on';
}
render();
</script></div></body></html>
"""


def main():
    events = load_events()
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(events, ensure_ascii=False))
            .replace("__GEN__", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__CNT__", str(len(events))))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[saved] {OUT} ({len(events)} events)")


if __name__ == "__main__":
    main()
