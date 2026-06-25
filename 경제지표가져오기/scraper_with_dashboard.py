from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException
import sys
import time
import re
import pandas as pd
import os, json, datetime   # ← 대시보드 생성에 사용 (추가됨)

# 출력 파일은 항상 이 스크립트가 있는 폴더(경제지표가져오기)에 저장한다.
# (어느 위치에서 실행해도 엉뚱한 폴더에 떨어지지 않도록 절대경로로 고정)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Windows 콘솔(cp949)에서 ✓ 같은 유니코드 출력 시 UnicodeEncodeError 방지
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# ───────────────────────────────────────── 
# 타깃 국가 코드 (G7 + 호주 + 중국 + 한국)
# G7: 미국(usa), 영국(gbr), 프랑스(fra), 독일(deu),
#     이탈리아(ita), 일본(jpn), 캐나다(can) + G7그룹(g7)
# + 호주(aus), 중국(chn), 한국(kor)
# ─────────────────────────────────────────
TARGET_COUNTRIES = {
    'usa': '미국',
    'gbr': '영국',
    'fra': '프랑스',
    'deu': '독일',
    'ita': '이탈리아',
    'jpn': '일본',
    'can': '캐나다',
    'aus': '호주',
    'chn': '중국',
    'kor': '한국',
}


def setup_driver(headless=False):
    options = Options()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1400,900')
    options.add_argument('--lang=ko-KR')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        'Network.setUserAgentOverride',
        {"userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36"}
    )
    return driver


def set_importance_3stars(driver, wait):
    """충격 드롭박스 → 별 3개(★★★)만 선택"""
    # 충격 버튼 클릭 (드롭다운 열기)
    importance_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@class,'btn-calendar') and contains(.,'충격')]")
        )
    )
    importance_btn.click()
    time.sleep(0.8)

    # 드롭다운이 열렸는지 확인
    wait.until(
        EC.presence_of_all_elements_located(
            (By.XPATH, "//a[@onclick and contains(@onclick,'setCalendarImportance')]")
        )
    )

    # 각 별 레벨을 매번 새로 찾아서 처리 (StaleElement 방지)
    # 별3개('3')만 선택, 별1·2개는 해제
    for level in ('1', '2', '3'):
        want_selected = (level == '3')
        for attempt in range(3):
            try:
                link = driver.find_element(
                    By.XPATH,
                    f"//a[@onclick and contains(@onclick,\"setCalendarImportance('{level}')\")]"
                )
                # 현재 선택 상태 파악 (체크박스 우선, 없으면 active 클래스로 판단)
                li = link.find_element(By.XPATH, './ancestor::li')
                try:
                    cb = li.find_element(By.CSS_SELECTOR, 'input[type="checkbox"]')
                    is_selected = cb.is_selected()
                except Exception:
                    is_selected = 'active' in (li.get_attribute('class') or '')

                if is_selected != want_selected:
                    driver.execute_script("arguments[0].click();", link)
                    time.sleep(0.4)
                break
            except StaleElementReferenceException:
                time.sleep(0.3)
                continue
            except Exception as e:
                print(f"  [!] 별{level}개 처리 실패: {e}")
                break

    # 드롭다운 닫기 (ESC 또는 바깥 클릭)
    driver.find_element(By.TAG_NAME, 'body').click()
    time.sleep(1)

    print("[✓] 충격(중요도) 별3개 설정 완료")


