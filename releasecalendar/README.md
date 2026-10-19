# 실적 발표 달력

`build_earnings_calendar.py`는 QAE의 `____Rawdata___/실적발표*.txt` 중 수정시각이 가장 최근인 파일만 읽습니다. 폴더는 `QAE_RAWDATA_DIR`로 지정할 수 있습니다. 기존 `기업실적.xlsx`와 `marketcap.json`은 더 이상 읽지 않습니다. TXT가 없거나 행을 해석할 수 없으면 실패하며 기존 화면을 보존합니다.

입력 열은 `Company`, `Ticker`, `Market Cap (USD)`, `Expected Report Date`입니다. 현재 제공된 열·행 구분 없는 복사 형식과 공백/줄바꿈을 지원합니다. 날짜는 YYYY-MM-DD, 시총은 쉼표가 포함된 정수입니다. 대문자만 있는 기업명과 티커가 붙은 형식은 동일 문자열 반복(IBMIBM) 및 PLC 접미사를 처리합니다. 다른 모호한 원본 형식은 열 구분을 보존하여 파서를 확장해야 합니다.

예상 발표일을 원본 그대로 사용합니다. 공식 확정일로 간주하거나 시간대를 변환하지 않습니다. 시간·시간대·회계분기는 원본에 없으므로 이전 데이터에서 가져오지 않습니다. 날짜별 기업은 원본 시가총액 내림차순으로 정렬합니다. 화면에 원본 파일명·수정일·생성일을 분리해서 표시합니다.

기존 `AfterHTML.py` → `build_earnings_calendar.py` → `macro_hub/scripts/sync_embeds.py` 경로를 사용합니다. 웹 경로는 `/earnings`입니다. 배포는 기존 Git push 절차입니다.

검증: `python -X utf8 test_earnings.py`

입력 확인은 QAE 루트의 `python -X utf8 rawdata.py`로 합니다. `/webonly`·`/nightly`·로컬 일간 표 전용 실행은 새 실적 TXT를 재생성하지 않습니다. 먼저 생성기를 실행한 뒤 웹 표시본을 동기화하세요. AfterHTML 실행기는 생성 실패를 종료 코드 1로 반환합니다.
