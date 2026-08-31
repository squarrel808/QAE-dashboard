# haver-api_macrographs

Growth Dashboard(블룸버그 기반)의 국가별 차트를 **Haver 데이터로 재현**하는 파이프라인.
원본 엑셀의 차트 XML을 파싱해 "어떤 지표들이 한 차트에 묶여 있는지"를 그대로 추출했고,
각 블룸버그 티커는 Haver 카탈로그 덤프(db_catalog/canada_catalog) 기준으로 매핑했다.

## 실행 (회사 PC, Haver DLX Direct 로그인 상태에서)

```
cd C:\Users\infomax\Documents\python\QAE\haver\haver-api_macrographs
python run_all.py
```

→ `Macro_Graphs_Haver.xlsx` 생성. 국가별 차트 시트(UK/DE/FR/IT/CA/JP/AU) + `{국가}_data` 시트.

개별 실행: `python fetch_macrographs.py` (수집만) / `python build_graphs.py` (차트만 다시 그림).
데이터는 증분 없이 매번 2010-01-01부터 전체 재수집(127개 시리즈, 1~2분).

## 파일 구조

| 파일 | 역할 |
|---|---|
| `charts_config.xlsx` | **차트·시리즈 구성 원장 (수정은 여기서)** — Charts / Series / Skipped 시트 |
| `fetch_macrographs.py` | Series 시트의 haver_ticker 수집 → `macro_raw_data.xlsx` (Wide/Metadata) |
| `build_graphs.py` | 변환(transform) 적용 후 차트 생성 → `Macro_Graphs_Haver.xlsx` |
| `haver_client.py` | Haver DLX 래퍼 (haver-api_PCA/haver_provider.py 축약판) |
| `run_all.py` | fetch → build 일괄 실행 |

## charts_config.xlsx 편집법

- **Series 시트**가 핵심. 한 행 = 차트 안의 시리즈 하나.
  - `haver_ticker`: `CODE@DATABASE` 형식 (예: `S112ELUR@G10`)
  - `transform`: `level` / `yoy` / `mom` / `diff` / `3mma`, `+`로 조합 가능(예: `yoy+3mma`)
    - yoy는 Metadata의 주기(M/Q/W)에 맞춰 12/4/52기 자동 적용
  - `axis`: `primary` / `secondary` (보조축)
  - `type`: `line` / `bar`
- 차트 추가: Charts 시트에 chart_id 행 추가 + Series 시트에 같은 chart_id로 시리즈 행 추가.
- **Skipped 시트**: 원본 대시보드에 있었지만 뺀 시리즈와 사유
  (블룸버그·Citi·Nanos 독점지수, Haver 미보유 Indeed 구인공고, 원천 불명 파생열 등).

## 주의사항

- 블룸버그는 YoY 가공치를 주는 경우가 많지만 Haver는 대부분 레벨 원계열이라,
  매핑 때 "YoY 변환 필요"로 표시된 시리즈는 transform=yoy로 자동 설정돼 있다.
- S&P Global PMI(INTSRVYS DB)는 **2021년 이후만** 수록 — 차트 앞부분이 비는 게 정상.
- 호주 소매판매(retail trade)는 ABS 월간 계열이 2025-06에 중단(DISC) — ANZ DB 후속 계열 확인 필요.
- 매핑은 지표 "의미" 기준(공식 대응표 아님). 레벨/단위가 원본 차트와 다를 수 있으니
  이상해 보이는 차트는 Series 시트의 `haver_descriptor`·`note` 열로 원계열을 확인할 것.
- 전체 매핑 근거는 채팅으로 전달된 `Haver_ticker_mapping_260804.xlsx` 참고 (신뢰도·미발견 목록 포함).
