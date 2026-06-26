# -*- coding: utf-8 -*-
"""
build_caimap_json.py — CAI·MAP 모듈 데이터 빌더
원본 gs_api/cai_map_dashboard.html 의 `const D = {...}` 를 추출해
public/data/caimap.json 으로 저장한다. (화면은 components/CaiMap.tsx 가 Recharts로)
실행:  python scripts/build_caimap_json.py
"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
SRC = os.path.join(REPO, "gs_api", "cai_map_dashboard.html")
OUT = os.path.join(ROOT, "public", "data", "caimap.json")


def balanced(txt, start):
    depth = 0
    for i in range(start, len(txt)):
        if txt[i] == "{":
            depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                return txt[start:i + 1]
    return None


def main():
    if not os.path.exists(SRC):
        raise SystemExit("원본 없음: " + SRC)
    txt = open(SRC, encoding="utf-8", errors="ignore").read()
    i = txt.index("const D")
    blob = balanced(txt, txt.index("{", i))
    if not blob:
        raise SystemExit("const D 추출 실패(파일 손상?).")
    data = json.loads(blob)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("[saved]", OUT, "| countries:", len(data.get("countries", [])),
          "| cai:", len(data.get("cai", {})), "| map:", len(data.get("map", {})))


if __name__ == "__main__":
    main()
