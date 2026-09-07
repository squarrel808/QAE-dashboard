# QAE Macro Dashboard

> 기준일 2026-09-07 · 배포처 https://macro-hub-nu.vercel.app

블룸버그·Haver·GS API·증권사 리서치를 모아 매일 아침 대시보드로 굽고 Vercel에 올리는 파이프라인.

---

## 한 장 요약

```
[06:00] 리서치 자동수집          Desktop\보따리\YYMMDD\ 에 리서치 PDF 저장
[??:??] daily_summary.py        같은 폴더에 일일리서치통합요약_*.docx 생성  ← 스케줄 미등록, 수동
[07:00] QAE대시보드갱신
          전체업데이트.bat /nohaver /dataonly /nopause
            └ run_qae.py
                ├ 수집   Haver / 증권사 리포트
                ├ 가공   폴더별 BeforeHTML → AfterHTML → 각 dashboard.html
                ├ 변환   macro_hub/scripts/build_*_json.py → public/data/*.json
                ├ 동기   sync_embeds.py → public/embeds/*.html
                └ 전송   git commit + push
                            └ Vercel 이 감지해 자동 재배포 (1~2분)
```

**배포는 push 가 트리거다.** 따로 배포 명령이 없다.

---

## 실행

| 상황 | 명령 |
|---|---|
| 그냥 전체 갱신 | `전체업데이트.bat` 더블클릭 |
| Haver 까지 새로 받기 | DLX Direct 로그인한 상태에서 `전체업데이트.bat` |
| 뭐가 돌지 미리 보기 | `전체업데이트.bat /dryrun` |
| 웹 산출물만 다시 굽기 | `전체업데이트.bat /webonly` |

### 주요 인수

| 인수 | 뜻 |
|---|---|
| `/nohaver` | Haver 수집 생략. 무인 실행은 DLX 로그인이 안 돼 항상 이걸 붙인다 |
| `/noreport` | 셀레니움 리포트 수집 생략 |
| `/webonly` | 수집·생성 건너뛰고 JSON/embeds 만 |
| `/addall` | git 에 **저장소 전체**를 담는다 (기본은 산출물만) |
| `/nopush` | 커밋만 하고 push 안 함 |
| `/nogit` | git 단계 통째로 생략 |
| `/nopause` | 끝에서 키 입력 안 기다림 (스케줄러용) |
| `/dryrun` | 실행 안 하고 계획만 출력 |

> **git 기본값은 산출물만이다.** 이 저장소는 여러 작업이 동시에 미커밋 상태로 굴러가서,
> `add -A` 가 기본이면 작업 중인 코드까지 "데이터 갱신" 커밋에 쓸려 들어간다.
> 전체를 올려야 할 때만 `/addall` 을 명시한다.

---

## 탭별 데이터 출처

| 탭 | 화면 | 출처 | 갱신 방법 |
|---|---|---|---|
| 경제지표 | `/econ` | `블벅경제지표\*.xlsx` | **파일을 폴더에 넣으면 끝** |
| 실적 캘린더 | `/earnings` | releasecalendar | 자동 |
| Report | `/reports` | `Desktop\보따리\*\일일리서치통합요약_*.docx` | 통합요약 DOCX 생성 시 자동 |
| PCA | `/pca` | Haver (`haver-api_PCA`) | Haver 로그인 후 수집 |
| CAI | `/caimap` | GS Marquee API | 자동 |
| CPI 분포 | `/cpidist` | Haver (`haver-api_CPI`) | Haver 로그인 후 수집 |
| Consensus | `/consensus` | `Consensus Builder\ECFC_*.xlsb` | **파일을 폴더에 넣으면 끝** |
| Policy Tone | `/policy` | 중앙은행 연설문 스크래핑 + Claude 채점 | 자동 (`policytone\.env` 에 API 키 필요) |
| Equity | `/equity` | GS Pair Baskets API | 자동 |

### 파일을 넣어서 갱신하는 두 곳