def set_countries(driver, wait):
    """나라 드롭박스 → G7 + 호주 + 중국 + 한국만 선택"""
    # 나라 버튼 클릭
    country_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[@onclick='toggleMainCountrySelection();']")
        )
    )
    country_btn.click()
    time.sleep(1)

    # 나라 선택 패널이 열렸는지 확인
    wait.until(
        EC.visibility_of_element_located(
            (By.XPATH, "//li[@onclick and contains(@onclick,'calendarSelecting')]")
        )
    )

    # 먼저 'Clear' 버튼으로 전체 선택 해제
    try:
        clear_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(),'Clear') or contains(@class,'clear')]")
            )
        )
        clear_btn.click()
        time.sleep(1)
        print("[✓] 전체 나라 선택 해제(Clear) 완료")
    except Exception as e:
        print(f"[!] Clear 버튼 클릭 실패: {e}")

    # 타깃 국가 코드를 대문자로 변환
    target_codes_upper = [code.upper() for code in TARGET_COUNTRIES.keys()]

    # 먼저 화면에 존재하는 모든 국가 코드를 수집 (요소 참조는 보관하지 않음)
    available_codes = []
    for li in driver.find_elements(By.XPATH, "//li[contains(@onclick,'calendarSelecting')]"):
        onclick_attr = li.get_attribute('onclick')
        if not onclick_attr:
            continue
        # 국가 코드 추출: calendarSelecting(this, event, 'AUS')
        m = re.search(r"'([A-Z0-9]+)'", onclick_attr)
        if m and m.group(1) in target_codes_upper:
            available_codes.append(m.group(1))

    # 타깃 국가만 매번 새로 찾아서 클릭 (StaleElement 방지)
    selected_countries = []
    for code in available_codes:
        for attempt in range(3):
            try:
                li = driver.find_element(
                    By.XPATH, f"//li[contains(@onclick,\"'{code}'\")]"
                )
                try:
                    cb = li.find_element(By.CSS_SELECTOR, 'input[type="checkbox"]')
                    already = cb.is_selected()
                except Exception:
                    already = 'active' in (li.get_attribute('class') or '')

                if not already:
                    driver.execute_script("arguments[0].click();", li)
                    time.sleep(0.3)
                selected_countries.append(code)
                print(f"  [✓] 선택: {code} ({TARGET_COUNTRIES.get(code.lower(), code)})")
                break
            except StaleElementReferenceException:
                time.sleep(0.3)
                continue
            except Exception as e:
                print(f"  [!] {code} 선택 실패: {e}")
                break

    # 패널 닫기
    driver.find_element(By.TAG_NAME, 'body').click()
    time.sleep(1.5)

    print(f"[✓] 나라 선택 완료: {selected_countries}")


def extract_table(driver, wait):
    """
    필터 적용 후 생성된 테이블에서
    날짜, 시간, 국가, 지표명, 실제, 이전, 예측치 추출
    ★ 날짜는 <td>가 아니라 <th>(thead 행)에 들어있음 ★
    """
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'tr')))
    time.sleep(1)  # 데이터 로딩 대기

    rows = driver.find_elements(By.CSS_SELECTOR, 'table tr')
    data = []
    current_date = ''
    date_pat = re.compile(r'^\d{2}/\d{2}/\d{4}$')

    for row in rows:
        # 1) 날짜 행: th 안에 날짜(dd/mm/yyyy)가 들어있음
        ths = row.find_elements(By.TAG_NAME, 'th')
        if ths:
            head = ths[0].text.strip()
            if date_pat.match(head):
                current_date = head
            continue  # 헤더 행은 데이터로 쓰지 않음

        # 2) 데이터 행: td 9개 이상
        cells = row.find_elements(By.TAG_NAME, 'td')
        if len(cells) >= 9:
            time_val    = cells[0].text.strip()   # 시간
            country_iso = cells[3].text.strip()   # 국가코드
            indicator   = cells[4].text.strip()   # 지표명
            actual      = cells[5].text.strip()   # 실제
            previous    = cells[6].text.strip()   # 이전
            forecast    = cells[7].text.strip()   # 예측치

            if time_val and indicator:
                data.append({
                    '날짜':   current_date,
                    '시간':   time_val,
                    '국가':   country_iso,
                    '지표명': indicator,
                    '실제':   actual,
                    '이전':   previous,
                    '예측치': forecast,
                })

    return data


