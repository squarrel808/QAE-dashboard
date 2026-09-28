# -*- coding: utf-8 -*-
"""
cme_dashboard.py  ―  멀티 프로젝트 자동화 대시보드 생성기 (v2)

구조 (아파트 관리사무소 게시판에 비유):
  [대문]    projects.json 에 등록된 프로젝트들을 한 줄씩:
            프로젝트 제목 / 실행 예정일 / 직전 실행 성공·실패
  [디테일]  프로젝트를 클릭하면:
            - 단계별 소요시간 가로 바차트 (예: 수집 711초 ██████, 전송 8초 █)
            - 각 단계의 pass/fail
            - 단계를 클릭하면 상세 로그 (실패 티커 목록 + 그 단계의 실행 로그 원문)

데이터 출처 (프로젝트마다 logs_dir 안):
  run_history.csv  실행 1건 = 1줄 요약        → 대문의 직전 실행, 디테일 요약
  run_steps.csv    실행 1건 = 단계 수만큼 줄   → 바차트 (run_cme.py 가 기록)
  run_failures.csv 실패 티커 상세             → 단계 클릭 시 펼침
  cme_*.log 등 일별 로그                      → 단계 클릭 시 로그 원문 발췌

'실행 예정일' 우선순위:
  1) projects.json 의 schtasks_name → 윈도우 작업 스케줄러에 직접 조회 (가장 정확)
  2) schedule_hint → 적힌 글자 그대로 표시
  3) 둘 다 없으면 과거 실행 패턴(평일 + 평소 실행 시각)으로 추정 → "(추정)" 표시

사용법:
  python cme_dashboard.py            # 갱신 + 브라우저 열기
  python cme_dashboard.py --no-open  # 갱신만 (run_cme.py 가 매 실행 끝에 이렇게 부름)

외부 라이브러리 불필요. 산출물: 이 폴더의 cme_dashboard.html (오프라인에서 열림)
"""

import os
import re
import sys
import csv
import json
import html
import glob
import statistics
import subprocess
import webbrowser
from datetime import datetime, timedelta

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))     # ...\python
PROJECTS_JSON = os.path.join(BASE_DIR, "projects.json")
OUT_HTML      = os.path.join(BASE_DIR, "scheduler_dashboard.html")

MAX_RUNS_WITH_LOGS = 30    # 로그 원문을 HTML 에 심는 최근 실행 수 (파일 비대 방지)
MAX_LOG_LINES      = 200   # 단계당 로그 발췌 최대 줄수 (앞 150 + 뒤 50)

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


