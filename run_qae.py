# -*- coding: utf-8 -*-
"""
run_qae.py  ―  QAE 대시보드 갱신 '지휘자(오케스트레이터)'

하는 일 (CME 의 run_cme.py 와 같은 역할):
  1) Haver 수집 → 리포트 수집 → 폴더별 데이터/HTML → macro_hub JSON/embeds
     → git push  순서대로 실행한다. 한 단계가 실패해도 멈추지 않고 끝까지 간다.
  2) 실행 결과를 상위 python 폴더의 scheduler_dashboard.py 가 읽는 형식으로 기록:
       - logs/qae_YYYYMMDD.log  : 그날 실행의 상세 로그 (단계별 ▶ ~ ◀ 구간)
       - logs/run_history.csv   : 실행 1건 = 1줄 요약
       - logs/run_steps.csv     : 단계별 소요시간 (대시보드 가로 바차트)
       - logs/run_failures.csv  : 실패한 단계 상세 (대시보드에서 클릭해 펼침)
  3) 마지막에 scheduler_dashboard.py 를 호출해 scheduler_dashboard.html 을 갱신한다.

옵션 (전체업데이트.bat 이 그대로 넘겨줌):
  /nohaver    Haver 수집 생략 (DLX 로그인 하기 싫을 때, 기존 엑셀 사용)
  /noreport   셀레니움 리포트 수집 생략
  /webonly    수집·HTML 생성 전부 생략, JSON/embeds 만 다시 굽기
  /nightly    저장된 리포트 DOCX + 웹 산출물 갱신, 실패 시 전송 중단, 실제 사이트 확인
  /nohouseviews  별도 Claude 분석 생략, 보고서 목록은 DOCX에서 갱신
  /nopush     커밋만 하고 push 안 함
  /nogit      git 을 아예 건드리지 않음 (로컬 갱신/테스트용)
  /dataonly   git add 를 산출물(macro_hub/public 등)로 제한
  /dryrun     실제로 실행하지 않고 '무엇이 돌아갈지'만 보여줌 (기록도 남기지 않음)

메모:
  - 단계 라벨의 괄호 안(예: "JSON (build_pca_json.py)")은 로그의 '▶ 이름 실행 시작'
    과 정확히 같아야 대시보드가 그 단계의 로그 원문을 찾아준다.
    Haver 는 PCA/CPI 두 폴더의 파일명이 같아서 폴더명을 붙여 구분한다.
  - 대시보드는 '수집'/'전송' 으로 시작하는 단계를 특별 취급하므로,
    수집 단계는 "수집 (...)", git push 단계는 "전송 (git)" 으로 이름 붙였다.
"""

import os
import sys
import csv
import time
import subprocess
from datetime import datetime

# ── 경로 설정 ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # ...\python\QAE
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

HISTORY_CSV = os.path.join(LOG_DIR, "run_history.csv")
FAILURES_CSV = os.path.join(LOG_DIR, "run_failures.csv")
STEPS_CSV = os.path.join(LOG_DIR, "run_steps.csv")
DAILY_LOG = os.path.join(LOG_DIR, f"qae_{datetime.now():%Y%m%d}.log")

# 상위 python 폴더의 대시보드 생성기 (매 실행 끝에 자동 갱신)
DASHBOARD_SCRIPT = os.path.join(os.path.dirname(BASE_DIR), "scheduler_dashboard.py")

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PROFILE = r"C:\selenium_profile"

