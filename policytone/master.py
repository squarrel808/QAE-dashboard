# -*- coding: utf-8 -*-
"""
master.py — 매파/완화 파이프라인 전체를 한 번에 순서대로 실행
=========================================================================
    1) collect.py            웹 수집 → speeches_meta.xlsx + bodies/*.txt
    2) score.py              채점·집계·지수화 → speech_scores.csv / stance_index.csv
    3) hawkdove_dashboard.py 대시보드 HTML 생성 → hawkdove_dashboard.html

각 단계는 독립 프로세스로 실행하고, 한 단계라도 실패하면 멈춘다.
이 파일이 있는 policytone 폴더 기준이라 어디서 돌려도 OK.

사용법:
    python master.py            # 1→2→3 전부
    python master.py score      # 2,3 만 (수집 건너뜀)
    python master.py dash       # 3 만 (대시보드만 다시 그림)
"""
import os, sys, subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# (표시 이름, 스크립트 파일명) — 순서대로 실행
STEPS = [
    ("수집  collect",   "collect.py"),
    ("채점  score",     "score.py"),
    ("대시보드 build",  "hawkdove_dashboard.py"),
]

# 단축 인자: 특정 단계부터만 실행
START_ALIASES = {
    "collect": 0, "all": 0,
    "score": 1, "채점": 1,
    "dash": 2, "dashboard": 2, "대시보드": 2,
}


def run_step(title, script_name):
    path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(path):
        print(f"!! [{title}] 스크립트 없음: {path}")
        return False
    print("\n" + "=" * 60)
    print(f">> [{title}] 실행: {script_name}")
    print("=" * 60)
    result = subprocess.run([sys.executable, path], cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"!! [{title}] 실패 (exit code {result.returncode})")
        return False
    print(f"++ [{title}] 완료")
    return True


def main():
    start = 0
    if len(sys.argv) > 1:
        start = START_ALIASES.get(sys.argv[1].lower(), 0)
    print("=== master.py 시작 ===")
    print(f"기준 폴더: {BASE_DIR}")
    print(f"실행 단계: {[s[0] for s in STEPS[start:]]}")

    for title, script_name in STEPS[start:]:
        if not run_step(title, script_name):
            print("\n=== 중단: 위 단계 실패로 다음 단계를 진행하지 않습니다 ===")
            sys.exit(1)

    print("\n=== 전체 완료 ===")
    print("  결과: speech_scores.csv / stance_index.csv / hawkdove_dashboard.html")
    print("  hawkdove_dashboard.html 을 브라우저에서 열어보세요!")


if __name__ == "__main__":
    main()
