# 배포 가이드 (Vercel) — 차근차근

## Equity 일별 이미지 및 표시명 (2026-10-27)

`build_pairbaskets_json.py`는 실제 일별 종가를 저장합니다. 기간 수익률은 달력 기준으로 계산하며 필요한 과거 이력이 없으면 순위에서 제외합니다. 두 추이 그래프는 SVG 이미지이며 기간·바스켓 선택 후 이미지로 저장할 수 있습니다.

이름 누락·티커형 이름 40개는 `scripts/pairbasket_labels.json`의 GS 자산 설명 검토 결과로 보완합니다. 원래 티커를 함께 표시하고 마우스를 올리면 설명과 검토 주의사항을 볼 수 있습니다. 공식 상품명과 설명 기반 표시명을 구분하며, 구성명이 확인되지 않은 2개는 미확인으로 표시합니다. 이 매핑은 매번 데이터 생성 시 적용됩니다.

## Surprise Index 배포 연결 (2026-10-26)

Consensus 다음에 `/surprise` 탭을 추가했습니다. 두 지수의 국가별 그래프와 히트맵은 `public/embeds/surprise.html` 하나에 데이터까지 포함됩니다. 전체 업데이트 web 단계는 Snowflake 조회→HTML 생성→동기화를 실행합니다. `npm run build`는 로컬 원본을 배포용 HTML로 동기화하거나 원본이 없으면 커밋된 public HTML을 검증합니다. Vercel에 CME 인증파일이나 API 키를 올릴 필요가 없습니다.

첫 배포에는 탭·route·build/sync 코드 변경도 함께 커밋해야 합니다. 기본 업데이트의 산출물 전용 커밋은 최초 기능 코드까지 포함하지 않습니다. 이후에는 기존 public 산출물 업데이트 흐름으로 반영됩니다. 이번 연결 작업 자체는 commit/push 또는 운영 배포를 실행하지 않습니다.

아침에 이 순서대로만 따라오시면 됩니다. 크게 **3단계**예요:
(A) 로컬에서 데이터 채우고 화면 확인 → (B) GitHub에 올리기 → (C) Vercel 연결.

---

## A. 로컬에서 먼저 확인

터미널(PowerShell)에서 macro_hub 폴더로 이동:

```powershell
cd "C:\Users\infomax\Documents\python\QAE\macro_hub"
```

### A-1. 데이터 채우기 (한 줄)

```powershell
npm run data
```

이 한 줄이 JSON 5종을 굽습니다:

- `build_pairbaskets_json.py` → Equity Factors(GS 인증 필요). GS 없이 모양만 보려면 대신 `npm run data:mock`.
- `build_policy_json.py` → Policy Tone(이미 있는 CSV 사용).
- `build_consensus_json.py` / `build_pca_json.py` / `build_caimap_json.py` → Consensus / PCA / CAI·MAP.

**임베드 HTML 은 여기 안 들어 있습니다.** 경제지표·실적 캘린더·CPI 분포 탭까지 갱신하려면 따로:

```powershell
python scripts/sync_embeds.py
```

> `sync_embeds.py` 실행 결과에 각 파일이 `OK`로 뜨는지 보세요. `WARN(끝에 </html> 없음)`이 뜨면
> 그 원본 대시보드를 먼저 다시 생성해야 합니다(예: `PCA/pca_gdp.py` 등 원본 빌드 스크립트 실행).

### A-2. 띄워서 확인

```powershell
npm run dev
```

→ 브라우저에서 `http://localhost:3000` 열기. 탭 9개(경제지표 / 실적 캘린더 / Report / PCA /
CAI·MAP / CPI 분포 / Consensus / Policy Tone / Equity)가 다 보이고 그래프가 그려지면 성공.
빨간 에러가 나면 그 메시지를 저한테 복붙해주세요.

---

## B. GitHub에 올리기

macro_hub는 이미 `QAE-dashboard` git 저장소 **안에** 있으니, 평소처럼 커밋·push하면 됩니다:

```powershell
cd "C:\Users\infomax\Documents\python\QAE"
git add macro_hub
git commit -m "Add Next.js macro hub"
git push
```

> 참고: `node_modules`, `.next`, `.env*` 는 `.gitignore`로 빠집니다(올라가면 안 되는 것들).
> `public/data/*.json` 과 `public/embeds/*.html` 은 올라가야 합니다(배포 사이트가 읽을 데이터).

---

## C. Vercel 연결 (최초 1회)