# CSV 헤더 — scheduler_dashboard.py 가 이 컬럼명을 그대로 읽는다 (CME 와 동일)
HISTORY_HEADER = [
    "run_id", "start_time", "end_time", "duration_sec",
    "collect_result",   # 갱신 단계 전체 결과: OK / FAILED
    "collect_exit",     # 실패한 단계 수 (0 이면 전부 성공)
    "ok_count",         # 성공한 단계 수
    "total_count",      # 실제로 실행한 단계 수 (건너뛴 건 제외)
    "fail_count",       # 실패한 단계 수
    "trade_date",       # 이 실행의 데이터 갱신일
    "send_flag",        # 1=푸시함 / 0=푸시할 변경 없음·생략 / NA
    "send_result",      # SENT / SKIPPED / FAILED / NOT_RUN
    "send_exit",
    "error",
]
FAILURES_HEADER = ["run_id", "security", "status"]
STEPS_HEADER = ["run_id", "step", "start_time", "end_time",
                "duration_sec", "result", "exit_code"]

# ── 파이프라인 정의 ───────────────────────────────────────────────────
# (그룹, 표시 라벨, 로그용 이름, 작업폴더(QAE 기준 상대), 스크립트(작업폴더 기준 상대))
#   · 그룹  : haver / report / build / web  — 옵션으로 통째 생략 가능
#   · 로그용 이름은 공백이 없어야 한다 (대시보드 로그 파서가 \S+ 로 잡음)
PIPELINE = [
    ("haver", "수집 (haver-api_PCA/fetch_haver_to_excel.py)",
     "haver-api_PCA/fetch_haver_to_excel.py",
     os.path.join("haver", "haver-api_PCA"), "fetch_haver_to_excel.py"),
    ("haver", "수집 (haver-api_CPI/fetch_haver_to_excel.py)",
     "haver-api_CPI/fetch_haver_to_excel.py",
     os.path.join("haver", "haver-api_CPI"), "fetch_haver_to_excel.py"),

    ("collect_report", "수집 (download_reports.py)", "download_reports.py",
     "report_pipeline", "download_reports.py"),
    # PDF 재요약(summarize.py)은 제거했다. 보따리\_자동화\daily_summary.py 가 만든
    # 통합요약 DOCX 에 같은 내용이 이미 있어 같은 자료를 두 번 요약할 이유가 없다.
    # (pdfplumber 의존도 함께 사라졌다)
    ("report", "파싱 (parse_daily_docx.py)", "parse_daily_docx.py",
     "report_pipeline", "parse_daily_docx.py"),
    ("houseviews", "하우스뷰 (extract_houseviews.py)", "extract_houseviews.py",
     "report_pipeline", "extract_houseviews.py"),
    ("report", "목록 (build_reports_json.py)", "build_reports_json.py",
     "report_pipeline", "build_reports_json.py"),

    ("build", "데이터 (BeforeHTML_master.py)", "BeforeHTML_master.py",
     ".", "BeforeHTML_master.py"),
    ("build", "HTML (AfterHTML_master.py)", "AfterHTML_master.py",
     ".", "AfterHTML_master.py"),

    ("web", "JSON (build_pairbaskets_json.py)", "build_pairbaskets_json.py",
     "macro_hub", os.path.join("scripts", "build_pairbaskets_json.py")),
    ("web", "JSON (build_policy_json.py)", "build_policy_json.py",
     "macro_hub", os.path.join("scripts", "build_policy_json.py")),
    ("web", "JSON (build_consensus_json.py)", "build_consensus_json.py",
     "macro_hub", os.path.join("scripts", "build_consensus_json.py")),
    ("web", "JSON (build_pca_json.py)", "build_pca_json.py",
     "macro_hub", os.path.join("scripts", "build_pca_json.py")),
    ("web", "JSON (build_caimap_json.py)", "build_caimap_json.py",
     "macro_hub", os.path.join("scripts", "build_caimap_json.py")),
    ("web", "embeds (sync_embeds.py)", "sync_embeds.py",
     "macro_hub", os.path.join("scripts", "sync_embeds.py")),
]


