# 매일 09:00 자동 보고서

Codex 예약 작업 두 개가 매일 오전 9시(로컬 시간)에 병렬로 실행된다.

- `AI 밸류체인 일간 보고서` → `AI_Rotation`
- `미국·중국·유로존 Top10 일간 보고서` → `Top10_Down10`

공통 원자료는 `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx`다. 새 Bloomberg 파일은 예약 실행 전에 `Rawfile\Daily_Input`에 넣고 `Rawfile\update_all.ps1`로 Master에 반영해야 한다. 예약 보고서 작업 자체는 Master를 읽기만 하며 다른 작업과 충돌하지 않도록 Master를 갱신하지 않는다.

두 작업은 `gpt-5.6-sol`, reasoning `medium`으로 설정했다. 10분 내외 실행을 목표로 계산은 로컬 Python에서 수행하고, 웹 촉매 조사는 핵심 상·하위 종목으로 제한한다. 같은 기준일의 검증된 산출물이 이미 있고 Master가 바뀌지 않았다면 중복 생성을 건너뛴다.

## 요청형 STOXX 600·TOPIX 섹터 로테이션

섹터 로테이션은 사용자의 요청에 따라 실행한다. 원자료를 `Rawfile\Daily_Input`에 추가한 뒤 Codex에 `daily` 또는 `weekly`라고 요청하면 된다.

- `daily`, `일간`, `어제`, `1D` → 최신 실제 거래일과 직전 실제 거래일을 비교하는 1D
- `weekly`, `주간`, `주보`, `5D` → 최신 실제 거래일과 5거래일 전을 비교하는 5D
- 기본 시장 → STOXX Europe 600과 TOPIX 모두
- 결과 → `output\Sector_Industry\Daily_YYYYMMDD` 또는 `Weekly_YYYYMMDD`

표 이미지는 `섹터, N, 산업 그룹, 1D/5D 평균, 중앙값, 상승 비율, 분산, 시장 대비` 열을 사용한다. 계산 JSON에는 GICS Industry Group과 섹터별 상승·하락 상위 종목을 각각 최대 8개까지 저장한다.

실행 진입점은 `Theme\run_sector_rotation.ps1`이고 자세한 규칙은 `Theme\README.md`에 있다. 원자료의 최신 열이 주말·휴일·장 마감 전 이월값이면 실제 거래일에서 제외한다.

## 가격 계산 원칙

- 종목 가격수익률은 `종료가격 / 시작가격 - 1`로 계산한다.
- AI 밸류체인과 국가·시장 참고가격처럼 여러 종목을 합친 **집계가격**은 시가총액 가중 평균가격을 사용하지 않는다.
- 집계가격은 `Σ(Price × Shares) / ΣShares`로 계산하고, 집계수익률은 이 집계가격의 기간 변화율로 계산한다.
- 현재 Master에는 Shares가 별도 필드로 없으므로 `Shares = Market Cap / Price`로 역산한다.
- 시가총액은 P/E·EPS 등 비가격 펀더멘털 집계, 구성비 및 기업행위 QA에만 사용한다.
- Top10/Down10 종목 순위는 개별 종목 가격수익률 순위이므로 가중치의 영향을 받지 않는다.
