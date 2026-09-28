# AI 밸류체인 운영

## 현재 운영 경로

원본 4개를 넣은 뒤 아래 공통 갱신기를 실행한다.

```powershell
python -X utf8 "C:\Users\infomax\Documents\python\QAE\데일리시황\update_daily_tables.py" --check
python -X utf8 "C:\Users\infomax\Documents\python\QAE\데일리시황\update_daily_tables.py" --period 5D
```

성공한 실행은 `표_업데이트\latest.json`의 `requested_at`과 같은 run 폴더에 저장된다.

- 정량 데이터: `표_업데이트\runs\<run>\AI\ai_data.json`
- 정량 표: `표_업데이트\runs\<run>\AI\ai_5D.html`
- 날짜별 최종본: `BQL\Theme\output\YYYYMMDD\AI\SP500_AI_밸류체인_5D_코멘터리_YYYYMMDD.html`

`Theme\Material\AI\latest_data.json`, `run_ai_report*`, `run_final*`은 과거 수동 경로이므로 최신 run 선택에 사용하지 않는다.

## 계산과 서술의 분리

`build_ai_value_chain_html.py`가 `ai_data.json`을 바탕으로 밸류체인 표, 기간별 수익률, 상승 종목 비율, 순위와 종목 행을 전부 만든다. AI 집계는 종목별 Shares를 반영한 `Σ(Price×Shares)/ΣShares` 방식이다.

코멘터리 단계는 위 표를 다시 만들지 않는다. 별도 commentary JSON의 문장만 정량 HTML의 슬롯에 붙인다.

```powershell
python -X utf8 "C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\attach_commentary.py" `
  --base-html "<run>\AI\ai_5D.html" `
  --commentary-json "<AI 코멘트 JSON>" `
  --output "<날짜별 최종 HTML>"
```

commentary JSON에는 다음만 둔다.

- `global`: 보고서 전체 해석
- `stages`: 12개 밸류체인별 해석
- `stocks`: 티커별 짧은 해석
- 각 문장의 날짜, 출처, URL, 확신도

수익률, 순위, breadth, BM, 표 행, 종목 배열은 commentary JSON에 복제하지 않는다. 정량 값이 잘못되었다면 코멘트로 보정하지 말고 계산기를 먼저 수정해 base를 재생성한다.

## 주요 파일

- `build_sp500_ai_value_chain.py`: 분류와 정량 계산
- `build_ai_value_chain_html.py`: 정량 HTML 렌더러와 코멘트 슬롯
- `..\attach_commentary.py`: 정량 HTML에 서술만 결합
- 분류 자료와 종목 설명 자료: 편입 근거와 사업 설명

## 검증

- `latest.json`과 선택한 run의 manifest가 같은 실행인지 확인한다.
- `ai_data.json`의 `meta.asOf`와 base HTML의 기준일이 일치해야 한다.
- 12개 stage, Core/Expanded 분리, 기간 시작일과 종목 수를 확인한다.
- 코멘트 결합 전후 표의 행 수와 표 숫자는 같아야 한다.
- 결합 대상 `report / asOf / primary`가 다르면 중단한다.
