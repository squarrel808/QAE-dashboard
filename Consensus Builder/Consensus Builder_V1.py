# -*- coding: utf-8 -*-
"""
Consensus Builder_V1
====================
세 스크립트를 한 번에 순서대로 실행하는 통합 런처.

    1) merge_xlsb_to_xlsx.py   xlsb -> history\..._YYYYMMDD.xlsx 병합
    2) CPI consensus.py        cpi_consensus_dashboard.html 생성
    3) GDP consensus.py        gdp_consensus_dashboard.html 생성

각 스크립트는 같은 폴더에 있는 기존 파일을 그대로 재사용하며,
충돌 방지를 위해 각각 독립 프로세스로 실행한다.

사용법:
    python "Consensus Builder_V1.py"            # 오늘 날짜로 merge 후 전체 실행
    python "Consensus Builder_V1.py" 20260609   # merge 날짜를 직접 지정
"""

import os
import sys
import subprocess

# 이 런처가 있는 폴더 = 기준 폴더 (다른 데서 돌려도 OK)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# (표시 이름, 스크립트 파일명, 추가 인자) 순서대로 실행
#  · hawkdove 는 옆 policytone 폴더의 대시보드 생성기. 기존 stance_index.csv 로 HTML만 재생성.
#    (수집·채점까지 새로 돌리려면 policytone\master.py 를 따로 실행)
STEPS = [
    ("merge xlsb -> xlsx", "merge_xlsb_to_xlsx.py", sys.argv[1:2]),  # 날짜 인자 있으면 전달
    ("CPI consensus",      "CPI consensus.py",      []),
    ("GDP consensus",      "GDP consensus.py",      []),
    ("Hawk-Dove 대시보드", os.path.join("..", "policytone", "hawkdove_dashboard.py"), []),
]


def run_step(title, script_name, extra_args):
    script_path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"!! [{title}] 스크립트를 찾을 수 없음: {script_path}")
        return False

    print("\n" + "=" * 60)
    print(f">> [{title}] 실행: {script_name}")
    print("=" * 60)

    # 같은 파이썬 인터프리터로, 기준 폴더에서 실행
    cmd = [sys.executable, script_path] + list(extra_args)
    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode != 0:
        print(f"!! [{title}] 실패 (exit code {result.returncode})")
        return False

    print(f"++ [{title}] 완료")
    return True


def main():
    print("=== Consensus Builder_V1 시작 ===")
    print(f"기준 폴더: {BASE_DIR}")

    for title, script_name, extra_args in STEPS:
        ok = run_step(title, script_name, extra_args)
        if not ok:
            print("\n=== 중단: 위 단계가 실패해서 다음 단계를 진행하지 않습니다 ===")
            sys.exit(1)

    print("\n=== 전체 완료 ===")
    print("  - cpi_consensus_dashboard.html")
    print("  - gdp_consensus_dashboard.html")
    print("  - ..\\policytone\\hawkdove_dashboard.html")
    print("브라우저에서 열어보세요!")


if __name__ == '__main__':
    main()