1. [vercel.com](https://vercel.com) 가입/로그인 (GitHub 계정으로 하면 편함).
2. **Add New → Project** → `quantddubi/ibreport_telegram`이 아니라 **이 QAE-dashboard 저장소** 선택 → Import.
   (이미 ibreport를 배포해보셨으니 흐름은 같아요.)
3. **중요 — Root Directory 설정**: Import 화면에서 `Edit` 눌러 Root Directory를 **`macro_hub`** 로 지정.
   (저장소 루트가 아니라 이 폴더가 앱이라는 뜻. Framework는 Next.js로 자동 인식됩니다.)
4. **Environment Variables**에 실시간 API용 키 추가:
   - Name: `FMP_API_KEY`  / Value: 본인 키
   - (없으면 실시간 데모만 안 뜨고 나머진 정상)
5. **Deploy** 클릭. 1~2분 후 `https://(프로젝트이름).vercel.app` 주소가 나옵니다.

이후로는 **git push만 하면 자동 재배포**됩니다.

---

## D. 데이터 갱신 루틴 (배포 후 평소 작업)

**평소에는 저장소 루트의 `전체업데이트.bat` 하나로 끝냅니다.** 수집 → HTML 생성 → JSON →
embeds → commit → push 까지 다 돌고, git 에는 산출물만 담깁니다(작업 중인 코드는 안 딸려감).

```powershell
cd "C:\Users\infomax\Documents\python\QAE"
.\전체업데이트.bat /nohaver          # Haver 로그인 없이 나머지 전부 + 배포
```

macro_hub 쪽만 손으로 다시 굽고 싶을 때:

```powershell
cd "C:\Users\infomax\Documents\python\QAE\macro_hub"
npm run data                      # JSON 5종 재생성
python scripts/sync_embeds.py     # 임베드 HTML 동기화
cd ..
git add macro_hub/public
git commit -m "data refresh"
git push                          # Vercel이 알아서 재배포
```

비유: **반찬가게 새벽 준비**예요. 새벽에 반찬(JSON·HTML)을 새로 만들어 진열(push)하면,
손님(방문자)은 그날 낮에 신선한 걸 바로 가져갑니다.

실시간 모듈(`/api/quote`)만은 손님이 올 때마다 즉석에서 만들어요(키는 Vercel 환경변수에 숨김).

---

## 막히면

- `npm run dev`에서 빨간 에러 → 메시지 전체 복붙.
- 특정 탭만 "동기화되지 않았어요" 박스가 뜸 → `python scripts/sync_embeds.py` 다시 실행 후 새로고침.
- Vercel 빌드 실패 → Vercel의 빌드 로그 마지막 부분 복붙.

## 실적 달력 갱신 — 2026-10-19 변경

`____Rawdata___/실적발표*.txt` 중 수정시각이 최신인 파일로 `/earnings`를 생성합니다. TXT의 기업명·티커·USD 시가총액·예상 발표일을 사용하며, 원본 날짜를 변환하지 않습니다. 시간·시간대·회계분기는 원본에 없어 표시하지 않습니다. 공식 IR 일정 자동 수집 기능은 없습니다.

QAE 루트에서 아래 순서로 실행합니다.

```powershell
python -X utf8 releasecalendar/build_earnings_calendar.py
python -X utf8 macro_hub/scripts/sync_embeds.py
```

생성이 성공한 뒤에만 동기화·배포합니다. `sync_embeds.py`는 복사만 하므로 단독 실행으로 새 TXT가 반영되지 않습니다. 전체 갱신의 AfterHTML 단계에서도 TXT를 읽습니다. `/webonly`와 `/nightly`는 달력 재생성을 생략하므로 먼저 위 생성기를 실행해야 합니다. 로컬 표 전용 `update_daily_tables.py`도 실적 달력을 갱신하지 않습니다.

화면의 원본 파일명·수정시각·예상 일정 범위를 확인하고 변경된 게시 파일만 커밋·push합니다. 코드 변경이 있으면 관련 코드·안내 문서도 함께 커밋합니다. 배포 후 `/earnings`와 `/embeds/earnings.html`의 내용까지 확인합니다. TXT가 없거나 해석에 실패하면 옛 엑셀로 폴백하지 않습니다. 기존 `기업실적.xlsx`·`marketcap.json`은 보관 자료이며 실행에서 사용하지 않습니다.

입력 형식과 검증 방법: [실적 달력 안내](../releasecalendar/README.md).