# ── 로그 도우미 ───────────────────────────────────────────────────────
def log(msg):
    """화면과 일별 로그 파일에 동시에 한 줄 기록."""
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)
    with open(DAILY_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_step(run_id, step, start_dt, end_dt, exit_code):
    """단계 1개의 스톱워치 기록 → run_steps.csv (대시보드 바차트 재료)."""
    is_new = not os.path.exists(STEPS_CSV)
    with open(STEPS_CSV, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=STEPS_HEADER)
        if is_new:
            w.writeheader()
        w.writerow({
            "run_id": run_id,
            "step": step,
            "start_time": f"{start_dt:%Y-%m-%d %H:%M:%S}",
            "end_time": f"{end_dt:%Y-%m-%d %H:%M:%S}",
            "duration_sec": int((end_dt - start_dt).total_seconds()),
            "result": "OK" if exit_code == 0 else "FAILED",
            "exit_code": exit_code,
        })


def append_history(row):
    is_new = not os.path.exists(HISTORY_CSV)
    with open(HISTORY_CSV, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_HEADER)
        if is_new:
            w.writeheader()
        w.writerow(row)


def append_failures(run_id, failures):
    """실패한 단계들 → run_failures.csv (대시보드에서 단계 클릭 시 펼쳐짐)."""
    if not failures:
        return
    is_new = not os.path.exists(FAILURES_CSV)
    with open(FAILURES_CSV, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FAILURES_HEADER)
        if is_new:
            w.writeheader()
        for item in failures:
            w.writerow({"run_id": run_id,
                        "security": item["security"],
                        "status": item["status"]})


# ── 실행 도우미 ───────────────────────────────────────────────────────
def _child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _stream(proc):
    """자식 프로세스 출력을 화면과 일별 로그에 '|' 를 붙여 실시간으로 흘려보낸다."""
    with open(DAILY_LOG, "a", encoding="utf-8") as f:
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            try:
                print(f"    | {line}", flush=True)
            except UnicodeEncodeError:
                enc = sys.stdout.encoding or "utf-8"
                print(f"    | " + line.encode(enc, "replace").decode(enc, "replace"),
                      flush=True)
            f.write(f"    | {line}\n")
    proc.wait()
    return proc.returncode


def run_step(run_id, label, log_name, workdir, script):
    """파이썬 스크립트 한 단계 실행. 반환 = 종료코드.
       스크립트가 없으면 실행하지 않고 실패(2)로 기록한다."""
    cwd = os.path.normpath(os.path.join(BASE_DIR, workdir))
    target = os.path.join(cwd, script)
    start = datetime.now()
    log(f"───── ▶ {log_name} 실행 시작 ─────")

    if not os.path.exists(target):
        log(f"    | (파일 없음: {target})")
        log(f"───── ◀ {log_name} 종료 (exit=2) ─────")
        append_step(run_id, label, start, datetime.now(), 2)
        return 2

    proc = subprocess.Popen(
        [sys.executable, "-u", script],
        cwd=cwd, env=_child_env(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    rc = _stream(proc)
    log(f"───── ◀ {log_name} 종료 (exit={rc}) ─────")
    try:
        append_step(run_id, label, start, datetime.now(), rc)
    except Exception as e:
        log(f"⚠️  run_steps.csv 기록 실패(무시): {e}")
    return rc


def run_git(run_id, do_push, add_all):
    """git add → commit → push 를 한 단계로 묶어 실행.
       반환 = (send_result, send_flag, exit_code)."""
    label, log_name = "전송 (git)", "git"
    start = datetime.now()
    log(f"───── ▶ {log_name} 실행 시작 ─────")

    def git(*args):
        """git 명령 하나 실행 → (종료코드). 출력은 로그로 흘려보낸다."""
        proc = subprocess.Popen(
            ["git"] + list(args), cwd=BASE_DIR, env=_child_env(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        return _stream(proc)

    send_result, send_flag, rc = "NOT_RUN", "NA", 0
    try:
        # 다른 작업에서 이미 스테이징한 코드를 데이터 커밋에 섞지 않는다.
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], cwd=BASE_DIR,
            text=True, encoding="utf-8").splitlines()
        allowed = ("macro_hub/public/data/", "macro_hub/public/embeds/")
        if not add_all and any(not p.startswith(allowed) for p in staged):
            raise RuntimeError("다른 작업의 스테이징 변경이 있어 전송을 중단합니다")
        if add_all:
            rc = git("add", "-A")
        else:
            log("    | (/dataonly) 산출물만 스테이징")
            rc = git("add", "--", "macro_hub/public/data", "macro_hub/public/embeds")
        if rc:
            raise RuntimeError("산출물 스테이징 실패")

        # diff --cached --quiet : 0=변경없음 / 1=스테이징된 변경 있음
        diff_rc = git("diff", "--cached", "--quiet")
        if diff_rc not in (0, 1):
            raise RuntimeError("스테이징 변경 확인 실패")
        has_change = diff_rc == 1
        if not has_change:
            log("새로 커밋할 변경 없음. 이전 미전송 커밋도 확인합니다.")
            send_result, send_flag = "SKIPPED", "0"
        else:
            rc = git("commit", "-m", f"데이터 갱신 {datetime.now():%Y-%m-%d}")
            if rc != 0:
                send_result, send_flag = "FAILED", "0"
            elif not do_push:
                log("(/nopush) 커밋만 하고 push 는 생략했습니다.")
                send_result, send_flag = "SKIPPED", "0"
        if rc == 0 and do_push:
            # 이전 실행에서 commit만 성공하고 push가 실패한 경우에도 재전송.
            rc = git("push")
            if rc == 0:
                log("GitHub 전송 완료 — Vercel 배포 성공은 사이트 확인 후 확정합니다.")
                send_result, send_flag = "SENT", "1"
            else:
                log("push 실패 — 자격증명/네트워크 확인")
                send_result, send_flag = "FAILED", "1"
    except Exception as e:
        log(f"git 단계 예외: {e}")
        send_result, rc = "FAILED", 1

    log(f"───── ◀ {log_name} 종료 (exit={rc}) ─────")
    try:
        append_step(run_id, label, start, datetime.now(), rc)
    except Exception as e:
        log(f"⚠️  run_steps.csv 기록 실패(무시): {e}")
    return send_result, send_flag, rc, label


def launch_chrome():
    """셀레니움용 크롬을 디버그포트 9222 로 띄운다 (이미 떠 있으면 새 창만 뜸)."""
    if not os.path.exists(CHROME):
        log(f"⚠️  크롬을 찾지 못함(리포트 수집이 실패할 수 있음): {CHROME}")
        return
    try:
        subprocess.Popen([CHROME, "--remote-debugging-port=9222",
                          f"--user-data-dir={CHROME_PROFILE}"])
        time.sleep(7)
    except Exception as e:
        log(f"⚠️  크롬 실행 실패(무시하고 계속): {e}")


def refresh_dashboard():
    """scheduler_dashboard.py 를 호출해 scheduler_dashboard.html 갱신 (best-effort)."""
    if not os.path.exists(DASHBOARD_SCRIPT):
        log(f"ℹ️  대시보드 생성기 없음(건너뜀): {DASHBOARD_SCRIPT}")
        return
    try:
        subprocess.run([sys.executable, DASHBOARD_SCRIPT, "--no-open"],
                       cwd=os.path.dirname(DASHBOARD_SCRIPT), env=_child_env(),
                       timeout=180, check=False)
        log("🖥️  대시보드 갱신 완료 (scheduler_dashboard.html)")
    except Exception as e:
        log(f"⚠️  대시보드 갱신 실패(무시하고 계속): {e}")


# ── 옵션 파싱 ─────────────────────────────────────────────────────────
def parse_opts(argv):
    flags = {a.lstrip("-/").lower() for a in argv[1:]}
    webonly = "webonly" in flags
    nightly = "nightly" in flags
    return {
        "haver": not nightly and not webonly and "nohaver" not in flags,
        "collect_report": not nightly and not webonly and "noreport" not in flags,
        "report": nightly or (not webonly and "noreport" not in flags),
        "houseviews": "nohouseviews" not in flags and (nightly or (not webonly and "noreport" not in flags)),
        "build": not nightly and not webonly,
        "nightly": nightly,
        "web": True,
        "git": "nogit" not in flags,
        "push": "nopush" not in flags,
        # 기본은 산출물만 담는다. 이 저장소는 여러 트랙이 동시에 미커밋 상태로
        # 굴러가서, add -A 가 기본이면 작업 중인 코드까지 "데이터 갱신" 커밋
        # 하나에 쓸려 들어간다 (2026-09-01 에 84개·61개 파일로 두 번 발생).
        # 전체를 담고 싶을 때만 /addall 을 명시한다. /dataonly 는 하위호환용.
        "add_all": "addall" in flags,
        "dryrun": "dryrun" in flags,
    }


def show_plan(opt):
    """/dryrun — 실제 실행 없이 이번 옵션으로 무엇이 돌아갈지만 출력."""
    print("=" * 62)
    print("  /dryrun — 실제로는 아무것도 실행하지 않습니다 (기록도 남기지 않음)")
    print("=" * 62)
    n = 0
    for group, label, _log_name, workdir, script in PIPELINE:
        target = os.path.normpath(os.path.join(BASE_DIR, workdir, script))
        exists = "" if os.path.exists(target) else "   ⚠ 파일 없음"
        if opt.get(group, True):
            n += 1
            print(f"  [{n:>2}] {label}{exists}")
            print(f"       {target}")
        else:
            print(f"   --  {label}   (건너뜀)")
    if opt["git"]:
        how = "add -A" if opt["add_all"] else "add 산출물만(/dataonly)"
        tail = "commit + push" if opt["push"] else "commit 만(/nopush)"
        print(f"  [{n + 1:>2}] 전송 (git)  —  {how} → {tail}")
    else:
        print("   --  전송 (git)   (건너뜀 /nogit)")
    if opt["nightly"]:
        print("  야간: 저장된 DOCX → Report → 웹 데이터 → 최신성 검사 → 전송 → 실제 사이트 확인")
    print("=" * 62)
    print(f"  실행 예정 단계: {n}개")
    print(f"  로그/이력 기록 위치: {LOG_DIR}")
    print(f"  대시보드 생성기    : {DASHBOARD_SCRIPT}")
    return 0


# ── 메인 흐름 ─────────────────────────────────────────────────────────
def main():
    start = datetime.now()
    run_id = f"{start:%Y%m%d_%H%M%S}"
    opt = parse_opts(sys.argv)

    if opt["dryrun"]:
        return show_plan(opt)

    hist = {k: "" for k in HISTORY_HEADER}
    hist.update({
        "run_id": run_id,
        "start_time": f"{start:%Y-%m-%d %H:%M:%S}",
        "trade_date": f"{start:%Y-%m-%d}",
        "send_result": "NOT_RUN",
        "send_exit": "NA",
        "send_flag": "NA",
    })

    log(f"========== QAE 대시보드 갱신 시작 (run_id={run_id}) ==========")
    log(f"옵션: haver={opt['haver']} report={opt['report']} build={opt['build']} "
        f"git={opt['git']} push={opt['push']} add_all={opt['add_all']}")

    failures, ok_count, total_count = [], 0, 0
    chrome_done = False

    for group, label, log_name, workdir, script in PIPELINE:
        if not opt.get(group, True):
            log(f"⏭️  건너뜀: {label}  (옵션으로 생략)")
            continue
        # 리포트 그룹 첫 단계 직전에 셀레니움용 크롬을 띄운다
        if group == "collect_report" and not chrome_done:
            log("셀레니움용 크롬 실행 (디버그포트 9222)")
            launch_chrome()
            chrome_done = True

        rc = run_step(run_id, label, log_name, workdir, script)
        total_count += 1
        if rc == 0:
            ok_count += 1
        else:
            failures.append({"security": label, "status": f"exit {rc}"})
            if opt["nightly"]:
                log("야간 필수 단계 실패 — 이후 처리와 전송을 중단합니다")
                break

    marker = None
    if opt["nightly"] and not failures:
        check_start = datetime.now()
        total_count += 1
        try:
            from deploy_check import prepare
            marker = prepare(run_id)
            log("배포 전 검사 완료: 최신 요약 " + marker["latestSummary"])
            ok_count += 1
            append_step(run_id, "검증 (배포 전)", check_start, datetime.now(), 0)
        except Exception as exc:
            failures.append({"security": "검증 (배포 전)", "status": str(exc)})
            log("배포 전 검사 실패: " + str(exc))
            append_step(run_id, "검증 (배포 전)", check_start, datetime.now(), 1)

    # git 단계 (/nopush 면 커밋까지만, /nogit 이면 아예 건너뜀)
    if opt["nightly"] and failures:
        send_result = hist["send_result"] = "NOT_RUN"
        log("갱신 실패로 사이트 전송하지 않음")
    elif opt["git"]:
        send_result, send_flag, send_exit, git_label = run_git(
            run_id, opt["push"], opt["add_all"])
        hist["send_result"] = send_result
        hist["send_flag"] = send_flag
        hist["send_exit"] = send_exit
        if send_result == "FAILED":
            failures.append({"security": git_label, "status": f"exit {send_exit}"})
    else:
        log("⏭️  건너뜀: 전송 (git)  (/nogit)")
        send_result = hist["send_result"] = "SKIPPED"   # 성공 판정에는 영향 없게
        hist["send_flag"] = "NA"
        hist["send_exit"] = "NA"

    if marker and send_result == "SENT":
        from deploy_check import verify
        check_start = datetime.now()
        total_count += 1
        verified = verify(marker, log=log)
        append_step(run_id, "검증 (Vercel 사이트)", check_start, datetime.now(), 0 if verified else 1)
        if verified:
            ok_count += 1
        else:
            failures.append({"security": "검증 (Vercel 사이트)", "status": "15분 내 사이트 반영 확인 실패"})

    end = datetime.now()
    hist.update({
        "end_time": f"{end:%Y-%m-%d %H:%M:%S}",
        "duration_sec": int((end - start).total_seconds()),
        "ok_count": ok_count,
        "total_count": total_count,
        "fail_count": len(failures),
        "collect_exit": total_count - ok_count,
        "collect_result": "OK" if ok_count == total_count else "FAILED",
        "error": ("실패 단계: " + ", ".join(f["security"] for f in failures)) if failures else "",
    })

    append_failures(run_id, failures)
    append_history(hist)

    log(f"========== 종료 | 소요 {hist['duration_sec']}초 | "
        f"단계 {ok_count}/{total_count} 성공 | 전송={send_result} ==========")
    if failures:
        for f in failures:
            log(f"   [실패] {f['security']}  ({f['status']})")
    log(f"이력 CSV: {HISTORY_CSV}")

    refresh_dashboard()

    ok_run = (hist["collect_result"] == "OK"
              and hist["send_result"] in ("SENT", "SKIPPED"))
    return 0 if ok_run else 1


if __name__ == "__main__":
    # 오전/야간/수동 실행이 같은 산출물과 Git 인덱스를 동시에 수정하지 않도록 보호.
    if parse_opts(sys.argv)["dryrun"]:
        sys.exit(main())
    with open(os.path.join(LOG_DIR, "qae.lock"), "a+b") as lock:
        if sys.platform == "win32":
            import msvcrt
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                log("다른 QAE 갱신이 실행 중입니다 — 중복 실행하지 않음")
                sys.exit(2)
        sys.exit(main())
