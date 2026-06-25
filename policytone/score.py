# -*- coding: utf-8 -*-
"""
채점 전용 스크립트 — 수집물(엑셀+txt) 읽기 → LLM 3축 채점 → 지수화 → 백테스트
=========================================================================
역할: 웹을 긁지 않는다. collect.py 가 만든 speeches_meta.xlsx 와 bodies/*.txt 만 읽어
      LLM 채점 → stance 계산 → 일별 집계 → 지수화 → (옵션) 백테스트.
      ※ 채점/집계/지수화 로직은 hawkdove_pipeline.py 와 100% 동일.
        (다른 점은 '웹 수집' 대신 '엑셀+txt 읽기' 뿐)

선행 조건:  먼저 `python collect.py` 실행 → speeches_meta.xlsx / bodies/ 생성

[종합 stance = 공식 계산]   stance = 0.5*policy_path + 0.3*inflation + 0.2*growth_labor
   · LLM 은 3축(inflation/growth_labor/policy_path)만 채점
   · stance 는 파이썬에서 계산 → 100% 재현 가능

실행:
  pip install -r requirements.txt
  (.env 에 ANTHROPIC_API_KEY=sk-ant-...  또는  export ANTHROPIC_API_KEY=...)
  python score.py
"""

import os, re, time, json, sys
import pandas as pd

# 콘솔이 cp949여도 '—' 같은 비-cp949 문자 출력 시 죽지 않게 stdout/stderr UTF-8 고정
for _s in (sys.stdout, sys.stderr):
    _rc = getattr(_s, "reconfigure", None)
    if _rc:
        try:
            _rc(encoding="utf-8", errors="replace")
        except Exception:
            pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ─────────────────────────────────────────────────────────────
# 설정  (hawkdove_pipeline.py 와 동일)
# ─────────────────────────────────────────────────────────────
MODEL         = "claude-haiku-4-5"
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")

# 산출물 저장/입력 폴더 = 이 스크립트(policytone)가 있는 폴더 (실행 위치와 무관)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

META_XLSX = os.path.join(BASE_DIR, "speeches_meta.xlsx")   # collect.py 산출물
BODY_DIR  = os.path.join(BASE_DIR, "bodies")

# 종합 stance 가중치  (합 = 1.0)
W_POLICY, W_INFL, W_GROWTH = 0.5, 0.3, 0.2

# 달력 기반 + forward-fill: 연설 없는 날도 직전 스탠스를 그대로 유지(계단식)
#   → 스탠스가 다음 연설까지 지속(중앙은행 기조는 침묵한다고 사라지지 않음)
#   → 아래 윈도우가 '연설 개수'가 아니라 '달력 일수'를 의미하게 됨 (변동성 大 감소)
#   False면 구버전(연설일만, 윈도우=연설 개수) 방식으로 복귀
USE_CALENDAR_FFILL = True

MA_WINDOW    = 1      # 이동평균 창 — 1이면 MA 사실상 끔(ffill 유지값에 직접 z-score). 평활 원하면 ↑
ROLL_WINDOW  = 1095   # z-score 롤링 표준화 창 — ffill on이면 '일수' = 3년(365×3), off면 연설 개수
USE_CONF_WEIGHT = False   # True면 confidence 가중평균, False면 단순평균

# 위원 참여도(coverage) 가중치 — 변동성 완화용
#   coverage = 그날 발언한 위원 수 / 전체 통화정책위원 수
#   다수 위원이 발언한 날은 위원회 전체 스탠스를 더 잘 대표 → 이동평균에서 큰 가중치
#   1명만 발언한 날의 극단값이 지수를 흔드는 걸 눌러준다.
USE_COVERAGE_WEIGHT = True
COMMITTEE_SIZE = {        # 전체 통화정책위원 수 (필요시 조정)
    "FED": 12,            # FOMC 의결권자 12명 (이사 7 + 뉴욕연은 + 순환 지역총재 4)
    "BOJ": 9,             # 일본은행 정책위원회 9명
    "ECB": 25,            # 정책위원회(집행이사 6 + 회원국 총재) ≈ 25 (대략치)
    "BOE": 9,             # 영란은행 통화정책위원회(MPC) 9명
}

