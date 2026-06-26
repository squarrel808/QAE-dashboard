# -*- coding: utf-8 -*-
"""
build_pca_json.py — PCA 모듈 데이터 빌더
원본 PCA/pca_dashboard.html 에 구워진 `const DATA = {...}` 블롭을 추출해
public/data/pca.json 으로 저장한다. (화면은 components/Pca.tsx 가 Recharts로 그림)

원본 데이터를 새로 만들려면 먼저 PCA/pca_gdp.py 등으로 pca_dashboard.html 을 재생성한 뒤
이 스크립트를 돌리면 된다.

실행:  python scripts/build_pca_json.py
"""
import os, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
SRC = os.path.join(REPO, "PCA", "pca_dashboard.html")
OUT = os.path.join(ROOT, "public", "data", "pca.json")


def main():
    if not os.path.exists(SRC):
        raise SystemExit("원본 없음: " + SRC)
    txt = open(SRC, encoding="utf-8", errors="ignore").read()
    m = re.search(r"const DATA\s*=\s*(\{.*?\});", txt, re.S)
    if not m:
        raise SystemExit("pca_dashboard.html 에서 const DATA 를 찾지 못했습니다(파일 손상?).")
    data = json.loads(m.group(1))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    vs = data.get("versions", {})
    print("[saved]", OUT, "| country:", data.get("country"),
          "| versions:", list(vs.keys()),
          "| YoY dates:", len(vs.get("YoY", {}).get("dates", [])))


if __name__ == "__main__":
    main()
