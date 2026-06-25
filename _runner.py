# -*- coding: utf-8 -*-
"""
_runner.py — 공통 실행기 (모든 BeforeHTML/AfterHTML/Master 런처가 공유)
=========================================================================
파이썬 스크립트들을 순서대로 별도 프로세스로 실행해주는 얇은 도우미.
각 런처는 이 함수만 호출하면 되므로 로직 중복이 없다.
"""
import os, sys, subprocess


def run_paths(paths, stop_on_fail=True, label=""):
    """
    paths        : 실행할 .py 절대경로 리스트 (순서대로)
    stop_on_fail : True면 한 단계 실패 시 멈춤 / False면 계속 진행
    label        : 로그용 이름
    각 스크립트는 자기 폴더(cwd)에서 실행된다.
    """
    ok = fail = 0
    if not paths:
        print(f"   [{label}] 실행할 단계 없음")
        return True
    for p in paths:
        rel = p
        if not os.path.exists(p):
            print(f"   [건너뜀] 파일 없음: {rel}")
            fail += 1
            continue
        print(f"\n=== 실행: {os.path.basename(os.path.dirname(p))}/{os.path.basename(p)} ===")
        # 자식 스크립트도 UTF-8로 출력하게 강제(cp949 콘솔에서 '—' 등으로 죽는 것 방지)
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run([sys.executable, p], cwd=os.path.dirname(p), env=env)
        if result.returncode == 0:
            ok += 1
            print(f"++ 완료: {os.path.basename(p)}")
        else:
            fail += 1
            print(f"!! 실패: {os.path.basename(p)} (exit {result.returncode})")
            if stop_on_fail:
                print("=== 중단: 위 단계 실패로 이후 단계 생략 ===")
                break
    print(f"\n[{label}] 성공 {ok} / 실패 {fail}")
    return fail == 0