# ──────────────────────── 파일 읽기 도우미 ────────────────────────
def read_csv_dicts(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_projects():
    with open(PROJECTS_JSON, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("projects", [])


# ──────────────────── 일별 로그에서 단계별 원문 발췌 ────────────────────
TS = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"
RE_RUN   = re.compile(TS + r" =+ .*?\(run_id=(\w+)\)")
RE_START = re.compile(TS + r" ───── ▶ (\S+) 실행 시작")
RE_END   = re.compile(TS + r" ───── ◀ (\S+) 종료")


def extract_step_logs(logs_dir, wanted_run_ids):
    """일별 .log 들을 훑어 { run_id: { 스크립트파일명: [로그 줄들] } } 로 반환.
       ▶ 시작 ~ ◀ 종료 사이의 줄들을 그 단계의 로그로 본다."""
    out = {}
    for path in sorted(glob.glob(os.path.join(logs_dir, "*.log"))):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                run_id, cur_script, buf = None, None, []
                for raw in f:
                    line = raw.rstrip("\n")
                    m = RE_RUN.match(line)
                    if m:
                        run_id, cur_script, buf = m.group(2), None, []
                        continue
                    m = RE_START.match(line)
                    if m and run_id in wanted_run_ids:
                        cur_script, buf = m.group(2), []
                        continue
                    m = RE_END.match(line)
                    if m and run_id in wanted_run_ids and cur_script:
                        if len(buf) > MAX_LOG_LINES:
                            buf = (buf[:150]
                                   + [f"    ... (중간 {len(buf)-200}줄 생략) ..."]
                                   + buf[-50:])
                        out.setdefault(run_id, {})[cur_script] = buf
                        cur_script, buf = None, []
                        continue
                    if cur_script is not None:
                        buf.append(line)
        except Exception:
            continue   # 로그 하나가 깨져도 대시보드 전체는 계속
    return out


# ──────────────────────── 실행 예정 계산 ────────────────────────
def next_run_from_schtasks(task_name):
    """윈도우 작업 스케줄러에 '다음 실행 시간'을 직접 물어본다. 실패하면 None."""
    if not task_name or os.name != "nt":
        return None
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", task_name, "/FO", "LIST", "/V"],
                           capture_output=True, timeout=10)
        text = r.stdout.decode("utf-8", errors="replace")
        if not text.strip():
            text = r.stdout.decode("cp949", errors="replace")
        for line in text.splitlines():
            if ("다음 실행 시간" in line) or ("Next Run Time" in line):
                val = line.split(":", 1)[1].strip()
                if val and val not in ("N/A", "해당 없음"):
                    return val
    except Exception:
        pass
    return None


def next_run_estimate(runs):
    """과거 실행들의 '평소 실행 시각(중앙값)' + 평일 규칙으로 다음 실행을 추정."""
    times = []
    for r in runs:
        try:
            dt = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
            times.append(dt.hour * 3600 + dt.minute * 60 + dt.second)
        except Exception:
            continue
    if not times:
        return None
    med = int(statistics.median(times))
    hh, mm = med // 3600, (med % 3600) // 60
    now = datetime.now()
    cand = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cand <= now:
        cand += timedelta(days=1)
    while cand.weekday() >= 5:          # 토(5)/일(6) 건너뜀
        cand += timedelta(days=1)
    return f"{cand:%Y-%m-%d} ({WEEKDAY_KO[cand.weekday()]}) {cand:%H:%M}"


def compute_next_run(proj, runs):
    v = next_run_from_schtasks(proj.get("schtasks_name", ""))
    if v:
        return v, "스케줄러"
    if proj.get("schedule_hint"):
        return proj["schedule_hint"], "수동 입력"
    v = next_run_estimate(runs)
    if v:
        return v, "추정"
    return "-", "기록 없음"


# ──────────────────────── 프로젝트 데이터 수집 ────────────────────────
def build_project_data(proj):
    logs_dir = os.path.join(BASE_DIR, proj["logs_dir"].replace("/", os.sep))
    runs      = read_csv_dicts(os.path.join(logs_dir, "run_history.csv"))
    steps     = read_csv_dicts(os.path.join(logs_dir, "run_steps.csv"))
    fail_rows = read_csv_dicts(os.path.join(logs_dir, "run_failures.csv"))

    runs.sort(key=lambda r: r.get("run_id", ""), reverse=True)   # 최신순

    steps_by_run = {}
    for s in steps:
        steps_by_run.setdefault(s.get("run_id", ""), []).append(s)

    failures_by_run = {}
    for r in fail_rows:
        failures_by_run.setdefault(r.get("run_id", ""), []).append(
            {"security": r.get("security", ""), "status": r.get("status", "")})

    recent_ids = {r["run_id"] for r in runs[:MAX_RUNS_WITH_LOGS]}
    logs_by_run = extract_step_logs(logs_dir, recent_ids)

    next_run, next_src = compute_next_run(proj, runs)

    return {
        "id": proj["id"],
        "title": proj["title"],
        "next_run": next_run,
        "next_run_source": next_src,
        "runs": runs,
        "steps_by_run": steps_by_run,
        "failures_by_run": failures_by_run,
        "logs_by_run": logs_by_run,
    }


def refresh_botari():
    """대시보드를 만들기 전에 '보따리' 다운로드 점검 CSV를 최신화한다.
       (botari_monitor.py 가 있으면 조용히 실행, 없거나 실패해도 대시보드는 계속)"""
    try:
        import botari_monitor
        botari_monitor.main()
    except Exception as e:
        print(f"(보따리 점검 건너뜀: {e})")


def build():
    refresh_botari()
    projects = [build_project_data(p) for p in load_projects()]
    import importlib.util
    monitor_path = os.path.join(BASE_DIR, "QAE", "_자동화", "ib_interpretation_monitor.py")
    spec = importlib.util.spec_from_file_location("ib_monitor", monitor_path)
    monitor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor)
    projects = [p for p in projects if p["id"] != "qae_ib_interpretation"]
    projects.append(monitor.sync())
    for project in projects:
        if project["id"] == "qae":
            project["scheduler_status"] = monitor.deployment_status()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    page = (HTML_TEMPLATE
            .replace("/*__DATA__*/", json.dumps(projects, ensure_ascii=False))
            .replace("__GENERATED__", html.escape(generated)))
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(page)
    return OUT_HTML, len(projects)


