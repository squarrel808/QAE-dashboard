# CFNAI형 일반 PCA · 2026-10-29

PCA I·II·III가 `fixed_pca.py`를 공유한다. 개별 계수에 부호 제약을 두지 않는다.
입력 전처리는 각 모델의 기존 설정 그대로이며, 전체 표본 평균·표준편차로
표준화한다. 지표 쌍별 공통 관측의 상관행렬을 구한 뒤 필요하면 고유값을
보정하여 양의 준정부호 행렬을 만든다. 최대 고유값의 고유벡터를 한 번 구해
현재 자료의 전체 과거에 고정 적용한다. 전체 벡터 방향만 경제적 방향 평균과
양의 상관이 되도록 선택한다. 개별 변수의 경제적 부호는 보장하지 않는다.

관측치 가중합 / sqrt(관측 지표 수)라는 기존 결측 조정을 유지한다. 원자료를
보간하거나 미래 값으로 채우지 않는다. 이 처리는 결측 수에 따라 유효 계수의
크기에 영향을 주므로 공식 CFNAI의 결측 예측 절차와 같지 않다. 입력·부문별
합산 방식도 달라 공식 CFNAI를 재현한 지수로 해석하면 안 된다.

완성된 부문 점수는 전체 표본에서 평균 0, 표준편차 1로 재표준화한다.
PCA I는 기존 카테고리 동일가중, II·III는 기존 연초 GDP 비중 합산을 유지한다.
세 모델의 Momentum은 완성된 Level의 최근 3개월 평균 - 직전 3개월 평균이다.
추가 PCA·표준화·반감기는 적용하지 않는다. 새 데이터로 갱신할 때 로딩을
재추정하며 과거 전체 점수도 개정된다. 실시간 빈티지 백테스트가 아니다.

공식 자료: https://www.chicagofed.org/-/media/publications/cfnai/background/cfnai-background-pdf.pdf

반복 갱신: 기존 QAE 자동화의 PCA I 계산 및 `PCA_Four_Axis/run_update.py`가
II·III를 순차 계산·검증·게시 스냅샷에 복사한다. Vercel은 게시 스냅샷을 사용한다.

검증: `python -X utf8 PCA_Common/test_fixed_pca.py`, 각 모델 `test_model.py`.
`build_comparison.py`는 2026-10-29 원자료를 고정한 방법론 변경 보고서를 만든다.
비교용 이전 결과는 `outputs/pca_cfna_comparison/before`에 보존한다.
