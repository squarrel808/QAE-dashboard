# Citi Surprise Index

Vercel 통합 대시보드에서는 **Consensus 다음 Surprise Index 탭**(`/surprise`)으로 표시합니다. 이 실행기가 성공하면 `macro_hub/public/embeds/surprise.html`도 자동 동기화하며 Node.js가 필요합니다. QAE 전체 업데이트의 web 단계에서도 이 실행기를 호출합니다. Vercel 빌드는 로컬 인증정보를 사용하지 않고 생성된 HTML을 배포합니다. 최초 route·메뉴 코드도 커밋해야 하며, 이후 public HTML은 기존 배포 대상에 포함됩니다.

`update_surprise.cmd`를 더블클릭하면 기존 CME와 동일한 Snowflake 프로필·개인키로 **TAA_DB_DEV.CORE.SERIES_MASTER / FACT_TIME_SERIES**를 읽기 조회하고, 검증 후 국가별 그래프와 히트맵을 갱신합니다. PostgreSQL 연결은 제거했으며 이전 PostgreSQL 스냅샷도 재게시할 수 없습니다. `표_업데이트/index.html`의 Economic / Inflation 메뉴에서 엽니다.

- 경기: 일별 원자료 + 최근 5개 유효 평일 관측치의 단순평균(5DMA).
- 물가: 월별 원자료. 일별 변환이나 5개월 평균을 적용하지 않습니다.
- 그래프: 국가별 개별 카드, 지역·그룹 구분, 1년/3년/5년/전체, 공통/개별 Y축, 마우스 날짜·값 확인.
- 히트맵: 경기는 최근 60개 관측일 중 5관측일 간격 및 마지막 관측일, 물가는 최근 24개월. 0 중심 대칭 색상이며 지수별 색상 범위가 다릅니다.
- Snowflake 조회일과 관측일을 별도로 표시합니다. 경기: 활성 Citi 일별 18개 시계열(Haver 17개·BRIC Bloomberg), 물가: Haver 월별 16개 시계열. 비활성 마스터·빈 시계열·다른 회사의 Surprise 지수는 제외합니다.

## 실행

```powershell
python -X utf8 .\update_surprise.py
python -X utf8 .\update_surprise.py --open
# API 호출 없이 마지막 성공 스냅샷으로 화면만 재생성
python -X utf8 .\update_surprise.py --from-cache
```

`config.json`에서 조회 시작일·Snowflake 가상환경 Python·프로필·role·warehouse·개인키 경로를 관리합니다. 커넥터는 기존 SNOWFLAKE 저장소의 가상환경에서 실행하며 일반 실행기에는 pandas가 필요합니다. 인증정보 내용은 복사하거나 결과물에 저장하지 않습니다. 개인키와 connections.toml은 로컬에만 보관합니다.

데이터 조회·검증이 성공해야 `index.html`을 교체합니다. 동일 SELECT의 윈도우 COUNT와 실제 수신 행 수를 대조하고, CORE 중복·빈도·결측·미래 날짜·국가 범위를 검증합니다. 모든 국가의 마지막 관측일이 경기 10일·물가 75일 이내인지 검사합니다(달력일 기준, config에서 관리). 일부 국가만 실패해도 기존 게시본을 보존하며 `last_attempt.json`과 종료 코드로 실패를 알립니다. 주말 행은 5DMA에서 제외하며 원자료에 보존합니다. `latest.json`은 마지막 성공 기록입니다. `--from-cache`는 Snowflake 스냅샷만 허용하고 원래 조회시각을 유지합니다. 웹 동기화 실패 시 로컬 새 화면은 남지만 갱신 상태는 실패로 기록됩니다.

이 폴더의 `runs`는 Snowflake 스냅샷·계산 데이터·HTML·manifest·교체 전 화면을 보존합니다. 외부 DB를 수정하거나 업로드하지 않습니다. 자동 시간 예약은 없습니다. 로컬 데일리 표 갱신기는 메뉴를 유지하며, QAE `전체업데이트.bat`의 web 단계는 Snowflake 갱신을 호출합니다.