# ════════════════════════════ HTML/JS ════════════════════════════
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>프로젝트 자동화 대시보드</title>
<style>
  :root{
    --bg:#0f172a; --card:#1e293b; --line:#334155; --txt:#e2e8f0; --muted:#94a3b8;
    --ok:#22c55e; --skip:#38bdf8; --fail:#ef4444; --warn:#f59e0b; --accent:#818cf8;
  }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--txt);
       font-family:"Segoe UI",system-ui,"Malgun Gothic",sans-serif;}
  .wrap{max-width:1100px;margin:0 auto;padding:28px 20px 60px;}
  h1{font-size:22px;margin:0 0 4px;}
  .sub{color:var(--muted);font-size:13px;margin-bottom:22px;}
  .box{background:var(--card);border:1px solid var(--line);border-radius:12px;
       padding:16px;margin-bottom:20px;overflow-x:auto;}
  .box h2{font-size:14px;margin:0 0 12px;color:var(--muted);font-weight:600;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th,td{padding:10px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap;}
  th{color:var(--muted);font-weight:600;font-size:12px;}
  .badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:700;}
  .b-ok{background:rgba(34,197,94,.18);color:var(--ok);}
  .b-skip{background:rgba(56,189,248,.18);color:var(--skip);}
  .b-fail{background:rgba(239,68,68,.18);color:var(--fail);}
  .b-na{background:rgba(148,163,184,.18);color:var(--muted);}
  .muted{color:var(--muted);}
  .empty{color:var(--muted);text-align:center;padding:40px;}
  /* 대문 */
  tr.projrow{cursor:pointer;}
  tr.projrow:hover td{background:rgba(129,140,248,.08);}
  .projtitle{font-weight:700;font-size:14px;color:var(--accent);}
  .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:3px;}
  /* 디테일 */
  .backbtn{cursor:pointer;background:none;border:1px solid var(--line);color:var(--muted);
           border-radius:8px;padding:5px 14px;font-size:13px;margin-bottom:14px;}
  .backbtn:hover{color:var(--txt);border-color:var(--accent);}
  .runsel{background:#0b1220;color:var(--txt);border:1px solid var(--line);
          border-radius:8px;padding:6px 10px;font-size:13px;}
  .kpis{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 4px;}
  .kpi{background:#0b1220;border:1px solid var(--line);border-radius:10px;
       padding:8px 14px;font-size:12.5px;}
  .kpi .lbl{color:var(--muted);font-size:11px;display:block;margin-bottom:2px;}
  /* 단계 바차트 */
  .steprow{cursor:pointer;border:1px solid var(--line);border-radius:10px;
           padding:10px 14px;margin-bottom:8px;background:#0b1220;}
  .steprow:hover{border-color:var(--accent);}
  .steptop{display:flex;align-items:center;gap:10px;font-size:13px;}
  .stepname{min-width:190px;font-weight:600;}
  .bartrack{flex:1;background:#111c33;border-radius:6px;height:22px;position:relative;overflow:hidden;}
  .barfill{height:100%;border-radius:6px;min-width:2px;}
  .bardur{min-width:90px;text-align:right;font-variant-numeric:tabular-nums;}
  .stepdetail{display:none;margin-top:12px;border-top:1px solid var(--line);padding-top:12px;}
  .fitem{display:inline-flex;gap:6px;align-items:center;margin:3px 8px 3px 0;
         background:#111c33;border:1px solid var(--line);border-radius:8px;padding:4px 9px;font-size:12px;}
  .fitem .st{color:var(--fail);font-weight:700;font-size:11px;}
  pre.log{background:#020617;border:1px solid var(--line);border-radius:8px;
          padding:12px;font-size:11.5px;line-height:1.55;overflow-x:auto;
          max-height:420px;overflow-y:auto;white-space:pre;color:#cbd5e1;}
  .errmsg{color:var(--warn);font-size:12.5px;margin:6px 0;}
</style>
</head>
<body>
<div class="wrap" id="app"></div>

<script>
const PROJECTS = /*__DATA__*/;
const GENERATED = "__GENERATED__";

function esc(s){ return (s==null?"":String(s)).replace(/[&<>]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
function num(v){ const n=parseInt(v,10); return isNaN(n)?0:n; }
function isRunOk(r){
  if(r.monitor_status) return r.monitor_status === "PUBLISHED";
  // snowflake_result 는 나중에 추가된 컬럼이라 옛 실행에는 비어 있다.
  // 비어 있으면 그 단계가 없던 시절이므로 성공 판정에서 제외한다.
  const sf = r.snowflake_result;
  const sfOk = !sf || sf==="LOADED";
  return r.collect_result==="OK"
      && (r.send_result==="SENT"||r.send_result==="SKIPPED")
      && sfOk;
}
function fmtDur(sec){
  if(sec === "" || sec == null) return "미기록";
  sec = num(sec);
  if(sec >= 60) return Math.floor(sec/60)+"분 "+(sec%60)+"초";
  return sec+"초";
}
function sendBadge(s){
  const map={SENT:"b-ok",SKIPPED:"b-skip",FAILED:"b-fail",NOT_RUN:"b-na"};
  return `<span class="badge ${map[s]||'b-na'}">${esc(s||'-')}</span>`;
}
function sfBadge(s){
  // 옛 실행은 값이 비어 있다. 실패가 아니라 '해당 없음' 으로 표시한다.
  if(!s) return '<span class="badge b-na">해당 없음</span>';
  const map={LOADED:"b-ok",FAILED:"b-fail",NOT_RUN:"b-na"};
  return `<span class="badge ${map[s]||'b-na'}">${esc(s)}</span>`;
}

/* ─────────── 대문 (프로젝트 리스트) ─────────── */
function runBadge(r){
  const st=r.monitor_status;
  if(st==='NO_RECORD') return '<span class="badge b-na">실행 기록 없음</span>';
  if(st==='RUNNING') {
    const old=Date.now()-new Date(r.started_iso).getTime()>6*3600000;
    return `<span class="badge b-skip">${old?'종료 미확인':'실행 중'}</span>`;
  }
  return isRunOk(r)?'<span class="badge b-ok">완료</span>':'<span class="badge b-fail">실패·보류</span>';
}
function schedulerStatus(p){
  const s=p.scheduler_status;
  if(!s) return '';
  if(s.unavailable) return '<div class="muted">Windows 예약 조회 불가</div>';
  const rc=Number(s.result), ok=rc===0, running=rc===267009 || s.state==='Running';
  const result=running?'실행 중':ok?'종료 정상 (배포 확인 별도)':'비정상 종료 0x'+rc.toString(16).toUpperCase();
  return `<div class="muted">Windows 예약: ${s.enabled?'활성':'비활성'} · ${esc(s.last_run.slice(0,19).replace('T',' '))}<br>${esc(result)}<br>다음: ${esc(s.next_run.slice(0,19).replace('T',' '))}${s.cached?'<br>조회 캐시: '+esc(s.observed_at.slice(0,19)):''}</div>`;
}
function dailyStatus(p){
  if(!p.daily_check) return '';
  const kst=new Date(Date.now()+9*3600000), today=kst.toISOString().slice(0,10);
  const due=kst.getUTCHours()*60+kst.getUTCMinutes()>=p.schedule_hour*60+p.schedule_minute;
  const found=p.runs.some(r=>r.start_time.slice(0,10)===today && r.monitor_status!=='NO_RECORD');
  const failure=p.runs.find(r=>r.start_time.slice(0,10)===today && r.execution_origin==='scheduled' && r.monitor_status==='FAILED');
  if(failure) return '<div class="errmsg">오늘 예약 실패: '+esc(failure.error.split('. ')[0])+'</div><span class="muted">최근 처리: </span>';
  return !found?`<span class="badge b-na">${due?'오늘 실행 기록 없음':'오늘 실행 대기'}</span> `:'';
}
function renderHome(){
  let rows = PROJECTS.map(p=>{
    const last = p.runs[0];
    const lastBadge = !last ? '<span class="badge b-na">기록 없음</span>' : runBadge(last);
    const lastTime = last ? last.start_time : "-";
    const dots = p.runs.slice(0,5).reverse().map(r=>
      `<span class="dot" style="background:${r.monitor_status==='NO_RECORD'?'var(--muted)':r.monitor_status==='RUNNING'?'var(--warn)':isRunOk(r)?'var(--ok)':'var(--fail)'}" title="${esc(r.start_time)}"></span>`).join("");
    const srcNote = p.next_run_source==="추정" ? ' <span class="muted">(추정)</span>'
                  : p.next_run_source==="스케줄러" ? ''
                  : p.next_run_source==="수동 입력" ? '' : '';
    return `<tr class="projrow" onclick="showDetail('${p.id}')">
      <td class="projtitle">${esc(p.title)}</td>
      <td>${esc(p.next_run)}${srcNote}</td>
      <td>${dailyStatus(p)}${schedulerStatus(p)}${lastBadge} <span class="muted" style="font-size:11.5px">${esc(lastTime)}</span></td>
      <td>${dots||'<span class="muted">-</span>'}</td>
      <td class="muted">${p.runs.length}회</td>
    </tr>`;
  }).join("");
  document.getElementById("app").innerHTML = `
    <h1>프로젝트 자동화 대시보드</h1>
    <div class="sub">생성 시각: ${esc(GENERATED)} · 프로젝트를 클릭하면 상세 화면으로 이동합니다</div>
    <div class="box">
      <table><thead><tr>
        <th>프로젝트</th><th>실행 예정</th><th>직전 실행</th><th>최근 5회</th><th>총 실행</th>
      </tr></thead><tbody>${rows ||
        '<tr><td colspan="5" class="empty">projects.json 에 등록된 프로젝트가 없습니다.</td></tr>'}</tbody></table>
    </div>`;
}

/* ─────────── 디테일 (단계 바차트 + 로그) ─────────── */
function showDetail(pid, runId){
  const p = PROJECTS.find(x=>x.id===pid);
  if(!p){ renderHome(); return; }
  if(!p.runs.length){
    document.getElementById("app").innerHTML = `
      <button class="backbtn" onclick="renderHome()">← 프로젝트 목록</button>
      <h1>${esc(p.title)}</h1>
      <div class="empty">아직 실행 이력이 없습니다.</div>`;
    return;
  }
  const run = p.runs.find(r=>r.run_id===runId) || p.runs[0];
  const rid = run.run_id;

  // 실행 선택 드롭다운 (최신순)
  const opts = p.runs.map(r=>{
    const mark = r.monitor_status === "NO_RECORD" ? "?" : r.monitor_status === "RUNNING" ? "▶" : isRunOk(r) ? "✅" : "❌";
    return `<option value="${esc(r.run_id)}" ${r.run_id===rid?"selected":""}>${mark} ${esc(r.start_time)} (${fmtDur(r.duration_sec)})</option>`;
  }).join("");

  // 단계 데이터: run_steps.csv 에 있으면 그걸, 없으면(옛 실행) 전체 시간 1개로 대체
  let steps = (p.steps_by_run[rid]||[]).slice();
  let approx = false;
  if(!steps.length && !run.monitor_status){
    approx = true;
    steps = [{step:"전체 (단계 기록 없음)", duration_sec:run.duration_sec,
              result:isRunOk(run)?"OK":"FAILED", start_time:run.start_time, end_time:run.end_time}];
  }
  const maxDur = Math.max(...steps.map(s=>num(s.duration_sec)), 1);

  const stepRows = steps.map((s,i)=>{
    const okStep = s.result==="OK";
    const w = Math.max(100*num(s.duration_sec)/maxDur, 1.5);
    const color = okStep ? "var(--ok)" : "var(--fail)";
    return `<div class="steprow" onclick="toggleStep(event,'sd-${i}')">
      <div class="steptop">
        <span class="stepname">${esc(s.step)}</span>
        <div class="bartrack"><div class="barfill" style="width:${w}%;background:${color}"></div></div>
        <span class="bardur">${fmtDur(s.duration_sec)}</span>
        <span class="badge ${okStep?'b-ok':'b-fail'}">${okStep?'PASS':'FAIL'}</span>
      </div>
      <div class="stepdetail" id="sd-${i}">${stepDetailHtml(p, run, s)}</div>
    </div>`;
  }).join("");

  document.getElementById("app").innerHTML = `
    <button class="backbtn" onclick="renderHome()">← 프로젝트 목록</button>
    <h1>${esc(p.title)}</h1>
    <div class="sub">실행 선택:
      <select class="runsel" onchange="showDetail('${pid}', this.value)">${opts}</select>
    </div>
    <div class="kpis">
      <div class="kpi"><span class="lbl">실행 결과</span>${runBadge(run)}</div>
      <div class="kpi"><span class="lbl">총 소요</span>${fmtDur(run.duration_sec)}</div>
      <div class="kpi"><span class="lbl">성공/전체</span>${esc(run.ok_count)}/${esc(run.total_count)} OK</div>
      <div class="kpi"><span class="lbl">전송</span>${sendBadge(run.send_result)}</div>
      ${run.snowflake_result ? `<div class="kpi"><span class="lbl">적재</span>${sfBadge(run.snowflake_result)}</div>` : ""}
      <div class="kpi"><span class="lbl">${p.daily_check?"수치 기준일":"거래일"}</span>${esc(run.trade_date||'-')}</div>
    </div>
    ${run.error && run.error.trim() ? `<div class="errmsg">⚠ ${esc(run.error)}</div>` : ""}
    <div class="box">
      <h2>단계별 소요시간 ${approx?'<span class="muted">· 이 실행은 단계 기록이 없어 전체 시간만 표시</span>':''} · 단계를 클릭하면 상세 로그가 펼쳐집니다</h2>
      ${stepRows || '<div class="muted">단계 실행 기록 없음</div>'}
    </div>`;
}

function stepDetailHtml(p, run, s){
  let inner = "";
  const isCollect   = s.step.indexOf("수집")===0 || s.step.indexOf("전체")===0;
  const isSend      = s.step.indexOf("전송")===0;
  const isSnowflake = s.step.indexOf("적재")===0;
  // 수집 단계이거나, (수집이 아니어도) 실패한 단계면 실패 항목 목록을 같이 보여준다.
  const showFails = isCollect || s.result !== "OK";

  if(showFails){
    const fails = p.failures_by_run[run.run_id] || [];
    if(fails.length){
      inner += `<div style="margin-bottom:10px"><b style="color:var(--fail)">실패 항목 ${fails.length}개</b><br>`
             + fails.map(f=>`<span class="fitem">${esc(f.security)} <span class="st">${esc(f.status)}</span></span>`).join("")
             + `</div>`;
    } else {
      inner += `<div class="muted" style="margin-bottom:10px">실패 항목 없음 — ${esc(run.ok_count)}/${esc(run.total_count)} 전부 성공</div>`;
    }
  }
  if(isSend){
    inner += `<div style="margin-bottom:10px">전송 결과: ${sendBadge(run.send_result)}`
           + (run.send_flag==="0" ? ' <span class="muted">(직전과 같은 거래일 → 중복 방지 스킵)</span>' : '')
           + `</div>`;
  }
  if(isSnowflake){
    inner += `<div style="margin-bottom:10px">적재 결과: ${sfBadge(run.snowflake_result)}`
           + ` <span class="muted">TAA_DB_DEV.RAW.CME_SETTLE</span>`
           + `<br><span class="muted">값이 기존과 같으면 새로 넣지 않습니다.`
           + ` 아래 로그의 inserted 가 0 이어도 정상입니다.</span></div>`;
  }

  // 이 단계의 실행 로그 원문 (단계 label 안의 스크립트명으로 매칭)
  const logs = p.logs_by_run[run.run_id] || {};
  let lines = null;
  const m = s.step.match(/\(([^)]+)\)/);            // "수집 (seleniumcme.py)" → seleniumcme.py
  if(m && logs[m[1]]) lines = logs[m[1]];
  else if(Object.keys(logs).length===1) lines = logs[Object.keys(logs)[0]];

  if(lines && lines.length){
    inner += `<pre class="log">${esc(lines.join("\n"))}</pre>`;
  } else {
    inner += `<div class="muted">이 실행의 로그 원문이 없습니다 (오래된 실행이거나 로그 파일 삭제됨).</div>`;
  }
  return inner;
}

function toggleStep(ev, id){
  if(ev.target.closest("pre")) return;   // 로그 안 드래그/클릭은 무시
  const el = document.getElementById(id);
  el.style.display = (el.style.display==="block") ? "none" : "block";
}

renderHome();
// Reload the generated file to show updates written by begin/finish hooks.
setTimeout(()=>location.reload(),60000);
</script>
</body>
</html>
"""


def _safeprint(msg):
    """cp949 콘솔에서 이모지 등으로 인쇄가 깨져도 죽지 않도록."""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))


if __name__ == "__main__":
    out, n = build()
    _safeprint(f"✅ 대시보드 생성: {out}  (프로젝트 {n}개)")
    if "--no-open" not in sys.argv:
        try:
            webbrowser.open("file:///" + out.replace("\\", "/"))
        except Exception as e:
            print(f"(브라우저 자동 열기 실패, 파일을 직접 열어주세요: {e})")