RATES_CSV    = os.path.join(BASE_DIR, "rates_clean.csv")

MAX_BODY_CHARS = 18000   # LLM 에 보낼 본문 앞부분 길이(원본 파이프라인과 동일)
MIN_BODY_LEN   = 500     # 너무 짧은 본문은 채점 제외


def compute_stance(axes: dict) -> float:
    """종합 stance = 0.5*policy_path + 0.3*inflation + 0.2*growth_labor."""
    return (W_POLICY * axes.get("policy_path", 0)
            + W_INFL   * axes.get("inflation", 0)
            + W_GROWTH * axes.get("growth_labor", 0))


# ─────────────────────────────────────────────────────────────
# 1. LLM 채점 (3축만 — stance는 파이썬이 계산)
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """넌 채권 데스크의 통화정책 애널리스트야. 주어진 중앙은행 연설을
읽고 세 축으로만 평가해. 종합 점수는 매기지 마(우리가 따로 계산함). JSON으로만 답해.

[채점 기준 — 참고용, 절대규칙 아님. 부정·시제·문맥을 우선]
· 매파 신호: restrictive, vigilant, upside risks to inflation, premature to ease,
  overheating, higher for longer, need to tighten
· 완화 신호: accommodative, downside risks, patient, labor market softening,
  room to cut, disinflation on track, support growth

[축] 각 -2 ~ +2
· inflation:    인플레 상방 우려(+2) ↔ 하방/통제됨(-2)
· growth_labor: 성장·고용 과열/견조(+2) ↔ 둔화/약화(-2)
· policy_path:  인상·긴축 시그널(+2) ↔ 인하·완화 시그널(-2)
※ 점수는 '발화 시점의 스탠스'로. 사후 결과(예: transitory 오판)로 보정하지 마.

[confidence 기준 — 0~1]
· 0.8~1.0 : 통화정책을 직접·명확히 다루고 톤이 일관
· 0.4~0.6 : 통화정책 언급이 부수적이거나 매파·완화가 섞여 모호
· 0.0~0.3 : 거의 무관하거나 판단 근거 빈약

[기준점 예시 — 이 자(尺)에 맞춰라]   ※ 운영 전 실제 연설로 교체
· (강한 매파) "물가 안정 회복까지 제약적 기조 유지" → policy_path:+2, inflation:+2, growth_labor:+1
· (약한 매파) "정상화·테이퍼 처음 구체화하나 '아직 멀었다'로 완충"
  → policy_path:+0.5, inflation:+1, growth_labor:+1
· (완화) "정책 제약 완화 시작 적절" → policy_path:-2, inflation:-1, growth_labor:-1
· (중립) "완화적 환경 유지하되 정상화 시점 판단" → policy_path:0, inflation:0, growth_labor:0

[출력 — JSON only]
{"axes":{"inflation":<num>,"growth_labor":<num>,"policy_path":<num>},
 "confidence":<0~1>,"key_phrases":[...],"reasoning":"<한 문장>"}"""


# LLM이 반드시 이 형태로만 답하도록 강제하는 스키마 (Structured Outputs)
#   → 깨진 JSON / 따옴표 미이스케이프로 인한 파싱 실패를 API 레벨에서 차단
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "axes": {
            "type": "object",
            "properties": {
                "inflation":    {"type": "number"},
                "growth_labor": {"type": "number"},
                "policy_path":  {"type": "number"},
            },
            "required": ["inflation", "growth_labor", "policy_path"],
            "additionalProperties": False,
        },
        "confidence":  {"type": "number"},
        "key_phrases": {"type": "array", "items": {"type": "string"}},
        "reasoning":   {"type": "string"},
    },
    "required": ["axes", "confidence", "key_phrases", "reasoning"],
    "additionalProperties": False,
}


def _parse_json(raw: str) -> dict:
    raw = raw.replace("```json", "").replace("```", "")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ValueError("JSON 블록 없음")
    return json.loads(m.group(0))


