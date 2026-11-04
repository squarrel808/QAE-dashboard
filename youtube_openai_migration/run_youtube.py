# -*- coding: utf-8 -*-
"""
run_youtube.py ― 유투브 BBG 요약 자동화 '지휘자(오케스트레이터)'

run_cme.py 와 같은 뼈대입니다. 하는 일:
  1) summurizer.py 를 실행한다 (새 영상 수집 → 자막 → Claude 요약 → HTML 리포트).
  2) 실행 결과를 대시보드(scheduler_dashboard.py)가 읽는 형식 그대로 기록한다:
       logs/youtube_YYYYMMDD.log : 그날 실행의 상세 로그 (화면 출력 그대로)
       logs/run_history.csv      : 실행 1건 = 1줄 요약표
       logs/run_steps.csv        : 단계별 소요시간 (대시보드 바차트용)
       logs/run_failures.csv     : 자막 실패 영상 상세 (대시보드에서 클릭해 펼침)
  3) 마지막에 상위 python 폴더의 scheduler_dashboard.py 를 호출해 대시보드를 갱신한다.

컬럼 해석 (대시보드 호환을 위해 CME 와 '이름'은 같고 '뜻'만 다름):
  ok_count / total_count : 요약 성공 영상 수 / 새 영상 수
  fail_count             : 자막 추출 실패로 건너뛴 영상 수
  trade_date             : 리포트 날짜 (오늘)
  send_flag              : 1 = 리포트 생성됨 / 0 = 생성 안 됨
  send_result            : SENT = 리포트 생성 / SKIPPED = 새 영상 없음 / FAILED = 오류

숫자 파싱 방법: summurizer.py 의 화면 출력에서
  "새 영상: N개" / "완료! N개 영상 처리됨" / "자막 없음, 건너뜀" / "HTML 리포트 저장: ..."
줄들을 정규식으로 읽는다. (summurizer.py 를 안 고치고 겉에서 감싸기만 하는 방식)
"""

import os
import re
import sys
import csv
import subprocess
from datetime import datetime

# ── 경로 설정 ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR  = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

SUMMARIZER_SCRIPT = os.path.join(BASE_DIR, "summurizer.py")

HISTORY_CSV  = os.path.join(LOG_DIR, "run_history.csv")
FAILURES_CSV = os.path.join(LOG_DIR, "run_failures.csv")
STEPS_CSV    = os.path.join(LOG_DIR, "run_steps.csv")
DAILY_LOG    = os.path.join(LOG_DIR, f"youtube_{datetime.now():%Y%m%d}.log")

# 상위 python 폴더의 대시보드 생성기 (매 실행 끝에 자동 갱신)
DASHBOARD_SCRIPT = os.path.join(os.path.dirname(BASE_DIR), "scheduler_dashboard.py")

# CSV 헤더 — scheduler_dashboard.py 가 기대하는 컬럼과 동일해야 함
HISTORY_HEADER = [
    "run_id", "start_time", "end_time", "duration_sec",
    "collect_result", "collect_exit",
    "ok_count", "total_count", "fail_count", "trade_date",
    "send_flag", "send_result", "send_exit", "error",
]
FAILURES_HEADER = ["run_id", "security", "status"]
STEPS_HEADER    = ["run_id", "step", "start_time", "end_time",
                   "duration_sec", "result", "exit_code"]


# ── 로그 도우미 ───────────────────────────────────────────────────────
def log(msg):
    """화면과 일별 로그 파일에 동시에 한 줄 기록."""
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(DAILY_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_step(run_id, step, start_dt, end_dt, exit_code):
    """단계 1개의 스톱워치 기록 → run_steps.csv (대시보드 바차트 재료)."""
    is_new = not os.path.exists(STEPS_CSV)
    with open(STEPS_CSV, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STEPS_HEADER)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "run_id": run_id,
            "step": step,
            "start_time": f"{start_dt:%Y-%m-%d %H:%M:%S}",
            "end_time": f"{end_dt:%Y-%m-%d %H:%M:%S}",
            "duration_sec": int((end_dt - start_dt).total_seconds()),
            "result": "OK" if exit_code == 0 else "FAILED",
            "exit_code": exit_code,
        })


