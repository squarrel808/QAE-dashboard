# 미국 AI 밸류체인 기간별 보고서

보고서를 세 종류로 분리해 필요할 때 각각 실행한다.

| 실행 파일 | 보고서 | 핵심 용도 | 결과 폴더 |
|---|---|---|---|
| `run_1d.ps1` | 최근 1거래일 | 당일 로테이션·종목 이벤트 확인 | `output\1D` |
| `run_1w.ps1` | 최근 1주 | 주간 리더십·단기 확산 확인 | `output\1W` |
| `run_1m_3m.ps1` | 최근 1개월·3개월 | 중기 로테이션·월별 경로 확인 | `output\1M_3M` |
| `run_all.ps1` | 세 보고서 전체 | 한 번에 모두 갱신 | 위 세 폴더 |

모든 보고서에는 다음 내용이 공통으로 들어간다.

- 12개 전체 밸류체인의 1D·1W·1M·3M 성과표
- 전체 밸류체인별 역할·성과·breadth·상하위 기여 종목·해석
- 분석 대상 전 종목의 기간별 수익률과 AI 밸류체인 내 역할 설명
- 계산 정의와 데이터 주의사항은 문서 마지막에 배치

밸류체인 집계가격은 `Σ(Price × Shares) / ΣShares`로 계산한다. 현재 Master에는 Shares가 별도 필드로 없으므로 `Shares = Market Cap / Price`로 역산한다. 시가총액 가중 평균가격은 사용하지 않는다.

## 일반 실행

Master가 이미 최신이면 다음 중 하나만 실행한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\AI\Reports'
.\run_1d.ps1
.\run_1w.ps1
.\run_1m_3m.ps1
```

세 개를 한 번에 만들려면 다음을 실행한다.

```powershell
.\run_all.ps1
```

## 새 Bloomberg 파일까지 병합하고 실행

새 `.xlsb` 파일을 `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\Daily_Input`에 넣은 다음 `-UpdateRaw`를 붙인다.

```powershell
.\run_all.ps1 -UpdateRaw
```

데이터 JSON을 이미 계산했고 Word 문서만 다시 만들 때는 다음처럼 실행한다.

```powershell
.\run_1m_3m.ps1 -UseExistingData
```

생성 후 바로 Word로 열려면 `-Open`을 추가한다.

DOCX와 PDF를 함께 만들려면 `-Pdf`를 추가한다.

```powershell
.\run_1m_3m.ps1 -Pdf
```

## 기간 정의

- 1D: 기준일 대비 직전 유효 거래일
- 1W: 기준일 7일 전 이하의 가장 가까운 유효 거래일
- 1M: 전월 동일일 이하의 가장 가까운 유효 거래일
- 3M: 3개월 전 동일일 이하의 가장 가까운 유효 거래일

기준일과 파일명은 하드코딩하지 않는다. `BQuant_Master.xlsx`의 마지막 유효 가격 거래일을 자동으로 사용한다.