def score_speech(body: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    text = (body or "")[:MAX_BODY_CHARS]
    last_err = None
    for _ in range(2):
        try:
            msg = client.messages.create(
                model=MODEL, max_tokens=1000, system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"<speech>\n{text}\n</speech>"}],
                output_config={"format": {"type": "json_schema", "schema": SCORE_SCHEMA}},
            )
            # 스키마 강제 덕분에 첫 text 블록은 항상 유효한 JSON
            txt = next(b.text for b in msg.content if b.type == "text")
            return _parse_json(txt.strip())
        except Exception as e:
            last_err = e; time.sleep(1)
    raise last_err


# ─────────────────────────────────────────────────────────────
# 2. 일별 집계 (단순/conf 가중평균) + 이동평균
# ─────────────────────────────────────────────────────────────
def aggregate_daily(scored: pd.DataFrame) -> pd.DataFrame:
    scored = scored.dropna(subset=["date"]).copy()

    def agg(g, col):
        if USE_CONF_WEIGHT and g["confidence"].sum():
            return (g[col] * g["confidence"]).sum() / g["confidence"].sum()
        return g[col].mean()

    rows = []
    for (d, b), g in scored.groupby(["date", "bank"]):
        # 그날 발언한 '서로 다른' 위원 수 / 전체 위원 수 = coverage
        n_spk = g["speaker"].nunique() if "speaker" in g.columns else len(g)
        size  = COMMITTEE_SIZE.get(b, 0)
        coverage = min(n_spk / size, 1.0) if size else 1.0
        rows.append({"date": d, "bank": b, "n": len(g),
                     "n_speakers": n_spk, "coverage": coverage,
                     "stance":       agg(g, "stance"),
                     "inflation":    agg(g, "inflation"),
                     "growth_labor": agg(g, "growth_labor"),
                     "policy_path":  agg(g, "policy_path")})
    out = pd.DataFrame(rows).sort_values("date")

    # 이동평균: coverage 가중(참여 위원 많은 날을 더 신뢰) 또는 단순평균
    for col in ["stance", "inflation", "growth_labor", "policy_path"]:
        if USE_COVERAGE_WEIGHT:
            # 가중 이동평균 = Σ(값·coverage) / Σ(coverage)  (창 = MA_WINDOW)
            num = out.assign(_wx=out[col] * out["coverage"]) \
                     .groupby("bank")["_wx"] \
                     .transform(lambda s: s.rolling(MA_WINDOW, min_periods=1).sum())
            den = out.groupby("bank")["coverage"] \
                     .transform(lambda s: s.rolling(MA_WINDOW, min_periods=1).sum())
            out[f"{col}_ma"] = (num / den).fillna(out[col])
        else:
            out[f"{col}_ma"] = out.groupby("bank")[col].transform(
                lambda s: s.rolling(MA_WINDOW, min_periods=1).mean())
    return out


# ─────────────────────────────────────────────────────────────
# 3. 지수화 — 롤링 z-score → ±100
# ─────────────────────────────────────────────────────────────
def build_index(daily: pd.DataFrame) -> pd.DataFrame:
    cols = ["stance", "inflation", "growth_labor", "policy_path"]

    # ── 구버전: 연설일만, 윈도우 = '연설 개수' 기준 ──
    if not USE_CALENDAR_FFILL:
        df = daily.copy()
        def z_to_index(s):
            mean = s.rolling(ROLL_WINDOW, min_periods=10).mean()
            std  = s.rolling(ROLL_WINDOW, min_periods=10).std()
            z = (s - mean) / std.replace(0, pd.NA)
            return (z.clip(-3, 3) / 3 * 100).fillna(0)
        for col in [f"{c}_ma" for c in cols]:
            df[col.replace("_ma", "_idx")] = df.groupby("bank")[col].transform(z_to_index)
        return df

    # ── 달력 기반 + forward-fill: 연설 없는 날도 직전 스탠스 유지 ──
    #   윈도우(MA_WINDOW/ROLL_WINDOW)가 '달력 일수'를 의미하게 된다.
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    meta_cols = [c for c in ["n", "n_speakers", "coverage"] if c in d.columns]
    outs = []
    for bank, g in d.groupby("bank"):
        g = g.sort_values("date").set_index("date")
        cal = g[cols].resample("D").mean().ffill()          # 매일 펼치고 직전값 유지
        if meta_cols:                                       # 메타는 연설일에만(나머진 0)
            cal = cal.join(g[meta_cols].resample("D").sum()
                              .reindex(cal.index, fill_value=0))
        cal.insert(0, "bank", bank)
        for c in cols:
            ma   = cal[c].rolling(MA_WINDOW, min_periods=1).mean()
            mean = ma.rolling(ROLL_WINDOW, min_periods=20).mean()
            std  = ma.rolling(ROLL_WINDOW, min_periods=20).std()
            z    = (ma - mean) / std.replace(0, pd.NA)
            cal[f"{c}_ma"]  = ma
            cal[f"{c}_idx"] = (z.clip(-3, 3) / 3 * 100).fillna(0)
        outs.append(cal.reset_index())
    return pd.concat(outs, ignore_index=True)