**`블벅경제지표\`** — 블룸버그 이코노믹 캘린더 내보내기
- 파일명 규칙 없음. **폴더에 최근 쌓인 순서**로 고른다
- 형식 두 가지를 자동 판별: WECO 표준(`Date Time`/`Country Code`), BQuant `CALENDAR()`(`Country`/`Date tie`/`time`)
- 지표/연설 구분도 파일명이 아니라 내용(Survey·Actual 채움률, Relevance)으로 판별
- 지표는 **컨센서스(Survey) 있는 행만** 표시. 연설·이벤트는 전량
- 1개만 넣어도 그 파일에 해당하는 만큼 갱신된다
- 자세히: `블벅경제지표\사용법.md`

**`Consensus Builder\`** — ECFC 컨센서스
- `ECFC_Growth Consesus_수정.xlsb` / `ECFC_Inflation Consesus_수정.xlsb` 두 개를 덮어쓴다
- xlsb 에는 최근 60일치만 들어있고, 누적 시계열은 `history\` 에 쌓인다
- 병합 시 `history` 의 **최신 산출물**을 베이스로 이어붙인다 (원본 `_수정.xlsx` 는 오래 전에 멈춰 있음)
- 7일 넘는 공백이 생기면 로그에 경고가 찍힌다

---

## 폴더 구조

```
QAE/
├ run_qae.py                오케스트레이터 (실행 순서·git·로그)
├ 전체업데이트.bat            진입점
├ _자동화/                   스케줄 등록 배치
│
├ 블벅경제지표/               ← 경제지표 입력 (xlsx 넣는 곳)
│   └ load_weco.py           파일 판별·정규화
├ 경제지표가져오기/            weco_dashboard.py → dashboard.html
├ Consensus Builder/         ← 컨센서스 입력 (xlsb 넣는 곳)
│   ├ merge_xlsb_to_xlsx.py  xlsb + history → 누적 xlsx
│   ├ CPI/GDP consensus.py   대시보드
│   ├ CPI distribution.py    CPI 분포
│   └ history/               날짜별 누적본
├ haver/
│   ├ haver-api_PCA/         PCA 원본 수집
│   └ haver-api_CPI/         CPI 분포 원본 수집
├ PCA/                       pca_gdp.py — 국가별 활동지수
├ gs_api/                    CAI 맵, 페어 바스켓
├ policytone/                중앙은행 연설 수집·채점
├ releasecalendar/           실적 캘린더
├ report_pipeline/           리서치 DOCX → 하우스뷰·목록
└ macro_hub/                 Next.js 사이트 (Vercel 배포 대상)
    ├ app/                   탭별 라우트
    ├ components/            차트 컴포넌트
    ├ scripts/               build_*_json.py, sync_embeds.py
    └ public/data, embeds    사이트가 읽는 산출물
```

---

## 자동화

| 작업 | 시각 | 내용 |
|---|---|---|
| 리서치 자동수집 | 06:00 | `Desktop\보따리\크롬_연동.bat` — PDF 수집 |
| QAE대시보드갱신 | 07:00 | 전체 갱신 + 배포 (약 13분) |

**순서가 중요하다.** 리포트 요약은 "오늘 날짜 폴더가 있으면 그것만" 보므로, 수집(06:00)이 QAE(07:00)보다 먼저여야 당일 자료가 반영된다.

작업 스케줄러는 전역 대기열이 없어 **같은 시각 작업이 동시에 실행된다.** 새 작업을 넣을 때 07:00~07:15 구간을 피할 것.

등록: `_자동화\스케줄등록_0830.bat` (관리자 권한). 인수는 작업 속성 → 동작 → **"인수 추가"** 칸에 넣는다.

---

## 손이 필요한 것

| 항목 | 왜 |
|---|---|
| **Haver 수집** | DLX Direct 가 이메일+보안코드 로그인이라 무인 실행 불가. 스케줄은 `/nohaver` 로 돈다. PCA·CPI 원본을 새로 받으려면 로그인한 상태에서 직접 실행 |
| **통합요약 DOCX** | `보따리\_자동화\daily_summary.py` 가 스케줄러에 없다. 이게 안 돌면 Report 탭이 전날에 머문다 |
| **경제지표·컨센서스 파일** | 블룸버그에서 내보내 폴더에 넣는 건 사람이 한다 |

---

## 문제가 생기면

| 증상 | 확인 |
|---|---|
| 사이트가 안 바뀐다 | `git log origin/main -1` 로 push 됐는지. Vercel 은 push 를 보고 배포한다 |
| 어떤 단계가 실패했나 | `logs\qae_YYYYMMDD.log` 의 `[실패]` 줄 |
| 실행 이력 | `logs\run_history.csv`, `run_steps.csv` |
| Haver 조회 실패 | `Haver.path()` 가 빈 문자열인 게 **정상**. `Haver.direct(1)` 이 호출되는 경로인지 확인 |
| 한글 깨짐 / cp949 오류 | 스크립트 직접 실행 시 `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` |
| 커밋에 엉뚱한 파일이 잔뜩 | `/addall` 이 붙었는지 확인. 기본은 산출물만이다 |

---

## 참고 문서

| 문서 | 내용 |
|---|---|
| `블벅경제지표\사용법.md` | 경제지표 파일 넣는 법 |
| `macro_hub\README.md` | Next.js 사이트 구조 |
| `macro_hub\DEPLOY.md` | Vercel 최초 연결 |
| `report_pipeline\README.md` | 리서치 수집 파이프라인 |
| `사용법.md` | 이전 버전 문서 (2026-08 기준, 일부 낡음) |