# ═══════════════════════════════════════════════════════════════
# ▼▼▼ 여기부터 추가된 부분: 대시보드 HTML 생성 ▼▼▼
#   df 를 받아서 데이터가 박힌 dashboard.html 을 통째로 찍어낸다.
# ═══════════════════════════════════════════════════════════════
_DASH_TEMPLATE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Economic Calendar</title>
<style>
  :root{--ink:#1a1c1f;--muted:#9aa0a6;--line:#e8e8e6;--head:#f4f3f1;
    --badge:#6e1f1f;--up:#1a7a4c;--down:#c0392b;--flat:#5a5f66;}
  *{box-sizing:border-box;}
  body{margin:0;background:#f7f6f3;color:var(--ink);
    font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;}
  .num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum";}
  .wrap{max-width:1080px;margin:0 auto;padding:28px 20px 80px;}
  header.top{display:flex;align-items:flex-end;justify-content:space-between;
    border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:18px;flex-wrap:wrap;gap:12px;}
  .brand{font-family:Georgia,serif;font-size:26px;font-weight:700;letter-spacing:-.3px;}
  .brand small{display:block;font-family:sans-serif;font-size:11px;font-weight:600;
    letter-spacing:.18em;color:var(--muted);margin-top:4px;}
  .gen{font-size:11px;color:var(--muted);}
  .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px;}
  .stat{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px;}
  .stat .v{font-size:22px;font-weight:700;}
  .stat .l{font-size:11px;color:var(--muted);margin-top:2px;}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;}
  .chip{font-size:12px;font-weight:600;border:1px solid var(--line);background:#fff;border-radius:999px;
    padding:5px 11px;cursor:pointer;user-select:none;}
  .chip.on{background:var(--ink);color:#fff;border-color:var(--ink);}
  .board{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;}
  table{width:100%;border-collapse:collapse;}
  th{font-size:12px;color:var(--muted);font-weight:600;text-align:right;padding:9px 16px;}
  th.l{text-align:left;}
  tr.day td{background:var(--head);border-top:1px solid var(--line);border-bottom:1px solid var(--line);
    padding:8px 16px;font-weight:700;font-size:14px;}
  tr.day .colhead{font-size:11px;color:var(--muted);font-weight:600;text-align:right;}
  tr.ev td{padding:10px 16px;border-bottom:1px solid #f1f0ee;vertical-align:middle;}
  .time{display:inline-block;background:var(--badge);color:#fff;font-weight:700;font-size:11px;
    padding:4px 7px;border-radius:4px;min-width:74px;text-align:center;}
  .flag{font-size:15px;margin:0 6px 0 10px;}
  .ccode{font-size:11px;font-weight:700;color:var(--muted);}
  .ind{font-size:14px;}
  .period{color:var(--muted);font-size:11px;margin-left:6px;}
  td.r{text-align:right;}
  .val{font-weight:700;font-size:14px;}
  .val.up{color:var(--up);}.val.down{color:var(--down);}.val.flat{color:var(--ink);}
  .val.empty{color:var(--muted);font-weight:500;}
  .prev,.fcst{color:var(--flat);font-weight:600;font-size:13px;}
  .surp{display:inline-block;font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;margin-left:8px;}
  .surp.up{background:#e6f4ec;color:var(--up);}
  .surp.down{background:#fbeae8;color:var(--down);}
  .surp.flat{background:#eef0f1;color:var(--flat);}
  .surp.pend{background:#f3f1ec;color:#9a7a2e;}
  .note{font-size:12px;color:var(--muted);margin-top:14px;line-height:1.6;}
  @media(max-width:680px){.stats{grid-template-columns:repeat(2,1fr);}.period{display:none;}}
</style></head><body><div class="wrap">
  <header class="top">
    <div class="brand">Economic Calendar<small>G7 · AU · CN · KR — HIGH IMPORTANCE</small></div>
    <div class="gen num" id="gen"></div>
  </header>
  <div class="stats" id="stats"></div>
  <div class="chips" id="chips"></div>
  <div class="board"><table id="tbl"></table></div>
  <div class="note">· <b>서프라이즈 배지</b>는 <b>실제 − 예측치</b>의 방향(사실)만 표시(▲ 상회 / ▼ 하회 / = 부합).
    상회·하회가 호재인지 악재인지는 지표마다 다른 해석의 영역이라 판단하지 않았습니다.<br>
    · 실제값이 비어 있으면(발표 전) <b>예정</b>으로 표시됩니다.</div>
</div>
<script>
const DATA_RAW = __DATA_JSON__;
const GENERATED = "__GENERATED__";
const COUNTRY={EA:["🇪🇺","유로존"],EU:["🇪🇺","유로존"],US:["🇺🇸","미국"],USA:["🇺🇸","미국"],
 GB:["🇬🇧","영국"],UK:["🇬🇧","영국"],GBR:["🇬🇧","영국"],FR:["🇫🇷","프랑스"],FRA:["🇫🇷","프랑스"],
 DE:["🇩🇪","독일"],DEU:["🇩🇪","독일"],IT:["🇮🇹","이탈리아"],ITA:["🇮🇹","이탈리아"],
 JP:["🇯🇵","일본"],JPN:["🇯🇵","일본"],CA:["🇨🇦","캐나다"],CAN:["🇨🇦","캐나다"],
 AU:["🇦🇺","호주"],AUS:["🇦🇺","호주"],CN:["🇨🇳","중국"],CHN:["🇨🇳","중국"],KR:["🇰🇷","한국"],KOR:["🇰🇷","한국"]};
function ctry(c){c=(c||"").toUpperCase().trim();return COUNTRY[c]||["🏳️",c];}
function splitPeriod(n){const m=(n||"").match(/\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|Q[1-4]|H[12]|\d{4})$/i);
  return m?[n.slice(0,m.index).trim(),m[1]]:[n||"",""];}
function parseNum(s){if(s==null)return null;let t=String(s).trim().replace(/,/g,"").replace(/%/g,"");
  if(t===""||t==="-"||t==="—")return null;let mu=1;const L=t.slice(-1).toUpperCase();
  if(L==="K"){mu=1e3;t=t.slice(0,-1);}else if(L==="M"){mu=1e6;t=t.slice(0,-1);}
  else if(L==="B"){mu=1e9;t=t.slice(0,-1);}else if(L==="T"){mu=1e12;t=t.slice(0,-1);}
  const n=parseFloat(t);return isNaN(n)?null:n*mu;}
function surprise(a,f){const x=parseNum(a),y=parseNum(f);if(x==null)return{k:"pend",t:"예정"};
  if(y==null)return null;if(x>y)return{k:"up",t:"▲ 상회"};if(x<y)return{k:"down",t:"▼ 하회"};return{k:"flat",t:"= 부합"};}
const DATA=DATA_RAW.map(r=>({날짜:(r["날짜"]||"").trim(),시간:(r["시간"]||"").trim(),
  국가:(r["국가"]||"").trim(),지표명:(r["지표명"]||"").trim(),
  실제:(r["실제"]??"").toString().trim(),이전:(r["이전"]??"").toString().trim(),
  예측치:(r["예측치"]??"").toString().trim()})).filter(r=>r.지표명);
let active=new Set(DATA.map(r=>r.국가.toUpperCase()));
function render(){
  const total=DATA.length,released=DATA.filter(r=>parseNum(r.실제)!=null).length;
  const beats=DATA.filter(r=>{const s=surprise(r.실제,r.예측치);return s&&s.k==="up";}).length;
  const miss=DATA.filter(r=>{const s=surprise(r.실제,r.예측치);return s&&s.k==="down";}).length;
  gen.textContent="생성: "+GENERATED+" · "+total+"건";
  stats.innerHTML=`<div class="stat"><div class="v num">${total}</div><div class="l">전체 이벤트</div></div>
    <div class="stat"><div class="v num">${total-released}</div><div class="l">발표 예정</div></div>
    <div class="stat"><div class="v num" style="color:var(--up)">${beats}</div><div class="l">예상 상회</div></div>
    <div class="stat"><div class="v num" style="color:var(--down)">${miss}</div><div class="l">예상 하회</div></div>`;
  const codes=[...new Set(DATA.map(r=>r.국가.toUpperCase()))];
  chips.innerHTML=codes.map(c=>{const[f,n]=ctry(c);return `<span class="chip ${active.has(c)?"on":""}" data-c="${c}">${f} ${n}</span>`;}).join("");
  chips.querySelectorAll(".chip").forEach(el=>el.onclick=()=>{const c=el.dataset.c;active.has(c)?active.delete(c):active.add(c);render();});
  const rows=DATA.filter(r=>active.has(r.국가.toUpperCase())),by={};
  rows.forEach(r=>{const k=r.국가.toUpperCase();(by[k]=by[k]||[]).push(r);});
  // 국가별 그룹: 미국(US/USA) 우선 → 나머지는 코드순
  const usFirst=c=>(c==="US"||c==="USA")?0:1;
  const groupCodes=Object.keys(by).sort((a,b)=>usFirst(a)-usFirst(b)||a.localeCompare(b));
  // 날짜 dd/mm/yyyy → 정렬용 숫자(yyyymmdd)
  const dkey=d=>{const m=(d||"").match(/^(\d{2})\/(\d{2})\/(\d{4})$/);return m?+(m[3]+m[2]+m[1]):0;};
  let h=`<thead><tr><th class="l">날짜 / 시간 / 지표</th><th>실제</th><th>이전</th><th>예측치</th></tr></thead><tbody>`;
  groupCodes.forEach(code=>{const[f,n]=ctry(code);
    h+=`<tr class="day"><td><span class="flag">${f}</span> ${n}</td><td class="colhead">실제</td><td class="colhead">이전</td><td class="colhead">예측치</td></tr>`;
    by[code].slice().sort((x,y)=>dkey(x.날짜)-dkey(y.날짜)).forEach(r=>{const[ind,per]=splitPeriod(r.지표명),s=surprise(r.실제,r.예측치),cls=s?s.k:"flat";
      const a=r.실제?`<span class="val ${cls}">${r.실제}</span>`:`<span class="val empty">—</span>`;
      const b=s?`<span class="surp ${s.k}">${s.t}</span>`:"";
      h+=`<tr class="ev"><td><span class="period">${r.날짜||""}</span> <span class="time num">${r.시간}</span>
        <span class="ind">${ind}</span>${per?`<span class="period">${per}</span>`:""}${b}</td>
        <td class="r num">${a}</td><td class="r num"><span class="prev">${r.이전||"—"}</span></td>
        <td class="r num"><span class="fcst">${r.예측치||"—"}</span></td></tr>`;});
  });
  tbl.innerHTML=h+`</tbody>`;
}
render();
</script></body></html>"""


def build_dashboard(df, out_path=None):
    """df 를 받아 데이터가 박힌 대시보드 HTML 을 통째로 생성"""
    if out_path is None:
        out_path = os.path.join(SCRIPT_DIR, 'dashboard.html')
    records = df.fillna('').astype(str).to_dict(orient='records')
    data_json = json.dumps(records, ensure_ascii=False).replace('</', '<\\/')
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    html = _DASH_TEMPLATE.replace('__DATA_JSON__', data_json).replace('__GENERATED__', now)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[✓] 대시보드 생성 완료: {os.path.abspath(out_path)}  ({len(records)}건)")
    return out_path
# ═══════════════════════════════════════════════════════════════
# ▲▲▲ 추가 부분 끝 ▲▲▲
# ═══════════════════════════════════════════════════════════════


def main():
    driver = setup_driver(headless=False)  # headless=True 로 변경 가능
    wait = WebDriverWait(driver, 15)

    try:
        # 1) 사이트 접속
        print("[1] 사이트 접속 중...")
        driver.get('https://ko.tradingeconomics.com/calendar')
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'tr')))
        time.sleep(2)

        # 2) 충격(중요도) → 별3개만 선택
        print("[2] 충격 드롭박스 설정 중...")
        set_importance_3stars(driver, wait)
        time.sleep(1.5)

        # 3) 나라 → G7 + 호주 + 중국 + 한국
        print("[3] 나라 드롭박스 설정 중...")
        set_countries(driver, wait)
        time.sleep(2)

        # 4) 테이블 데이터 추출
        print("[4] 테이블 데이터 추출 중...")
        data = extract_table(driver, wait)

        if not data:
            print("[!] 데이터가 없습니다. 필터 설정을 확인하세요.")
            return

        # 5) DataFrame 생성 및 출력
        df = pd.DataFrame(data, columns=['날짜', '시간', '국가', '지표명', '실제', '이전', '예측치'])

        # 국가별 정렬: 미국(US/USA) 우선, 나머지는 기존 순서 유지(안정 정렬)
        us_codes = {'US', 'USA'}
        df = df.sort_values(
            by='국가',
            key=lambda col: col.str.upper().map(lambda c: 0 if c in us_codes else 1),
            kind='stable',
        ).reset_index(drop=True)

        print(f"\n[✓] 총 {len(df)}개 행 추출 완료\n")
        print(df.to_string(index=False))

        # 6) CSV 저장 (Excel 등에서 열려 있어 잠겨 있으면 다른 이름으로 저장)
        csv_path = os.path.join(SCRIPT_DIR, 'tradingeconomics_calendar.csv')
        try:
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"\n[✓] CSV 저장 완료: {csv_path}")
        except PermissionError:
            alt_path = os.path.join(SCRIPT_DIR, f"tradingeconomics_calendar_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv")
            df.to_csv(alt_path, index=False, encoding='utf-8-sig')
            print(f"\n[!] '{csv_path}' 가 열려 있어(Excel 등) 저장 불가 → 대신 저장: {alt_path}")

        # 7) 대시보드 HTML 생성 (CSV 저장 성공 여부와 무관하게 항상 생성)
        build_dashboard(df)

        return df

    finally:
        input("\n[종료하려면 Enter를 누르세요...]")
        driver.quit()


if __name__ == '__main__':
    df = main()
