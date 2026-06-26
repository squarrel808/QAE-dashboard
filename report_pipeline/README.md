# report_pipeline — 리서치 PDF → 요약 → 사이트

셀레니움이 받아온 PDF를 Claude로 요약해 `macro_hub`의 Reports 탭(`reports.json`)에 올리는 파이프라인.

## 흐름

```
download_reports.py  →  보따리\YYMMDD\*.pdf      (수집, 기존 셀레니움)
summarize.py         →  새 PDF만 요약 + 저장소 업로드 → reports.json   (신규)
git push             →  Vercel 자동 재배포
Reports 탭           →  reports.json 읽어 표·검색·다운로드            (이미 있음)
```

## 파일

| 파일 | 역할 |
|---|---|
| `download_reports.py` | 네 셀레니움 다운로더 (이 폴더에 같이 두기) |
| `summarize.py` | 폴더 스캔 → 파일명에서 기관/섹션 추출 → PDF 텍스트 → Claude 요약 → 저장소 업로드 → reports.json append |
| `state.json` | 이미 요약한 파일 기록(중복 방지, 자동 생성) |
| `.env` | API 키·설정 (`.env.example` 복사해서 작성) |
| `run_daily.bat` | 수집→요약→게시 1회 실행 |

## 기관·섹션 매핑 (파일명 기반, manifest 불필요)

| 파일명 prefix | 기관(source) | 섹션(section) |
|---|---|---|
| Equity_Research / Economics_Research / Beyond_Research / Overall_Most_Popular_Research / Portfolio_Strategy_Research | **GS** | Equity / Economics / Beyond / Overall / Portfolio Strategy |
| BofA | **BofA** | Trending |
| JPMM_Research | **JPM** | Research |
| HSBC_MostRead / HSBC_HouseViews | **HSBC** | Most Read / House Views |

제목은 파일명이 잘려있어서, **Claude가 PDF 본문을 보고 정식 제목**을 다시 뽑습니다.

## 설치 & 첫 실행 (로컬 테스트 모드)

```bash
cd report_pipeline
pip install -r requirements.txt
copy .env.example .env       # 그리고 .env 열어서 ANTHROPIC_API_KEY 채우기 (STORAGE=local 유지)
python summarize.py          # 보따리\오늘폴더 의 PDF를 요약 → reports.json + PDF를 public/report_files 로 복사
```

→ `macro_hub`에서 `npm run dev` 후 `/reports` 탭에서 확인. 제목 클릭 시 PDF 다운로드.

## PDF 저장소를 R2로 전환 (양 많아지면)

1. Cloudflare 가입 → R2 버킷 생성(예: `research-reports`) → **Public access** 켜서 공개 도메인(`https://pub-xxx.r2.dev`) 확보
2. R2 API 토큰 발급 → `.env` 의 `R2_*` 채우고 `STORAGE=r2` 로 변경
3. 끝. summarize.py가 PDF를 R2에 올리고 그 URL을 reports.json에 적습니다. (깃엔 PDF 안 올라감)

> 왜 R2? S3 호환이라 파이썬 `boto3`(가장 안정적인 SDK)로 바로 되고, 10GB 무료 + **다운로드 비용 0**이라 하루 40개씩 쌓여도 부담 없음.

## 매일 자동 (선택)

`run_daily.bat` 을 Windows **작업 스케줄러**에 "매일 오전 8시"로 등록 → 무인 운영.

## 주의
- `.env`, `state.json`, 받은 PDF(로컬모드의 `public/report_files`)는 용량/보안상 git 관리 정책을 따로 둘 것.
  (R2 모드면 PDF는 git에 안 들어가고 `reports.json`만 올라감 — 권장)