def run_script(script_path, run_id=None, step=None):
    """
    파이썬 스크립트를 하위 프로세스로 실행. 출력을 '실시간으로' 화면+일별 로그에
    흘려보내고, 나중에 숫자 파싱용으로 줄 목록도 모아서 반환한다.
    반환값 = (종료코드, 출력 줄 리스트)
    """
    name = os.path.basename(script_path)
    step_start = datetime.now()
    log(f"───── ▶ {name} 실행 시작 ─────")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.Popen(
        [sys.executable, "-u", script_path],
        cwd=BASE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    lines = []
    with open(DAILY_LOG, "a", encoding="utf-8") as f:
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            lines.append(line)
            print(f"    | {line}", flush=True)
            f.write(f"    | {line}\n")
    proc.wait()

    log(f"───── ◀ {name} 종료 (exit={proc.returncode}) ─────")

    if run_id and step:
        try:
            append_step(run_id, step, step_start, datetime.now(), proc.returncode)
        except Exception as e:
            log(f"⚠️  run_steps.csv 기록 실패(무시): {e}")
    return proc.returncode, lines


def parse_child_output(lines):
    """summurizer.py 출력에서 요약 숫자들을 뽑는다.
       반환: (새영상수, 요약성공수, 실패목록, 리포트경로)"""
    total, ok, report = None, None, ""
    failures, cur_title = [], ""
    for ln in lines:
        m = re.search(r"새 영상: (\d+)개", ln)
        if m:
            total = int(m.group(1))
        m = re.search(r"완료! (\d+)개 영상 처리됨", ln)
        if m:
            ok = int(m.group(1))
        m = re.search(r"▶ 처리 중: (.+)$", ln)
        if m:
            cur_title = m.group(1).strip()
        if "자막 없음, 건너뜀" in ln and cur_title:
            failures.append({"security": cur_title[:100], "status": "자막없음"})
            cur_title = ""
        if "OpenAI 요약 실패:" in ln and cur_title:
            failures.append({"security": cur_title[:100], "status": "요약실패"})
            cur_title = ""
        m = re.search(r"HTML 리포트 저장: (.+)$", ln)
        if m:
            report = m.group(1).strip()
        if "새로운 영상이 없습니다" in ln and total is None:
            total = 0
    return (total or 0), (ok or 0), failures, report


def append_history(row_dict):
    is_new = not os.path.exists(HISTORY_CSV)
    with open(HISTORY_CSV, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_HEADER)
        if is_new:
            writer.writeheader()
        writer.writerow(row_dict)


def append_failures(run_id, failures):
    if not failures:
        return
    is_new = not os.path.exists(FAILURES_CSV)
    with open(FAILURES_CSV, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FAILURES_HEADER)
        if is_new:
            writer.writeheader()
        for item in failures:
            writer.writerow({"run_id": run_id,
                             "security": item.get("security", ""),
                             "status": item.get("status", "")})


def refresh_dashboard():
    """scheduler_dashboard.py 를 조용히 실행해 대시보드 HTML 갱신 (best-effort)."""
    if not os.path.exists(DASHBOARD_SCRIPT):
        log(f"ℹ️  대시보드 생성기 없음(건너뜀): {DASHBOARD_SCRIPT}")
        return
    try:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.run([sys.executable, DASHBOARD_SCRIPT, "--no-open"],
                       cwd=os.path.dirname(DASHBOARD_SCRIPT), env=env,
                       timeout=60, check=False)
        log("🖥️  대시보드 갱신 완료")
    except Exception as e:
        log(f"⚠️  대시보드 갱신 실패(무시하고 계속): {e}")


# ── 메인 흐름 ─────────────────────────────────────────────────────────
def main():
    start = datetime.now()
    run_id = f"{start:%Y%m%d_%H%M%S}"

    hist = {k: "" for k in HISTORY_HEADER}
    hist["run_id"] = run_id
    hist["start_time"] = f"{start:%Y-%m-%d %H:%M:%S}"
    hist["send_result"] = "NOT_RUN"
    hist["send_exit"] = "NA"
    hist["send_flag"] = "NA"
    hist["fail_count"] = 0

    log(f"========== 유투브 BBG 요약 시작 (run_id={run_id}) ==========")

    error_msg = ""
    try:
        exit_code, out_lines = run_script(
            SUMMARIZER_SCRIPT, run_id, "수집·요약 (summurizer.py)")
        hist["collect_exit"] = exit_code
        hist["send_exit"] = exit_code

        total, ok, failures, report = parse_child_output(out_lines)
        hist["ok_count"] = ok
        hist["total_count"] = total
        hist["fail_count"] = len(failures)
        hist["trade_date"] = f"{start:%Y-%m-%d}"
        hist["send_flag"] = "1" if report else "0"

        append_failures(run_id, failures)
        if failures:
            preview = ", ".join(f"{x['security'][:30]}" for x in failures[:3])
            log(f"⚠️  처리 실패 {len(failures)}개 기록: {preview}"
                + (" ..." if len(failures) > 3 else ""))

        if exit_code != 0:
            hist["collect_result"] = "FAILED"
            hist["send_result"] = "FAILED"
            error_msg = f"summurizer.py 비정상 종료 (exit={exit_code})"
            log(f"❌ {error_msg}")
        else:
            hist["collect_result"] = "OK"
            if report:
                hist["send_result"] = "SENT"       # 리포트 생성됨
                log(f"✅ 성공: 새 영상 {total}개 중 {ok}개 요약 → {report}")
            else:
                hist["send_result"] = "SKIPPED"    # 새 영상 없음 (정상)
                log(f"⏭️  새 영상 없음 (또는 전부 자막 없음) → 리포트 생성 안 함")

    except Exception as e:
        error_msg = f"run_youtube.py 예외: {e}"
        if not hist["collect_result"]:
            hist["collect_result"] = "FAILED"
        hist["send_result"] = "FAILED"
        log(f"💥 {error_msg}")

    finally:
        end = datetime.now()
        hist["end_time"] = f"{end:%Y-%m-%d %H:%M:%S}"
        hist["duration_sec"] = int((end - start).total_seconds())
        hist["error"] = error_msg
        append_history(hist)
        log(f"========== 종료 | 소요 {hist['duration_sec']}초 | "
            f"결과={hist['collect_result']}/{hist['send_result']} ==========")
        refresh_dashboard()

    ok_run = (hist["collect_result"] == "OK"
              and hist["send_result"] in ("SENT", "SKIPPED"))
    return 0 if ok_run else 1


if __name__ == "__main__":
    sys.exit(main())
