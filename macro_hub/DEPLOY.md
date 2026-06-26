# 배포 가이드 (Vercel) — 차근차근

아침에 이 순서대로만 따라오시면 됩니다. 크게 **3단계**예요:
(A) 로컬에서 데이터 채우고 화면 확인 → (B) GitHub에 올리기 → (C) Vercel 연결.

---

## A. 로컬에서 먼저 확인

터미널(PowerShell)에서 macro_hub 폴더로 이동:

```powershell
cd "C:\Users\USER\OneDrive\문서\QAE-dashboard\macro_hub"
```

### A-1. 데이터 채우기 (한 줄)

```powershell
npm run data
```

이 한 줄이 세 가지를 합니다:

- `build_pairbaskets_json.py` → Equity Factors 데이터(GS 인증 필요). GS 없이 모양만 보려면 대신 `npm run data:mock`.
- `build_policy_json.py` → Policy Tone 데이터(이미 있는 CSV 사용).
- `sync_embeds.py` → PCA / Consensus / CAI·MAP 원본 대시보드 HTML을 `public/embeds/`로 복사.

> `sync_embeds.py` 실행 결과에 각 파일이 `OK`로 뜨는지 보세요. `WARN(끝에 </html> 없음)`이 뜨면
> 그 원본 대시보드를 먼저 다시 생성해야 합니다(예: `PCA/pca_gdp.py` 등 원본 빌드 스크립트 실행).

### A-2. 띄워서 확인

```powershell
npm run dev
```

→ 브라우저에서 `http://localhost:3000` 열기. 5개 탭(Equity / Policy / Consensus / PCA / CAI·MAP)이
다 보이고 그래프가 그려지면 성공. 빨간 에러가 나면 그 메시지를 저한테 복붙해주세요.

---

## B. GitHub에 올리기

macro_hub는 이미 `QAE-dashboard` git 저장소 **안에** 있으니, 평소처럼 커밋·push하면 됩니다:

```powershell
cd "C:\Users\USER\OneDrive\문서\QAE-dashboard"
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

데이터를 새로 받고 싶을 때:

```powershell
cd "C:\Users\USER\OneDrive\문서\QAE-dashboard\macro_hub"
npm run data                 # JSON 재생성 + embeds 동기화
cd ..
git add macro_hub/public
git commit -m "data refresh"
git push                     # Vercel이 알아서 재배포
```

비유: **반찬가게 새벽 준비**예요. 새벽에 반찬(JSON·HTML)을 새로 만들어 진열(push)하면,
손님(방문자)은 그날 낮에 신선한 걸 바로 가져갑니다.

실시간 모듈(`/api/quote`)만은 손님이 올 때마다 즉석에서 만들어요(키는 Vercel 환경변수에 숨김).

---

## 막히면

- `npm run dev`에서 빨간 에러 → 메시지 전체 복붙.
- 특정 탭만 "동기화되지 않았어요" 박스가 뜸 → `python scripts/sync_embeds.py` 다시 실행 후 새로고침.
- Vercel 빌드 실패 → Vercel의 빌드 로그 마지막 부분 복붙.
