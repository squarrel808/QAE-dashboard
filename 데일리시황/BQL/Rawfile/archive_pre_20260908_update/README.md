# BQuant Rawfile 운영 폴더

이 폴더가 모든 운영 대시보드의 단일 원천이다.

## 폴더 구조

- `Daily_Input`: Bloomberg/BQuant에서 새로 받은 일별 `.xlsb` 또는 `.xlsx` 파일을 넣는 곳
- `BQuant_Master.xlsx`: 과거 자료와 Daily Input을 합친 전체 Master
- `update_master.py`: Daily Input을 Master에 병합하고 재검증하는 코드
- `update_all.ps1`: Master 갱신 후 유로존·AI·Top10/Down10 산출물을 한 번에 재생성하는 실행 파일
- `rawfile_manifest.json`: 이미 처리한 파일의 SHA-256과 Master 요약

## 매일 사용법

새 파일을 `Daily_Input`에 넣고 아래 파일을 PowerShell에서 실행한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\BQL\Rawfile'
.\update_all.ps1
```

파일을 다른 폴더에 둔 채 바로 넘길 수도 있다. 파일명은 고정되어 있지 않다.

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

파일을 폴더에 복사하는 행위만으로 백그라운드 자동 실행되지는 않는다. `update_all.ps1`을 한 번 실행해야 한다.

