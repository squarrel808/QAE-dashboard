# BQuant Rawfile 운영 폴더

이 폴더가 유럽·미국·TOPIX 및 테마 대시보드의 단일 원천이다.

## 폴더 구조

- `Daily_Input`: 처리한 일별 원본 보관함. `update_master.py` 가 자동으로 여기에 복사한다
- `BQuant_Master.xlsx`: 과거 자료와 Daily Input을 합친 전체 Master
- `update_master.py`: Daily Input을 Master에 병합하고 재검증하는 코드
- `update_all.ps1`: Master 갱신 후 공통 Python 코드로 유럽·미국·TOPIX 대시보드를 생성하고, AI·Top10/Down10도 갱신하는 실행 파일
- `rawfile_manifest.json`: 이미 처리한 파일의 SHA-256과 Master 요약

## 매일 사용법

새 파일은 **`QAE\____Rawdata___\`** 에 넣는다. 파일명이 `Bquant_` 로 시작하기만 하면
뒤에 뭐가 붙어도(`(5)`, 날짜 등) 실행할 때 자동으로 집어와 `Daily_Input` 에 복사한다.
같은 내용을 여러 번 넣어도 해시로 걸러서 중복 처리하지 않는다.
(자동 수거를 끄려면 `python update_master.py --no-rawdata`)

넣었으면 아래 명령을 실행한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile'
.\update_all.ps1
```

파일을 아무 폴더에 둔 채 경로로 바로 넘길 수도 있다. 파일명은 고정되어 있지 않다.

```powershell
.\update_all.ps1 'C:\Users\infomax\Downloads\Bquant_All_19_Raw_Refreshed12시.xlsb'
```

이 경우 입력 파일은 내용 해시로 중복 검사한 뒤 `Daily_Input`에 복사된다.

## 병합 규칙

- 키: `지수 + Bloomberg ticker + 지표 + 날짜`
- 같은 키의 새 유효 숫자는 기존 값을 교체한다.
- 새 파일의 빈칸은 기존 유효 값을 지우지 않는다.
- 가장 최근 날짜를 가진 자료의 구성종목·GICS 분류를 현재 기준으로 쓴다.
- Master 작성 후 지수, 날짜, 구성종목, 10개 지표의 숫자 셀 개수를 다시 읽어 원본 병합 결과와 대조한다.
- 파일을 폴더에 복사하는 것만으로는 갱신되지 않는다. `update_all.ps1`을 실행해야 한다.
- 원본 수거 경로: `____Rawdata___\Bquant_*` → `Daily_Input\` → `BQuant_Master.xlsx`

## 단기 수익률 기준

원자료는 주말·휴일·장 마감 전 최신일에 직전 종가를 이월할 수 있다. 유럽·미국·TOPIX 대시보드는 구성종목 중 최소 2%의 가격이 직전 유효 세션 대비 실제로 바뀐 날짜만 1D·5D 거래 세션으로 인정한다. EPS 변화도 동일한 두 날짜를 사용한다.