# ─────────────────────────────────────────────────────────────
# 4. 백테스트
# ─────────────────────────────────────────────────────────────
def backtest(index_df: pd.DataFrame, rates_csv: str, bank: str, yld_col: str):
    rates = pd.read_csv(rates_csv, parse_dates=["date"])
    s = index_df[index_df["bank"] == bank][["date", "stance_idx"]].copy()
    s["date"] = pd.to_datetime(s["date"])
    m = pd.merge_asof(rates.sort_values("date"), s.sort_values("date"),
                      on="date", direction="backward")
    print(f"\n[{bank}] 매파지수 → 향후 금리({yld_col}) 변화 상관")
    for N in (5, 10, 20):
        m[f"d{N}"] = m[yld_col].shift(-N) - m[yld_col]
        c = m[["stance_idx", f"d{N}"]].corr().iloc[0, 1]
        print(f"   향후 {N:>2}일: {c:+.3f}")
    return m


# ─────────────────────────────────────────────────────────────
# 중간 저장 — 끊겨도 여기까지 채점한 건 보존 (돈 안 날아감)
# ─────────────────────────────────────────────────────────────
def save_results(all_scored):
    if not all_scored:
        return None
    scored = pd.DataFrame(all_scored)
    scored.to_json(os.path.join(BASE_DIR, "speech_scores_full.json"),
                   orient="records", force_ascii=False, indent=2)
    cols_drop = ["body"] if "body" in scored.columns else []
    scored.drop(columns=cols_drop).to_csv(
        os.path.join(BASE_DIR, "speech_scores.csv"), index=False, encoding="utf-8-sig")
    return scored


# ─────────────────────────────────────────────────────────────
# 증분 채점 — 이미 채점한 연설은 LLM 재호출 없이 재사용 (돈/시간 절약)
#   기존 speech_scores_full.json 을 url 기준으로 로드 → 신규 연설만 채점.
# ─────────────────────────────────────────────────────────────
def load_prev_scores():
    """(기존 점수 records, 이미 채점된 url set) 반환. 없으면 ([], set())."""
    fp = os.path.join(BASE_DIR, "speech_scores_full.json")
    if not os.path.exists(fp):
        return [], set()
    try:
        old = pd.read_json(fp)
    except Exception as e:
        print("   [증분] 기존 점수 읽기 실패 — 전체 재채점:", e)
        return [], set()
    if old.empty or "url" not in old.columns:
        return [], set()
    recs = old.to_dict("records")
    done = {str(r.get("url")) for r in recs if r.get("url")}
    return recs, done


