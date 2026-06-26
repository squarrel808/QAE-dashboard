# -*- coding: utf-8 -*-
"""
sync_embeds.py - 원본(자체완결) 대시보드 HTML을 macro_hub/public/embeds/ 로 복사한다.

PCA / Consensus / CAI·MAP 모듈은 캔버스로 직접 그리는 복잡한 디자인이라
React로 새로 그리지 않고 '원본 렌더러를 그대로 재사용'한다(components/RawDashboard.tsx).
그 원본 HTML을 앱이 읽을 수 있는 public/embeds/ 안으로 가져오는 단계.

데이터 갱신 흐름:
  1) 각 원본 빌드 스크립트 실행 (예: PCA/pca_gdp.py, "Consensus Builder/CPI consensus.py" ...)
     -> 최신 *_dashboard.html 생성
  2) python scripts/sync_embeds.py        <- 이 파일. 최신 HTML을 embeds/ 로 복사
  3) git push -> Vercel 자동 재배포

실행:  python scripts/sync_embeds.py
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # macro_hub/
REPO = os.path.dirname(ROOT)                 # QAE-dashboard/
DEST = os.path.join(ROOT, "public", "embeds")

# (대상 파일명, 원본 경로) — 원본은 QAE-dashboard 하위 폴더들
SOURCES = {
    "pca.html": os.path.join(REPO, "PCA", "pca_dashboard.html"),
    "consensus_cpi.html": os.path.join(REPO, "Consensus Builder", "cpi_consensus_dashboard.html"),
    "consensus_gdp.html": os.path.join(REPO, "Consensus Builder", "gdp_consensus_dashboard.html"),
    "caimap.html": os.path.join(REPO, "gs_api", "cai_map_dashboard.html"),
}


def main():
    os.makedirs(DEST, exist_ok=True)
    ok, miss = 0, 0
    for name, src in SOURCES.items():
        dst = os.path.join(DEST, name)
        if not os.path.exists(src):
            print("[skip] 원본 없음:", src)
            miss += 1
            continue
        shutil.copyfile(src, dst)
        size = os.path.getsize(dst)
        tail = ""
        try:
            with open(dst, "r", encoding="utf-8", errors="ignore") as f:
                tail = f.read()[-300:]
        except Exception:
            pass
        closed = "</html>" in tail
        flag = "OK" if closed else "WARN(끝에 </html> 없음 - 원본 확인)"
        print(f"[{flag}] {name}  <- {os.path.relpath(src, REPO)}  ({size:,} bytes)")
        ok += 1
    print(f"\n완료: {ok}개 복사, {miss}개 건너뜀  ->  {DEST}")
    if miss:
        print("건너뛴 모듈은 해당 원본 빌드 스크립트를 먼저 실행하세요.")


if __name__ == "__main__":
    main()
