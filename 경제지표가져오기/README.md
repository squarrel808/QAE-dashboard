# 경제지표 가져오기 (Economic Calendar Scraper + Dashboard)

[tradingeconomics 경제 캘린더](https://ko.tradingeconomics.com/calendar)에서
**중요도 ★★★(별 3개) + 주요 10개국**(G7 + 호주 · 중국 · 한국)의 경제지표를
selenium으로 긁어와 **CSV 저장**하고 **HTML 대시보드**를 생성합니다.

---

## ✅ 한 줄 요약 — 이거 하나만 실행하세요

```bash
python scraper_with_dashboard.py
```

→ Chrome 자동 실행 → 사이트 스크래핑 → `tradingeconomics_calendar.csv` 저장 → `dashboard.html` 생성

생성된 **`dashboard.html`** 을 더블클릭하면 브라우저에서 결과를 볼 수 있습니다.

> 실행이 끝나면 `[종료하려면 Enter를 누르세요...]` 가 뜹니다. Enter를 누르면 브라우저가 닫힙니다.

---

## 📂 파일별 역할

| 파일 | 역할 | 실행? |
|---|---|---|
| **`scraper_with_dashboard.py`** | **올인원.** 스크래핑 → CSV 저장 → 대시보드 생성까지 한 번에. **평소엔 이것만 실행.** | ✅ 실행 |
| `te_calendar.py` | 스크래핑만 하고 **CSV까지만** 저장 (대시보드 생성 X). 데이터만 필요할 때. | ✅ 실행 |
| `build_dashboard.py` | DataFrame을 받아 `dashboard.html` 을 만드는 **모듈**. 위 스크립트들이 내부에서 사용. 단독 실행 시 데모 데이터로 샘플 대시보드 생성. | ⚙️ 모듈 |

### 산출물 (실행하면 생기는 파일)

| 파일 | 설명 |
|---|---|
| `tradingeconomics_calendar.csv` | 스크래핑 결과 데이터 (날짜 · 시간 · 국가 · 지표명 · 실제 · 이전 · 예측치) |
| `tradingeconomics_calendar_YYYYMMDD_HHMMSS.csv` | 위 CSV가 Excel 등에서 **열려 있어 잠겨 있을 때** 자동으로 대신 저장되는 백업 파일 |
| `dashboard.html` | 데이터가 통째로 박힌 대시보드 HTML (더블클릭해서 봄) |
| `economic_calendar_dashboard.html` | 이전에 만들어 둔 대시보드 결과물(샘플) |

---

## 🔧 사전 준비

- **Python 3.7+** 와 **Google Chrome** 설치
- 패키지 설치:
  ```bash
  pip install selenium pandas
  ```
  > 크롬 드라이버는 selenium 4의 Selenium Manager가 자동으로 받아오므로 따로 설치 불필요.

---

## 🧩 동작 흐름 (scraper_with_dashboard.py)

```
1) 사이트 접속        https://ko.tradingeconomics.com/calendar
2) 충격(중요도) 필터   ★★★ (별 3개)만 선택
3) 나라 필터          G7 + 호주 + 중국 + 한국 (10개국)
4) 테이블 추출        지표 행 파싱
5) CSV 저장          tradingeconomics_calendar.csv  (잠겨 있으면 백업 이름)
6) 대시보드 생성       dashboard.html
```

대상 국가는 각 스크립트 상단 `TARGET_COUNTRIES` 딕셔너리에서 수정할 수 있습니다.

---

## ⚠️ 자주 겪는 문제

| 증상 | 원인 / 해결 |
|---|---|
| `Permission denied: tradingeconomics_calendar.csv` | CSV가 **Excel에서 열려 있음**. 닫고 다시 실행. (안 닫아도 백업 이름으로 저장되고 대시보드는 정상 생성됨) |
| `ImportError: cannot import name 'webdriver' from 'selenium'` | 파일 이름을 `selenium.py` 로 지으면 안 됨 (라이브러리와 충돌). 다른 이름으로 변경. |
| `UnicodeEncodeError ... cp949` | Windows 콘솔 인코딩 문제. 스크립트 상단에서 stdout을 UTF-8로 설정해 해결돼 있음. |
| 대시보드에서 모든 행이 "날짜미상 / 예정" 으로 나옴 | `날짜`·`실제` 컬럼이 비어 추출되는 알려진 한계. `extract_table()` 의 셀 인덱스를 사이트 구조에 맞게 보정 필요. |

---

## 📊 대시보드 보는 법

- **칩(나라 배지)** 클릭 → 해당 국가 표시/숨김 토글
- **서프라이즈 배지**: `실제 − 예측치` 방향만 표시 (▲ 상회 / ▼ 하회 / = 부합)
  - 상회·하회가 호재인지 악재인지는 지표마다 다르므로 판단하지 않음
- 실제값이 비어 있으면(발표 전) **예정** 으로 표시
