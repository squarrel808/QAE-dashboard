# Macro Dashboard — Streamlit 버전 (뼈대)

기존 HTML 대시보드 5개를 **5개 대분류 + 하위 탭** 구조로 묶은 Streamlit 앱입니다.

## 실행

```bash
cd streamlit_dashboard
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 이 자동으로 열립니다.

## 구조

| 대분류 | 하위 탭 | 데이터 출처 |
|---|---|---|
| ① 경제지표 | (단일) | `assets/econ_dashboard.html` |
| ② 증권사 자료 (Report) | 보고서목록 / 키워드트렌드 / Daily Brief / 북마크 / 네트워크 | ibreport (Vercel 라이브 iframe) |
| ③ PCA | (단일) | `assets/pca_dashboard.html` |
| ④ Consensus | GDP / CPI / CPI Distribution | `assets/consensus_*.html` |
| ⑤ Policy Tone | (단일) | `assets/policy_hawkdove.html` |

## 참고

- `assets/` 안의 HTML은 기존 대시보드를 복사해 둔 것입니다. 데이터를 갱신하려면
  원본 파이프라인을 다시 돌려 HTML을 새로 만든 뒤 이 폴더에 덮어쓰면 됩니다.
- ② 증권사 자료는 React(Next.js) 앱이라 코드로 옮기지 않고 Vercel 라이브 화면을
  iframe 으로 끼워 넣었습니다. 만약 화면이 빈칸으로 보이면 사이트가 iframe 임베드를
  막은 것이니, 각 탭 상단의 "새 탭에서 열기" 링크를 쓰면 됩니다.
- 다음 단계로 GS API 팩터 비교(momentum/value) 같은 **순수 Streamlit 페이지**를
  여기에 새 대분류로 추가하면 됩니다.
