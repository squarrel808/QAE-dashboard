> **2026-09-11 데일리 작업 기준 변경**
> 원본 4개를 넣은 후 `QAE\데일리시황\데일리_표_업데이트.cmd`를 실행합니다.
> AI 밸류체인·섹터는 표와 숫자만 갱신하고, WECO는 실제값과 검토된 기존 IB 근거를 연결합니다.
> 새 AI 해석은 별도 요청 시 작성합니다. 아래 보고서 실행 예시는 과거 수동 경로입니다.
> 결과: `QAE\데일리시황\표_업데이트\index.html` · 상세 규칙: `데일리시황\데일리_작업규칙.md`

# `____Rawdata___` — 받은 엑셀은 전부 여기에

블룸버그·BQuant에서 내려받은 원본 엑셀을 **파이프라인 폴더에 나눠 넣지 말고 여기 한 곳에** 떨궈 넣는다.
각 스크립트가 실행할 때 여기서 자기 파일을 집어간다.

---

## 넣는 법

파일을 이 폴더에 복사한다. 이름은 안 바꿔도 된다. 끝.

**앞부분(prefix)만 맞으면 뒤에 뭐가 붙어도 상관없다.**

| 넣는 파일 (앞부분) | 확장자 | 집어가는 곳 | 만들어지는 것 |
|---|---|---|---|
| `ECFC_Growth_Consensus` (구 `ECFC_Growth Consesus`도 지원) | `.xlsb` | `Consensus Builder\merge_xlsb_to_xlsx.py` | GDP 컨센서스 (`/consensus`) |
| `ECFC_Inflation_Consensus` (구 `ECFC_Inflation Consesus`도 지원) | `.xlsb` | `Consensus Builder\merge_xlsb_to_xlsx.py` | CPI 컨센서스 (`/consensus`) |
| `Bquant_` | `.xlsb` `.xlsx` | `데일리시황\BQL\Rawfile\update_master.py` | BQuant_Master → 유럽·TOPIX·AI·Top10 대시보드 |
| (모든 `.xlsx`) | `.xlsx` | `블벅경제지표\load_weco.py` | 경제지표 캘린더 (`/econ`) |

```
ECFC_Growth_Consensus_26_27_시트추가.xlsb
ECFC_Growth_Consensus_26_27_시트추가 (2).xlsb  ← 브라우저가 붙인 (2). 그대로 둬도 된다
ECFC_Growth_Consensus_20260928.xlsb
^^^^^^^^^^^^^^^^^^^^ 여기까지만 맞으면 전부 같은 파일로 본다
```

컨센서스 시트는 `미국26`·`미국27` 형식으로 2026·2027을 함께 넣을 수 있다.

같은 prefix 가 여러 개면 **수정시각이 가장 최근인 것 하나**를 쓴다.
경제지표(WECO)만 예외로, 최근 2주치 여러 개를 합쳐 쓴다 (같은 일정은 최신 파일 값).

> 경제지표 xlsx 는 prefix 를 안 본다. 파일 **내용**(헤더·컨센서스 채움률)으로 WECO/BQuant
> 캘린더인지, 지표인지 연설인지를 알아서 판별한다. 그래서 아무 이름이나 괜찮다.

---

## 갱신하기

넣기만 하면 갱신되지 않는다. 해당 스크립트를 돌려야 한다.

```powershell
# 컨센서스 (CPI/GDP)
cd 'C:\Users\infomax\Documents\python\QAE\Consensus Builder'
python merge_xlsb_to_xlsx.py; python 'CPI consensus.py'; python 'GDP consensus.py'

# 경제지표 캘린더
cd 'C:\Users\infomax\Documents\python\QAE\경제지표가져오기'
python weco_dashboard.py

# BQuant (유럽·TOPIX·AI·Top10)
cd 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile'
.\update_all.ps1
```

전체 갱신(`전체업데이트.bat`)에도 컨센서스·경제지표 단계가 들어 있다.

---

## 확인

```powershell
cd C:\Users\infomax\Documents\python\QAE
python rawdata.py
```

폴더에 뭐가 있고 어느 prefix 가 어느 파일에 물렸는지 표로 찍어 준다.

---

## 규칙 몇 가지

- **예전 폴더에 그냥 둬도 계속 돈다.** `Consensus Builder\`, `블벅경제지표\` 도 같이 훑고,
  두 곳에 다 있으면 **수정시각이 최신인 쪽**을 쓴다. 옮기는 중에 깨지지 않게 남겨둔 폴백이다.
- **다 쓴 파일을 지워도 된다.** 컨센서스는 `history\` 에, BQuant 는 `BQuant_Master.xlsx` 에
  누적되므로 원본이 사라져도 과거 자료는 남는다. 단, 지운 다음엔 그 파이프라인을 다시
  돌리기 전까지 새 원본을 넣어야 한다.
- **엑셀에서 연 채로 두지 마라.** `~$` 임시파일은 무시하지만, 잠긴 파일은 읽기가 실패한다.
- 이 폴더는 git 에 올리지 않는다 (원본이 크고, 산출물만 커밋하는 게 기본이다).

---

## 코드는 어디에

`QAE\rawdata.py` 하나가 찾는 일을 다 한다. 폴더 위치를 옮기려면 환경변수
`QAE_RAWDATA_DIR` 로 덮어쓴다.