# ─────────────────────────────────────────────────────────────
# 본문 로더 — 엑셀의 body_file(상대경로) → BASE_DIR 기준으로 복원해 txt 읽기
# ─────────────────────────────────────────────────────────────
def load_body(row) -> str:
    candidates = []
    fp = row.get("body_file")
    if isinstance(fp, str) and fp:
        candidates += [fp, os.path.join(BASE_DIR, fp)]   # 절대/상대 둘 다 시도
    sid = row.get("id")
    if isinstance(sid, str) and sid:
        candidates.append(os.path.join(BODY_DIR, sid + ".txt"))  # id 로 직접 복원
    for c in candidates:
        if c and os.path.exists(c):
            with open(c, "r", encoding="utf-8") as f:
                return f.read()
    return ""


# ─────────────────────────────────────────────────────────────
# 메인 — 웹 수집 없음. 엑셀+txt 만 읽어 채점
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists(META_XLSX):
        print(f"[중단] {META_XLSX} 없음 → 먼저 `python collect.py` 를 실행하세요.")
        raise SystemExit(0)

    meta = pd.read_excel(META_XLSX)
    print(f"메타 {len(meta)}건 로드 ({META_XLSX}) — 웹 수집 없이 채점 시작")

    # 증분: 이미 채점한 연설은 건너뛰고 신규만 LLM 호출 (매번 2024년부터 재채점 방지)
    all_scored, done_urls = load_prev_scores()
    if done_urls:
        print(f"[증분] 기존 채점 {len(done_urls)}건 재사용 → 신규 연설만 채점")

    last_bank, new_cnt = None, 0
    for _, row in meta.iterrows():
        url = str(row.get("url") or "")
        if url and url in done_urls:        # 이미 채점됨 → LLM 호출 생략(돈 안 나감)
            continue
        body = load_body(row)
        if len(body) < MIN_BODY_LEN:        # 본문 없거나 너무 짧으면 스킵
            continue
        try:
            sc = score_speech(body)
            axes = sc["axes"]
            stance = compute_stance(axes)        # ← 공식으로 계산
            all_scored.append({
                "date": row.get("date"), "bank": row.get("bank"),
                "speaker": row.get("speaker", ""), "title": row.get("title", ""),
                "url": row.get("url", ""),
                "stance": stance, "confidence": sc["confidence"],
                **axes,
                "key_phrases": " | ".join(sc.get("key_phrases", [])),
                "reasoning": sc.get("reasoning", ""),
            })
            done_urls.add(url)
            new_cnt += 1
        except Exception as e:
            print("   채점 실패:", row.get("url", ""), e)

        # 은행 바뀔 때 + 신규 25건마다 중간 저장 → 끊겨도 채점분 보존
        if row.get("bank") != last_bank or (new_cnt and new_cnt % 25 == 0):
            save_results(all_scored)
            last_bank = row.get("bank")
            print(f"   [중간저장] 누적 {len(all_scored)}건 (신규 {new_cnt}건) → speech_scores.csv")

    print(f"[증분] 이번 실행 신규 채점 {new_cnt}건 / 전체 {len(all_scored)}건")

    scored = save_results(all_scored)
    if scored is None or scored.empty:
        print("채점 결과 없음 — 종료")
        raise SystemExit(0)

    daily = aggregate_daily(scored)
    index_df = build_index(daily)
    index_df.to_csv(os.path.join(BASE_DIR, "stance_index.csv"), index=False, encoding="utf-8-sig")
    print(f"\n저장 위치: {BASE_DIR}")
    print("  speech_scores.csv / speech_scores_full.json / stance_index.csv")

    # 백테스트: rates_clean.csv 있을 때만 (없으면 빨간 에러 대신 건너뜀)
    if os.path.exists(RATES_CSV):
        print("\n=== 백테스트 ===")
        rates_cols = pd.read_csv(RATES_CSV, nrows=0).columns
        banks_in_data = set(index_df["bank"].unique())
        for bank, yld in [("FED", "us2y"), ("BOJ", "jp2y"), ("ECB", "de2y"), ("BOE", "uk2y")]:
            if bank in banks_in_data and yld in rates_cols:
                backtest(index_df, RATES_CSV, bank, yld)
    else:
        print(f"\n[건너뜀] {RATES_CSV} 없음 → 백테스트 생략 "
              f"(speech_scores.csv / stance_index.csv 는 정상 저장됨)")
