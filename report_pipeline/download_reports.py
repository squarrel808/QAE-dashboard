"""
리서치 리포트 통합 다운로더 (Marquee + BofA + HSBC + JPMM)
 [Marquee/GS] 4개 섹션 × (1d) × 10개 = 최대 40개  + Portfolio Strategy 5개
 [BofA]       Portfolio Strategy 5개
 [HSBC]       Trending Research Reports 상위 10개
 [JPMM/JPM]   Most Read(Day) 10개 + House Views(어제~오늘)
              Research 폴더 중 "3d ago" 이내(3일 이하)만
전제: 'C:\\selenium_profile' 전용 프로필을 사용. 첫 실행 때 각 사이트에 1회만
      수동 로그인하면, 이후로는 세션이 저장돼 로그인 상태가 계속 유지됩니다.
      (평소 쓰는 크롬과 별개라 충돌 없고, 크롬을 종료할 필요도 없음)
필요 패키지: pip install selenium
"""

import os
import re
import time
import json
import base64
from datetime import datetime, date, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


# ============================================================
#  공통 설정
# ============================================================
BASE = "https://marquee.gs.com"
TRENDING_URL = f"{BASE}/content/site/trending.html"
# [변경] 다운로드 폴더를 이 스크립트와 같은 폴더 안의 '보따리\\YYMMDD' 로 둔다.
#        (원본은 C:\\Users\\infomax\\Desktop\\보따리 였으나, 머신이 달라 프로젝트 내부로 이동)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(_SCRIPT_DIR, "보따리", datetime.now().strftime("%y%m%d"))
PER_SECTION = 10                 # Marquee: 한 시간 탭당 받을 개수
TIMEFRAMES = ["1d"]              # Marquee: 1d만 순회

# 리포트 1건당 PDF가 뜨기를 기다리는 최대 시간(초). PDF 버튼/뷰어가 랜덤하게 늦게 뜨는 경우 대비.
PDF_WAIT_MAX = 120               # ← 2분

# 로그인 유지용 전용 프로필 폴더 (Chrome 136+ 는 실제 프로필 디버그를 막으므로 별도 프로필 사용).
#   크롬_연동.bat 의 --user-data-dir 과 동일해야 함.
CHROME_PROFILE_DIR = r"C:\selenium_profile"

SECTIONS = [
    "Overall Most Popular Research",
    "Economics Research",
    "Equity Research",
    "Beyond Research",
]

# Portfolio Strategy Research 섹션에서 추가로 받을 개수 (Marquee 끝에 이어서 받음)
PORTFOLIO_TITLE = "Portfolio Strategy Research"
PORTFOLIO_PER_SECTION = 5

BOFA_DASHBOARD = "https://markets.ml.com/researchlibrary/rltrendsdashboard"
BOFA_PER_SECTION = 10

HSBC_HOME = "https://www.research.hsbc.com/ibcom/in/reach/servlet/ReachHome"
HSBC_PER_SECTION = 10

JPMM_HOME = "https://markets.jpmorgan.com/jpmm/"
JPMM_IFRAME_URL = "https://markets.jpmorgan.com/mcp-home/"
JPMM_MAX_AGE_DAYS = 1            # 매일 실행이므로 1일 이내만 (중복 방지; 필요시 숫자 조정)
JPMM_MAX_ITEMS = 30             # 안전 상한 (무한 스크롤/과다 다운로드 방지)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def get_browser_download_dir():
    """
    크롬 프로필이 '실제로' 다운로드를 떨구는 폴더(download.default_directory)를 Preferences에서 읽는다.

    [중요] CDP(Browser.setDownloadBehavior)로 다운로드 경로를 강제하면, BofA 전략 리포트처럼
      'target=_blank로 열린 about:blank 탭에서 시작된 큰 PDF'가 그 탭이 자동으로 닫히면서
      다운로드 도중 '취소'된다. (작은 PDF는 닫히기 전에 끝나서 됐던 것)
    → 그래서 CDP 강제를 쓰지 않고, 프로필 기본 폴더(prompt_for_download=false라 자동 저장)로
      받게 둔 뒤, 여기서 읽은 폴더를 감시해서 받은 파일을 DOWNLOAD_DIR로 옮긴다.
    """
    try:
        prefs_path = os.path.join(CHROME_PROFILE_DIR, "Default", "Preferences")
        with open(prefs_path, encoding="utf-8") as f:
            dd = ((json.load(f).get("download") or {}).get("default_directory"))
        if dd and os.path.isdir(dd):
            return dd
    except Exception:
        pass
    return DOWNLOAD_DIR


# 브라우저가 클릭-다운로드를 떨구는 실제 폴더 (여기서 받아 → DOWNLOAD_DIR로 옮김)
BROWSER_DL_DIR = get_browser_download_dir()


def make_driver():
    opts = Options()
    # ▼ 이미 켜둔 Chrome(크롬_연동.bat, 디버깅 포트 9222)에 '붙기' → 그 창의 로그인 세션 그대로 사용.
    #   (Chrome 136+는 기본 프로필 자동화를 막지만, 전용 프로필+디버깅포트로 띄운 창엔 붙을 수 있음)
    opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        raise RuntimeError(
            "[연결 실패] 9222 포트의 Chrome을 못 찾음 → 바탕화면 '크롬_연동.bat'을 "
            "먼저 더블클릭해 Chrome을 켜고 로그인한 뒤 다시 실행하세요. (원본: %s)"
            % repr(e)[:100])
    # ※ 다운로드 경로를 CDP로 강제하지 않는다(위 get_browser_download_dir 설명 참고).
    #    프로필 기본 폴더(BROWSER_DL_DIR)로 받게 두고, 받은 파일을 DOWNLOAD_DIR로 옮긴다.
    driver.set_page_load_timeout(60)
    return driver


def safe_name(text, idx, section, tf):
    text = "".join(c if c.isalnum() or c in " -_" else "_" for c in text)[:70].strip()
    return f"{section.replace(' ', '_')}_{tf}_{idx:02d}_{text or 'report'}.pdf"


def wait_new_pdf(before, timeout=40):
    """브라우저 다운로드 폴더(BROWSER_DL_DIR)에 새 .pdf가 완성될 때까지 대기
    (.crdownload 사라질 때까지). 반환값은 BROWSER_DL_DIR 안의 파일명."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            files = set(os.listdir(BROWSER_DL_DIR))
        except Exception:
            files = set()
        new = [f for f in files - before if f.lower().endswith(".pdf")]
        downloading = [f for f in files if f.endswith(".crdownload")]
        if new and not downloading:
            return new[0]
        time.sleep(1)
    return None


def looks_like_pdf_viewer(driver):
    """현재 탭이 'Chrome 내장 PDF 뷰어'인지(=URL 자체가 PDF 파일) 판별."""
    try:
        ct = (driver.execute_script("return document.contentType") or "").lower()
        if ct == "application/pdf":
            return True
    except Exception:
        pass
    try:
        url = (driver.current_url or "").lower().split("?")[0].split("#")[0]
        if url.endswith(".pdf"):
            return True
    except Exception:
        pass
    try:
        if driver.find_elements(By.CSS_SELECTOR, "embed[type='application/pdf']"):
            return True
    except Exception:
        pass
    return False


def download_current_pdf_via_fetch(driver, out_path, timeout=90):
    """
    현재 탭이 Chrome 내장 PDF 뷰어(window.location.href 자체가 PDF)일 때,
    '같은 출처 fetch'(로그인 쿠키 자동)로 받아 저장. (JPM/HSBC 직링크용)
    ※ BofA 처럼 다른 출처로 리다이렉트되는 링크는 fetch가 CORS로 막히고,
      requests는 회사망 SSL에 막히므로 → '버튼 클릭 → 브라우저 다운로드' 경로를 쓴다.
    """
    script = r"""
    const cb = arguments[arguments.length - 1];
    fetch(window.location.href, {credentials: 'include'})
      .then(r => r.blob())
      .then(blob => {
        const fr = new FileReader();
        fr.onload  = () => cb(fr.result);
        fr.onerror = () => cb('ERR:reader');
        fr.readAsDataURL(blob);
      })
      .catch(e => cb('ERR:' + e));
    """
    driver.set_script_timeout(timeout)
    data = driver.execute_async_script(script)
    if not data or str(data).startswith("ERR:"):
        raise RuntimeError(f"PDF fetch 실패: {str(data)[:120]}")
    b64 = data.split(",", 1)[1] if str(data).startswith("data:") else data
    raw = base64.b64decode(b64)
    if len(raw) < 1000:
        raise RuntimeError("받은 PDF가 너무 작음(빈 파일?)")
    with open(out_path, "wb") as f:
        f.write(raw)


# BofA 리포트 페이지의 PDF 아이콘(글자 없는 아이콘): a#print_pdf_anchor, title='PDF'
#   → 클릭하면 Content-Disposition으로 PDF가 '다운로드'됨 (fetch는 CORS, requests는 SSL로 막힘).
PDF_ANCHOR_CSS = "a#print_pdf_anchor[href], a[id*='print_pdf'][href], a[title='PDF'][href]"

# 그 외 일반 PDF/Download 버튼(클릭용) XPath 묶음
PDF_BTN_XPATH = (
    "//a[@id='print_pdf_anchor'] | //a[@title='PDF'] | "
    "//a[normalize-space()='PDF'] | //button[normalize-space()='PDF'] | "
    "//a[contains(translate(.,'PDF','pdf'),'pdf')] | "
    "//a[contains(@href,'.pdf')] | "
    "//*[@title='Download' or @aria-label='Download'] | "
    "//button[contains(translate(.,'DOWNLOAD','download'),'download')] | "
    "//a[contains(translate(.,'DOWNLOAD','download'),'download')] | "
    "//*[@data-testid='download' or @data-testid='download-button']")


def _find_pdf_clickable(driver):
    """현재 탭의 top 문서 + 모든 iframe 안에서 PDF 아이콘/버튼을 찾는다.
    찾으면 '그 요소가 있는 프레임으로 전환된 상태'로 요소를 반환, 없으면 default_content로 돌아가 None.
    (일부 BofA 리포트는 PDF 아이콘이 iframe 안에 있음)"""
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    els = (driver.find_elements(By.CSS_SELECTOR, PDF_ANCHOR_CSS)
           or driver.find_elements(By.XPATH, PDF_BTN_XPATH))
    if els:
        return els[0]
    for fr in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(fr)
            els = (driver.find_elements(By.CSS_SELECTOR, PDF_ANCHOR_CSS)
                   or driver.find_elements(By.XPATH, PDF_BTN_XPATH))
            if els:
                return els[0]   # 이 iframe 컨텍스트 유지한 채 반환
        except Exception:
            continue
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return None


def download_in_new_tab(driver, out_path, timeout=40, open_via=None, href=None,
                        must_download=False):
    """
    공통 다운로드 헬퍼: 새 탭(또는 새 창)에서 리포트를 열고 PDF를 받는다.
    최대 PDF_WAIT_MAX(2분) 동안 아래를 반복 체크:
      (A) 탭 자체가 'Chrome 내장 PDF 뷰어'(URL이 PDF)  → fetch로 저장   (JPM/HSBC 직링크)
      (B) 리포트 페이지(또는 iframe 안)의 PDF 아이콘/버튼 → 클릭 → PDF 다운로드  (BofA)
          ※ 첫 클릭이 '페이지 로딩 완료 전'이면 다운로드가 안 걸리는 경우가 있어
            다운로드가 잡힐 때까지 15초마다 재클릭한다.
      (C) 브라우저 다운로드 폴더에 새 PDF가 떨어짐      → DOWNLOAD_DIR로 옮겨 채택
      (B') 클릭이 새 PDF 뷰어 탭을 열면               → 그 탭에서 fetch로 저장
    끝나면 새 탭 닫고 원래 탭 복귀.
    must_download=True(BofA): 2분 안에 PDF 못 잡으면 빈 렌더로 안 넘어가고 예외 → '실패' 처리.
    """
    before = set(os.listdir(BROWSER_DL_DIR))
    main = driver.current_window_handle

    if open_via == "already":
        # 호출 측(막대 클릭)이 이미 새 탭을 열어둠 → main(대시보드)이 아닌 '가장 최근' 탭이 리포트 탭.
        #   (여기서 handles_before를 캡처하면 이미 그 탭이 포함돼 'diff=0' 레이스로 타임아웃 나던 버그)
        WebDriverWait(driver, 20).until(lambda d: len(d.window_handles) > 1)
        others = [h for h in driver.window_handles if h != main]
        new_handle = others[-1]
    else:
        handles_before = set(driver.window_handles)
        if href:
            driver.execute_script("window.open(arguments[0], '_blank');", href)
        WebDriverWait(driver, 20).until(
            lambda d: len(set(d.window_handles) - handles_before) >= 1)
        new_handle = list(set(driver.window_handles) - handles_before)[0]
    driver.switch_to.window(new_handle)

    try:
        # readyState 대기 (PDF 뷰어는 complete를 안 알릴 수 있어 실패해도 무시)
        try:
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            pass
        time.sleep(2)

        # 'Proceed'(오래된 리포트 → 저장할지 묻는 안내) 페이지가 뜨면 그 리포트는 건너뜀
        proceed = driver.find_elements(By.ID, "proceedBtnId")
        if not proceed:
            proceed = driver.find_elements(
                By.XPATH, "//input[@value='Proceed'] | //button[normalize-space()='Proceed']")
        if proceed:
            raise RuntimeError("오래된 리포트(Proceed 안내) → 건너뜀")

        deadline = time.time() + PDF_WAIT_MAX
        last_click = 0.0       # 마지막 클릭 시각 (0이면 아직 클릭 전)
        pre_click = None
        while time.time() < deadline:
            # 매 루프 시작 시 리포트 탭의 top 문서로 정렬
            try:
                if driver.current_window_handle != new_handle and new_handle in driver.window_handles:
                    driver.switch_to.window(new_handle)
                driver.switch_to.default_content()
            except Exception:
                pass

            # (A) 현재 탭이 PDF 뷰어(=URL이 PDF) → fetch로 저장
            try:
                if looks_like_pdf_viewer(driver):
                    download_current_pdf_via_fetch(driver, out_path, timeout=PDF_WAIT_MAX)
                    return
            except Exception:
                pass

            # (C) (클릭 결과 or 자동) 다운로드가 떨어졌나 → DOWNLOAD_DIR로 옮김
            fname = wait_new_pdf(before, timeout=1)
            if fname:
                os.replace(os.path.join(BROWSER_DL_DIR, fname), out_path)
                return

            # (B') 클릭으로 'PDF 뷰어 새 탭'이 열렸으면 그 탭에서 fetch
            if pre_click is not None:
                for w in (set(driver.window_handles) - pre_click):
                    try:
                        driver.switch_to.window(w)
                        if looks_like_pdf_viewer(driver):
                            download_current_pdf_via_fetch(driver, out_path, timeout=PDF_WAIT_MAX)
                            return
                    except Exception:
                        pass
                if new_handle in driver.window_handles:
                    try:
                        driver.switch_to.window(new_handle)
                    except Exception:
                        pass

            # (B) PDF 아이콘/버튼(top or iframe)을 클릭. 첫 클릭이 페이지 로딩 전이라 다운로드가
            #     안 떨어지는 경우가 있어, 다운로드가 잡힐 때까지 15초마다 '재클릭'한다.
            #     ※ 다운로드 진행중(.crdownload 존재)이면 재클릭하지 않고 기다린다.
            crd = [f for f in os.listdir(BROWSER_DL_DIR) if f.endswith(".crdownload")]
            if not crd and time.time() - last_click >= 15:
                el = _find_pdf_clickable(driver)
                if el is not None:
                    pre_click = set(driver.window_handles)
                    try:
                        driver.execute_script("arguments[0].click();", el)
                    except Exception:
                        pass
                    last_click = time.time()
                    try:
                        driver.switch_to.default_content()
                    except Exception:
                        pass

            time.sleep(2)

        # 2분 기다려도 PDF를 못 잡음
        if must_download:
            raise RuntimeError(f"PDF가 {PDF_WAIT_MAX}초 안에 안 떨어짐 → 건너뜀")

        # (must_download=False) 뷰어/본문 통째 렌더 폴백
        if new_handle in driver.window_handles:
            try:
                driver.switch_to.window(new_handle)
                driver.switch_to.default_content()
            except Exception:
                pass
        result = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True, "preferCSSPageSize": True})
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(result["data"]))
    finally:
        # main(원래 탭) 외의 새 탭/뷰어 탭을 모두 정리 후 원래 탭 복귀
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        for h in list(driver.window_handles):
            if h != main:
                try:
                    driver.switch_to.window(h)
                    driver.close()
                except Exception:
                    pass
        try:
            driver.switch_to.window(main)
        except Exception:
            pass


# ============================================================
#  Marquee (Goldman Sachs)
# ============================================================
def open_trending(driver, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            driver.get(TRENDING_URL)
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div#content-card-header")))
            time.sleep(2)
            return
        except TimeoutException as e:
            last_err = e
            print(f"  (trending 로드 재시도 {attempt + 1}/{retries})")
            time.sleep(3)
    raise last_err


def find_card(driver, title):
    # Marquee는 카드를 동적으로 다시 그려서 요소가 stale 되기 쉬움 → 재조회 재시도
    for _ in range(5):
        try:
            for h in driver.find_elements(By.CSS_SELECTOR, "div#content-card-header"):
                if h.text.strip().lower().startswith(title.lower()):
                    return h.find_element(By.XPATH, "..")
            raise RuntimeError(f"섹션을 못 찾음: {title}")
        except StaleElementReferenceException:
            time.sleep(1)
    raise RuntimeError(f"섹션을 못 찾음(stale 반복): {title}")


def select_timeframe(driver, card, label):
    for a in card.find_elements(By.CSS_SELECTOR, "a.nav-link"):
        if a.text.strip() == label:
            if "active" not in (a.get_attribute("class") or ""):
                driver.execute_script("arguments[0].click();", a)
                time.sleep(2)
            return True
    return False


def collect_links(card, css, limit=PER_SECTION):
    # 링크 수집 도중 DOM 재렌더로 stale 나면 처음부터 다시 수집(원자적으로)
    for _ in range(5):
        items, seen = [], set()
        try:
            for a in card.find_elements(By.CSS_SELECTOR, css):
                href = a.get_attribute("href")
                if not href or href.endswith("#") or href in seen:
                    continue
                seen.add(href)
                items.append((href, a.text.strip()))
                if len(items) >= limit:
                    break
            return items
        except StaleElementReferenceException:
            time.sleep(1)
    return items


def download_research(driver, href, out_path):
    driver.get(href)
    pdf_link = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//a[normalize-space()='PDF']")))
    report_win = driver.current_window_handle
    before_files = set(os.listdir(BROWSER_DL_DIR))
    before_wins = set(driver.window_handles)
    driver.execute_script("arguments[0].click();", pdf_link)

    # (A) 파일로 바로 다운로드되면 그걸 채택 (Marquee는 보통 뷰어로 열려 안 옴 → 짧게만 확인)
    fname = wait_new_pdf(before_files, timeout=5)
    if fname:
        os.replace(os.path.join(BROWSER_DL_DIR, fname), out_path)
        return

    # (B) 새 탭이 Chrome PDF 뷰어로 열리면(같은 출처) fetch로 저장 후 탭 닫기
    time.sleep(1)
    new_wins = [w for w in driver.window_handles if w not in before_wins]
    if new_wins:
        driver.switch_to.window(new_wins[-1])
        try:
            if looks_like_pdf_viewer(driver):
                download_current_pdf_via_fetch(driver, out_path)
                return
        finally:
            try:
                driver.close()
            finally:
                driver.switch_to.window(report_win)

    # (C) 같은 탭이 PDF 뷰어로 바뀐 경우 fetch
    if looks_like_pdf_viewer(driver):
        download_current_pdf_via_fetch(driver, out_path)
        return

    raise RuntimeError("PDF 다운로드 대기 시간 초과(다운로드/뷰어 모두 실패)")


def download_beyond(driver, href, out_path):
    driver.get(href)
    pdf_btn = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.XPATH, "//button[normalize-space()='PDF'] | //a[normalize-space()='PDF']")))
    report_win = driver.current_window_handle
    before_files = set(os.listdir(BROWSER_DL_DIR))
    before_wins = set(driver.window_handles)
    driver.execute_script("arguments[0].click();", pdf_btn)

    # (A) 파일 다운로드 / (B) 새 탭 뷰어 fetch / (C) 같은 탭 뷰어 fetch — Marquee와 동일 폴백
    fname = wait_new_pdf(before_files, timeout=5)
    if fname:
        os.replace(os.path.join(BROWSER_DL_DIR, fname), out_path)
        return
    time.sleep(1)
    new_wins = [w for w in driver.window_handles if w not in before_wins]
    if new_wins:
        driver.switch_to.window(new_wins[-1])
        try:
            if looks_like_pdf_viewer(driver):
                download_current_pdf_via_fetch(driver, out_path)
                return
        finally:
            try:
                driver.close()
            finally:
                driver.switch_to.window(report_win)
    if looks_like_pdf_viewer(driver):
        download_current_pdf_via_fetch(driver, out_path)
        return

    # (D) 최후수단: 페이지 자체를 CDP로 PDF 렌더(기존 방식)
    result = driver.execute_cdp_cmd("Page.printToPDF", {
        "printBackground": True, "preferCSSPageSize": True})
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(result["data"]))


def marquee_portfolio_strategy(driver):
    """Portfolio Strategy Research 섹션의 상위 PORTFOLIO_PER_SECTION개 리포트를 받는다.
    (구조가 일반 Research 카드와 동일 → download_research 재사용)
    반환: 받은 개수."""
    print(f"\n=== {PORTFOLIO_TITLE} | 1d ===")
    card = find_card(driver, PORTFOLIO_TITLE)
    # 1d 탭이 있으면 선택(없으면 기본 상태 그대로 진행)
    select_timeframe(driver, card, "1d")
    card = find_card(driver, PORTFOLIO_TITLE)

    items = collect_links(card, 'a[href*="/reports/"]', limit=PORTFOLIO_PER_SECTION)
    print(f"  {len(items)}개 항목 수집")

    total = 0
    for i, (href, name) in enumerate(items, 1):
        out = os.path.join(DOWNLOAD_DIR, safe_name(name, i, PORTFOLIO_TITLE, "1d"))
        try:
            download_research(driver, href, out)
            total += 1
            print(f"  [1d {i:02d}] 성공  {os.path.getsize(out)//1024} KB  {name[:50]}")
        except Exception as e:
            print(f"  [1d {i:02d}] 실패  {name[:50]}  -> {e}")
        time.sleep(1)
    return total


def marquee_main(driver):
    open_trending(driver)
    total = 0
    for title in SECTIONS:
        is_beyond = title.lower().startswith("beyond")
        css = 'a[href*="/content/markets/"]' if is_beyond else 'a[href*="/reports/"]'
        for tf in TIMEFRAMES:
            print(f"\n=== {title} | {tf} ===")
            # 카드찾기→탭선택→링크수집을 한 단위로 재시도. stale 등 실패해도 이 섹션만 건너뜀
            #   (한 섹션 오류가 Marquee 전체를 죽이던 문제 방지)
            items, skip = None, False
            for attempt in range(3):
                try:
                    card = find_card(driver, title)
                    if not select_timeframe(driver, card, tf):
                        print(f"  ('{tf}' 탭 없음 → 건너뜀)"); skip = True; break
                    card = find_card(driver, title)
                    items = collect_links(card, css)
                    break
                except Exception as e:
                    print(f"  (섹션 준비 재시도 {attempt + 1}/3: {type(e).__name__})")
                    open_trending(driver)
            if skip:
                continue
            if not items:
                print("  (항목 수집 실패 → 섹션 건너뜀)")
                continue
            print(f"  {len(items)}개 항목 수집")
            for i, (href, name) in enumerate(items, 1):
                out = os.path.join(DOWNLOAD_DIR, safe_name(name, i, title, tf))
                try:
                    if is_beyond:
                        download_beyond(driver, href, out)
                    else:
                        download_research(driver, href, out)
                    total += 1
                    print(f"  [{tf} {i:02d}] 성공  {os.path.getsize(out)//1024} KB  {name[:50]}")
                except Exception as e:
                    print(f"  [{tf} {i:02d}] 실패  {name[:50]}  -> {e}")
                time.sleep(1)
            open_trending(driver)

    # 4개 섹션 끝난 뒤 Portfolio Strategy Research 5개를 이어서 받는다.
    open_trending(driver)
    try:
        total += marquee_portfolio_strategy(driver)
    except Exception as e:
        print(f"  ({PORTFOLIO_TITLE} 건너뜀: {repr(e)[:80]})")

    print(f"\nMarquee 완료: 총 {total}개")
    return total


# ============================================================
#  BofA Markets - Login
# ============================================================
# 전용 프로필 세션이 풀리면 대시보드 URL이 로그인 페이지로 바뀌어 계속 타임아웃 남.
# → 매 실행 시 자동 로그인 시도. (이미 로그인돼 있으면 로그인 버튼이 없으므로 자동 건너뜀)
BOFA_LOGIN_URL = BOFA_DASHBOARD   # 미로그인 시 이 URL이 로그인 폼으로 리다이렉트됨
BOFA_USERID    = os.environ.get("BOFA_USERID", "")    # 폴백용(자동완성 실패 시에만). .env 에 설정.
BOFA_PASSWORD  = os.environ.get("BOFA_PASSWORD", "")  # 평문 코드 저장 금지 → .env 에서 읽음

# product 순회 없이 차트 기본(전체 product) 상태에서 상위 BOFA_TOTAL개를 한 번에 받는다.
BOFA_PRODUCTS    = ["Investment Strategy", "Equity", "Rates & FX", "Economics"]  # (미사용; 참고용)
BOFA_PER_PRODUCT = 5   # (미사용; 참고용)
BOFA_TOTAL       = 20  # 한 번에 받을 총 개수

# 'Log In' 버튼 셀렉터 (onclick=doLogin / aria-label / 텍스트 'Log In' 전부 커버)
BOFA_LOGIN_BTN_XPATH = (
    "//button[contains(@onclick,'doLogin')] | "
    "//button[@aria-label='Login button'] | "
    "//button[@type='button' and normalize-space(translate(.,'LOGIN','login'))='log in'] | "
    "//input[@type='submit' and normalize-space(translate(@value,'LOGIN','login'))='log in']")


def bofa_login(driver, userid=BOFA_USERID, password=BOFA_PASSWORD, timeout=45):
    """
    BofA 로그인 (직접 입력판).
    전용 프로필에선 자동완성이 안 채워져 입력칸이 빈 채로 뜬다. 빈칸으로 'Log In'을
    눌러도 doLogin() 검증에 막혀 아무 일도 안 일어나므로, ID/PW를 직접 입력한 뒤 클릭한다.

    [핵심] 로그인 여부를 '아이디칸 id'가 아니라 '로그인 버튼 존재'로 판단한다.
           (아이디칸 id가 바뀌어도 동작하도록)
    """
    driver.get(BOFA_LOGIN_URL)

    # 로그인 버튼이 있으면 = 로그인 페이지. 없으면 = 이미 로그인된 세션 → 건너뜀.
    try:
        btn = WebDriverWait(driver, 12).until(
            EC.element_to_be_clickable((By.XPATH, BOFA_LOGIN_BTN_XPATH)))
    except TimeoutException:
        print("[BofA] 로그인 버튼 없음(이미 로그인된 세션) → 건너뜀")
        return

    # [확정] 로그인칸은 빈 채로 뜨고(자동완성 안 됨), 빈칸으로 doLogin()을 부르면
    #        검증에 막혀 아무 일도 안 일어난다. → ID/PW를 직접 입력한 뒤 버튼 클릭.
    #        (입력칸 id가 'userid'/'password', 버튼 onclick='doLogin()'으로 DOM 확인됨)
    uid = (driver.find_elements(By.ID, "userid")
           or driver.find_elements(By.CSS_SELECTOR,
                "input[name='userid'], input#username, input[name='username'], input[type='text']"))
    pwd = (driver.find_elements(By.ID, "password")
           or driver.find_elements(By.CSS_SELECTOR, "input[type='password']"))
    if uid and pwd:
        uid[0].clear(); uid[0].send_keys(userid)
        pwd[0].clear(); pwd[0].send_keys(password)
        print("[BofA] ID/PW 직접 입력 완료 → 'Log In' 클릭")
    else:
        print("[BofA] 입력칸을 못 찾음 → 자동완성에 의존하여 클릭")

    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", btn)

    # 로그인 전환 확인 (login/signin 둘 다 사라져야 성공)
    try:
        WebDriverWait(driver, 15).until(
            lambda d: "login" not in d.current_url.lower()
                      and "signin" not in d.current_url.lower())
        print("[BofA] 로그인 완료")
        return
    except TimeoutException:
        pass

    # 아직 로그인 페이지면: doLogin() 직접 호출 + (자동완성 비었으면) 수동 입력 후 재시도
    print("[BofA] 전환 안 됨 → 수동 입력/doLogin() 재시도")
    uid = (driver.find_elements(By.ID, "userid")
           or driver.find_elements(By.CSS_SELECTOR,
                "input[name='userid'], input#username, input[name='username'], input[type='text']"))
    pwd = (driver.find_elements(By.ID, "password")
           or driver.find_elements(By.CSS_SELECTOR, "input[type='password']"))
    if uid and pwd and not (uid[0].get_attribute("value") or "").strip():
        uid[0].clear(); uid[0].send_keys(userid)
        pwd[0].clear(); pwd[0].send_keys(password)
    try:
        els = driver.find_elements(By.XPATH, BOFA_LOGIN_BTN_XPATH)
        if els:
            driver.execute_script("arguments[0].click();", els[0])
        else:
            driver.execute_script("if (typeof doLogin === 'function') doLogin();")
    except Exception:
        pass
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: "login" not in d.current_url.lower())
    except TimeoutException:
        pass
    print("[BofA] 로그인 시도 완료")


# ============================================================
#  BofA Markets - Trending Research Reports
# ============================================================
def bofa_open_dashboard(driver, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            try:
                driver.get(BOFA_DASHBOARD)
            except TimeoutException:
                pass  # SPA가 load 이벤트를 안 끝내도 무시하고 요소 대기로 진행
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[normalize-space()='Trending Research Reports']")))
            time.sleep(3)
            return
        except TimeoutException as e:
            last_err = e
            print(f"  (BofA dashboard 로드 재시도 {attempt + 1}/{retries})")
            time.sleep(3)
    raise last_err


# Trending Research Reports 차트(Highcharts)에서 '리포트 포인트'를 직접 다룬다.
#   [중요] product 변경 후 차트가 재렌더되면 ActionChains 좌표 클릭이 Highcharts 클릭 핸들러를
#     못 건드려(리포트가 안 열림) → Highcharts API로 포인트 클릭을 '발화'해야 확실히 열린다.
def _bofa_chart_js(body):
    return ("let h2=[...document.querySelectorAll('h2')]"
            ".find(e=>e.innerText.trim()=='Trending Research Reports');"
            "if(!h2) return null;"
            "let pb=h2.closest(\"[class*='portlet-boundary']\");"
            "let chart=(Highcharts.charts||[]).find(c=>c&&c.renderTo&&pb.contains(c.renderTo));"
            "if(!chart||!chart.series[0]) return null;"
            "let pts=chart.series[0].points||chart.series[0].data;" + body)


def bofa_report_points(driver):
    """Trending Research Reports 차트의 리포트(포인트) 이름 목록을 반환."""
    res = driver.execute_script(_bofa_chart_js(
        "return pts.map(p=>p.name||p.category||'');"))
    return res or []


def bofa_fire_point(driver, idx):
    """차트의 idx번째 포인트 클릭을 Highcharts API로 '발화' → 리포트가 새 탭으로 열림.
    반환: 리포트 이름(성공) / 'ERR' / None(차트·포인트 없음)."""
    return driver.execute_script(_bofa_chart_js(
        "let p=pts[arguments[0]]; if(!p) return null;"
        "let nm=p.name||p.category||'';"
        "try{ p.firePointEvent('click'); }"
        "catch(e){ try{ p.graphic.element.dispatchEvent("
        "new MouseEvent('click',{bubbles:true})); }catch(e2){ return 'ERR'; } }"
        "return nm;"), idx)


def bofa_find_report_bars(driver):
    # (구버전 좌표 클릭용 — 현재 bofa_main은 bofa_fire_point를 쓰므로 미사용. 참고용으로 남김)
    header = driver.find_element(
        By.XPATH, "//h2[normalize-space()='Trending Research Reports']")
    portlet = header.find_element(
        By.XPATH, "./ancestor::*[contains(@class,'portlet-boundary')][1]")
    bars = portlet.find_elements(
        By.CSS_SELECTOR, "g.highcharts-series.highcharts-tracker rect")
    return bars[:BOFA_PER_SECTION]


def bofa_download_report_from_newtab(driver, out_path, timeout=40):
    # must_download=True: PDF 버튼/다운로드를 못 잡으면 빈 PDF로 넘어가지 않고 '실패'로 처리
    download_in_new_tab(driver, out_path, timeout=timeout, open_via="already", must_download=True)


def bofa_set_time_24h(driver, wait=18):
    """[미사용] TIME 슬라이더를 '24 hrs'로 드래그 시도.
    현재 크롬/셀레니움 조합에서 jQuery UI 슬라이더의 '프로그램 드래그'가 먹지 않아(1 hr에서 안 움직임)
    bofa_main에서는 호출하지 않는다. (기본 시간창 그대로 사용) — 참고용으로만 남겨둠."""
    try:
        h2 = driver.find_element(
            By.XPATH, "//h2[normalize-space()='Trending Research Reports']")
        portlet = h2.find_element(
            By.XPATH, "./ancestor::*[contains(@class,'portlet-boundary')][1]")
        sel = portlet.find_element(By.CSS_SELECTOR, "select[id*='timeSlider']")
        if sel.get_attribute("value") == "24 hrs":
            return
        handle = portlet.find_element(
            By.CSS_SELECTOR, ".ui-slider-handle, .ui-slider a, [class*='slider-handle']")
        label = portlet.find_element(
            By.XPATH, ".//span[contains(@class,'ui-slider-label') and normalize-space()='24 hrs']")
        ActionChains(driver).click_and_hold(handle).pause(0.4).move_to_element(
            label).pause(0.4).release().perform()
        time.sleep(wait)
        print(f"  TIME -> {sel.get_attribute('value')}")
    except Exception as e:
        print(f"  (TIME 24h 설정 실패 → 기본값 사용: {repr(e)[:80]})")


def bofa_set_products(driver, wanted=BOFA_PRODUCTS, wait=18):
    """Trending Research Reports의 product 멀티셀렉트(jQuery multiple-select)를
    원하는 항목만 남기도록 설정하고 차트 재조회를 기다린다.
    - 네이티브 select가 아니라 .ms-parent 위젯이므로 실제 클릭으로 조작.
    - 인스턴스 ID가 동적이라 id$='_productpref' 접미사로 잡는다."""
    h2 = driver.find_element(
        By.XPATH, "//h2[normalize-space()='Trending Research Reports']")
    portlet = h2.find_element(
        By.XPATH, "./ancestor::*[contains(@class,'portlet-boundary')][1]")

    sel = portlet.find_element(By.CSS_SELECTOR, "select[id$='_productpref']")
    ms_parent = portlet.find_element(
        By.XPATH, ".//select[contains(@id,'_productpref')]"
                  "/following-sibling::div[contains(@class,'ms-parent')][1]")

    # 1) 드롭다운 열기 (.ms-choice 클릭 → .ms-drop 표시)
    choice = ms_parent.find_element(By.CSS_SELECTOR, ".ms-choice")
    driver.execute_script("arguments[0].click();", choice)
    drop = WebDriverWait(driver, 10).until(
        lambda d: ms_parent.find_element(By.CSS_SELECTOR, ".ms-drop"))
    time.sleep(0.4)

    # 2) [Select all] 먼저 해제(전부 체크 해제) → 깔끔하게 초기화
    try:
        sa = drop.find_element(
            By.CSS_SELECTOR, "li.ms-select-all input[type='checkbox']")
        if sa.is_selected():
            driver.execute_script("arguments[0].click();", sa)
            time.sleep(0.3)
    except Exception:
        pass  # select-all 없으면 개별 해제로 진행

    # 3) 원하는 항목만 체크
    boxes = drop.find_elements(
        By.CSS_SELECTOR, "li:not(.ms-select-all) input[type='checkbox'][value]")
    for cb in boxes:
        val = cb.get_attribute("value")
        should = val in wanted
        if cb.is_selected() != should:
            driver.execute_script("arguments[0].click();", cb)
            time.sleep(0.15)

    # 4) 드롭다운 닫고, 원본 select에 change 강제 발생 → 차트 재조회 트리거
    driver.execute_script("arguments[0].click();", choice)  # 닫기
    driver.execute_script("""
        var s = arguments[0];
        s.dispatchEvent(new Event('change', {bubbles:true}));
        if (window.jQuery) jQuery(s).trigger('change');
    """, sel)

    time.sleep(wait)  # 차트 재조회 로딩 대기
    picked = [o.get_attribute("value")
              for o in sel.find_elements(By.CSS_SELECTOR, "option")
              if o.is_selected()]
    print(f"  PRODUCT -> {picked}")


def bofa_main(driver):
    print("\n=== BofA | Trending Research Reports ===")
    bofa_login(driver)            # ← 대시보드 열기 전에 먼저 로그인
    bofa_open_dashboard(driver)
    total = 0

    # product 순회 없이: 차트 기본 선택(전체 product) 상태에서 Trending 상위 BOFA_TOTAL(20)개를 한 번에.
    # ※ TIME(시간창)은 자동 드래그가 안 먹어서 설정 생략 → 사이트 기본값(1 hr) 그대로 사용.
    try:
        names = bofa_report_points(driver)
    except Exception as e:
        print(f"  (리포트 목록 조회 실패: {repr(e)[:80]})")
        names = []
    n = len(names)
    print(f"  리포트 {n}개 (상위 {BOFA_TOTAL}개 받기)")

    for i in range(min(n, BOFA_TOTAL)):
        name = names[i] or f"report_{i+1}"
        out = os.path.join(
            DOWNLOAD_DIR, safe_name(name, i + 1, "BofA", "now"))
        try:
            # ★ Highcharts API로 포인트 클릭 발화 → 리포트가 새 탭으로 열림
            fired = bofa_fire_point(driver, i)
            if fired in (None, "ERR"):
                raise RuntimeError("포인트 클릭 발화 실패(차트/포인트 없음)")
            bofa_download_report_from_newtab(driver, out)
            total += 1
            print(f"  [{i+1:02d}] 성공  {os.path.getsize(out)//1024} KB  {name[:50]}")
        except Exception as e:
            print(f"  [{i+1:02d}] 실패  {name[:50]}  -> {e}")
            # 남은 새 탭/뷰어 정리 후 대시보드 탭으로 복귀
            if len(driver.window_handles) > 1:
                m = driver.window_handles[0]
                for h in driver.window_handles[1:]:
                    driver.switch_to.window(h); driver.close()
                driver.switch_to.window(m)
        time.sleep(1)

    print(f"  BofA 완료: 총 {total}개")
    return total


# ============================================================
#  JPMM (J.P. Morgan Markets) - Research 폴더, 3d ago 이내
# ============================================================
# [확정된 사실 - 화면/HTML로 확인됨]
#  1) 목록 진입: https://markets.jpmorgan.com/mcp-home/ 로 직접 접근 가능
#     (location.href 콘솔 확인 완료). iframe 전환은 보조용 폴백으로만 둠.
#  2) 시간 표기: "1d ago", "3d ago" 형식. 한 줄 구조 = "제목 | 작성자\nNd ago".
#  3) 리포트 행 클릭 → 같은 화면이 article_page 뷰어로 바뀜
#     (iframe id="mcp-app-view-research.article_page").
#  4) 뷰어 안에 PDF 버튼 존재:
#       <a href="/research/ArticleServlet?doc=GPS-XXXXXXX-0.pdf"
#          class="toolbar-button research-doc" data-doc-id="...">PDF</a>
#     → 이 href가 PDF 파일의 '직접 주소'. 절대 URL로 바꿔 새 탭에서 받으면
#       Chrome 내장 뷰어의 shadow-DOM 다운로드 버튼을 건드릴 필요가 없음.

def parse_relative_age_days(text):
    """'3d ago'->3, '1h ago'/'now'->0, '1w ago'->7, '2mo ago'->60 ... 형식 아니면 None."""
    t = (text or "").strip().lower()
    if t in ("now", "today", "just now"):
        return 0
    m = re.search(r"(\d+)\s*(mo|mon|month|min|sec|hr|hour|wk|week|day|yr|year|[smhdwy])\s*ago", t)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    # 긴 키부터 매칭 (mo가 m보다 먼저 잡히도록)
    table = [("mo", 30), ("mon", 30), ("month", 30), ("yr", 365), ("year", 365),
             ("wk", 7), ("week", 7), ("day", 1), ("hour", 0), ("hr", 0),
             ("min", 0), ("sec", 0), ("y", 365), ("w", 7), ("d", 1),
             ("h", 0), ("m", 0), ("s", 0)]
    for key, mult in sorted(table, key=lambda kv: len(kv[0]), reverse=True):
        if unit.startswith(key):
            return n * mult
    return None


def _jpmm_research_present(driver, timeout=8):
    """현재 컨텍스트(기본 or iframe 내부)에 Research 카드가 보이는지 확인."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[normalize-space()='Research']")))
        return True
    except TimeoutException:
        return False


def jpmm_enter_app(driver, max_login_wait_loops=3):
    """
    Research가 보이는 컨텍스트로 진입.
    반환값: 'direct'(내부 URL 직접) | 'iframe'(iframe 전환). 실패 시 RuntimeError.
    로그인 안 돼 있으면 input()으로 수동 로그인을 기다린 뒤 재시도.
    """
    for attempt in range(max_login_wait_loops + 1):
        # 1) 내부 앱 URL로 직접 진입
        driver.switch_to.default_content()
        try:
            driver.get(JPMM_IFRAME_URL)
            if _jpmm_research_present(driver, 15):
                print("[JPMM] 내부 앱 URL 직접 진입 성공")
                return "direct"
        except Exception:
            pass

        # 2) 메인 진입 후 iframe 전환
        driver.switch_to.default_content()
        try:
            driver.get(JPMM_HOME)
            iframe = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "iframe#mcp-app-view-mcphomepage")))
            driver.switch_to.frame(iframe)
            if _jpmm_research_present(driver, 15):
                print("[JPMM] iframe 전환 진입 성공")
                return "iframe"
        except TimeoutException:
            pass
        driver.switch_to.default_content()

        if attempt < max_login_wait_loops:
            print("\n[JPMM] Research 화면 미감지 → 로딩 대기 후 재시도(필요 시 브라우저에서 로그인).")
            try:
                input("       준비되면 Enter ▶ (비대화형이면 자동 대기) ")
            except EOFError:
                time.sleep(8)   # 백그라운드 실행(stdin 없음): EOF에 죽지 말고 더 기다렸다 재시도

    raise RuntimeError("JPMM Research 화면을 찾지 못했습니다 (로그인/셀렉터 확인 필요)")


def jpmm_collect_research(driver, max_age_days=JPMM_MAX_AGE_DAYS, max_items=JPMM_MAX_ITEMS):
    """
    Research 카드에서 (age_days <= max_age_days)인 항목을 수집.
    [확정] 목록 행 제목 = a[data-testid="card-title-link"], href에 doc ID 포함:
           https://jpmorganmarkets.com/research/content/GPS-5332387-0
           → doc ID(GPS-5332387-0)만 뽑으면 PDF 직접 주소를 조립할 수 있음.
    [확정] 시간 표기 = "Nd ago" (같은 행 컨테이너 안에 위치).
    반환: [(title, doc_id, age_days), ...]
    """
    # [수정] 'Research' 헤더에서 컨테이너를 거슬러 찾던 방식이 카드를 못 감싸 0개가 나오던 문제
    #        → 페이지 전체의 카드 제목 링크를 직접 조회하도록 단순화 (점검 결과 50개 존재 확인)
    items, seen = [], set()
    links = driver.find_elements(
        By.CSS_SELECTOR, "a[data-testid='card-title-link'], div[data-testid='card-title'] a")
    for a in links:
        try:
            href = a.get_attribute("href") or ""
            m = re.search(r"/content/([A-Za-z0-9\-]+)", href)
            if not m:
                continue
            doc_id = m.group(1)
            if doc_id in seen:
                continue

            # 같은 행 컨테이너로 올라가 'Nd ago'를 찾되, 'ago'가 1개뿐인(=한 카드) 컨테이너만 인정.
            # (여러 카드가 합쳐진 상위 컨테이너로 과대 상승해 엉뚱한 0d로 잡히던 문제 방지)
            row, age_text = a, ""
            for _ in range(6):
                row = row.find_element(By.XPATH, "..")
                low = (row.text or "").lower()
                if re.search(r"\bago\b", low):
                    if len(re.findall(r"\bago\b", low)) == 1:
                        age_text = row.text
                    break
            days = None
            for tok_line in age_text.split("\n"):
                d = parse_relative_age_days(tok_line)
                if d is not None:
                    days = d
                    break
            if days is None or days > max_age_days:
                continue

            title = (a.text.strip() or "report")
            seen.add(doc_id)
            items.append((title, doc_id, days))
            if len(items) >= max_items:
                break
        except Exception:
            continue  # 동적 렌더링으로 stale 된 요소 등은 건너뜀
    return items


def jpmm_main(driver):
    print("\n=== JPMM | Research (3d ago 이내) ===")
    jpmm_enter_app(driver)
    # 카드가 비동기로 늦게 뜨므로 대기
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[data-testid='card-title-link']")))
    except TimeoutException:
        pass
    total = 0

    items = jpmm_collect_research(driver)
    print(f"  3일 이내 Research {len(items)}개 수집")

    for i, (title, doc_id, days) in enumerate(items, 1):
        out = os.path.join(DOWNLOAD_DIR, safe_name(title, i, "JPMM_Research", f"{days}d"))
        # [확정] PDF 직접 주소: ArticleServlet?doc=<docid>.pdf
        #   (article_page 뷰어를 거치지 않으므로 무거운 React 로딩이 없어 빠름)
        pdf_url = f"https://markets.jpmorgan.com/research/ArticleServlet?doc={doc_id}.pdf"
        try:
            download_in_new_tab(driver, out, href=pdf_url)
            total += 1
            print(f"  [{i:02d}] 성공  {days}d  {os.path.getsize(out)//1024} KB  {title[:50]}")
        except Exception as e:
            print(f"  [{i:02d}] 실패  {title[:50]}  -> {e}")
            driver.switch_to.default_content()
        time.sleep(1)

    driver.switch_to.default_content()
    print(f"  JPMM 완료: {total}개")
    return total


# ============================================================
#  HSBC Global Investment Research
# ============================================================
_MONTHS = {m: i for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}


def parse_hsbc_date(token):
    """'12-Jun-26' -> date(2026, 6, 12). 형식 아니면 None."""
    try:
        d, mon, y = token.strip().split("-")
        return date(2000 + int(y), _MONTHS[mon[:3].title()], int(d))
    except Exception:
        return None


def hsbc_download(driver, href, out_path, wait=PDF_WAIT_MAX):
    """HSBC 전용 다운로드.
    [문제] HSBC 리포트 링크는 새 탭을 열면 곧바로 PDF 다운로드가 시작되고 그 탭이 즉시 닫힌다.
      → 공통 download_in_new_tab은 그 탭으로 switch 하려다 'no such window'로 실패한다.
    [해결] 탭 상태에 의존하지 않고 '다운로드 폴더(BROWSER_DL_DIR)'만 감시한다.
      (탭이 안 닫히고 PDF 뷰어/HTML로 남는 경우엔 fetch/printToPDF 폴백으로 처리)
    """
    before = set(os.listdir(BROWSER_DL_DIR))
    main = driver.current_window_handle
    handles_before = set(driver.window_handles)
    driver.execute_script("window.open(arguments[0], '_blank');", href)

    deadline = time.time() + wait
    try:
        while time.time() < deadline:
            # (C) 다운로드 폴더에 새 PDF가 떨어졌나 (탭이 닫혔어도 동작)
            fname = wait_new_pdf(before, timeout=1)
            if fname:
                os.replace(os.path.join(BROWSER_DL_DIR, fname), out_path)
                return

            # 아직 살아있는 새 탭이 PDF 뷰어면 fetch로 저장 (직링크가 뷰어로 열리는 경우)
            for h in [w for w in driver.window_handles if w not in handles_before]:
                try:
                    driver.switch_to.window(h)
                    if looks_like_pdf_viewer(driver):
                        download_current_pdf_via_fetch(driver, out_path, timeout=wait)
                        return
                except Exception:
                    pass
            time.sleep(1)

        # 시간 초과: 살아있는 탭이 HTML로 남아 있으면 통째 렌더(printToPDF) 폴백
        alive = [w for w in driver.window_handles if w not in handles_before]
        if alive:
            try:
                driver.switch_to.window(alive[-1])
                result = driver.execute_cdp_cmd("Page.printToPDF", {
                    "printBackground": True, "preferCSSPageSize": True})
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(result["data"]))
                return
            except Exception:
                pass
        raise RuntimeError(f"PDF가 {wait}초 안에 안 떨어짐")
    finally:
        # main(원래 탭) 외의 새 탭을 모두 정리 후 원래 탭 복귀
        for h in list(driver.window_handles):
            if h != main:
                try:
                    driver.switch_to.window(h); driver.close()
                except Exception:
                    pass
        try:
            driver.switch_to.window(main)
        except Exception:
            pass


def hsbc_login(driver, timeout=15):
    driver.get(HSBC_HOME)
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "dayReports")))
        print("[HSBC] 로그인된 세션 감지 → 로그인 단계 건너뜀")
        return
    except TimeoutException:
        pass
    print("\n[HSBC] 열린 브라우저에서 직접 로그인해 주세요.")
    try:
        input("       로그인 완료 후 Enter ▶ ")
    except EOFError:
        time.sleep(8)   # 백그라운드(stdin 없음): EOF에 죽지 말고 대기 후 진행
    driver.get(HSBC_HOME)
    WebDriverWait(driver, 45).until(
        EC.presence_of_element_located((By.ID, "dayReports")))


def hsbc_collect_most_read_day(driver):
    items, seen = [], set()
    rows = driver.find_elements(
        By.CSS_SELECTOR, "#dayReports ul.mostReadList li.mostReadItem")
    for li in rows:
        report_a = None
        for a in li.find_elements(By.TAG_NAME, "a"):
            title = (a.get_attribute("title") or "").strip().lower()
            if title.startswith("click to see the video"):
                continue
            report_a = a
            break
        if report_a is None:
            continue
        href = report_a.get_attribute("href")
        name = report_a.text.strip() or report_a.get_attribute("title") or "report"
        if not href or href in seen:
            continue
        seen.add(href)
        items.append((href, name))
        if len(items) >= HSBC_PER_SECTION:
            break
    return items


def hsbc_collect_house_views(driver, since_days=1):
    today = date.today()
    start = today - timedelta(days=since_days)
    items, seen = [], set()
    for div in driver.find_elements(
            By.CSS_SELECTOR, "#outlooksReports div.periodicalGroupItem"):
        links = div.find_elements(By.TAG_NAME, "a")
        if not links:
            continue
        a = links[0]
        href = a.get_attribute("href")
        if not href or "javascript" in href.lower() or href in seen:
            continue
        name = a.text.strip() or a.get_attribute("title") or "report"
        dt = next((parse_hsbc_date(t)
                   for t in div.text.replace("\n", " ").split()
                   if parse_hsbc_date(t)), None)
        if dt is None:
            continue
        if start <= dt <= today:
            seen.add(href)
            items.append((href, name, dt))
    return items


def hsbc_main(driver):
    print("\n=== HSBC | Most Read (Day) + House Views ===")
    hsbc_login(driver)
    # Most Read 목록이 비동기로 늦게 채워지므로 항목이 실제로 뜰 때까지 대기
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#dayReports li.mostReadItem")))
    except TimeoutException:
        pass
    total = 0

    day_items = hsbc_collect_most_read_day(driver)
    print(f"  [Most Read-Day] {len(day_items)}개 수집")
    for i, (href, name) in enumerate(day_items, 1):
        out = os.path.join(DOWNLOAD_DIR, safe_name(name, i, "HSBC_MostRead", "day"))
        try:
            hsbc_download(driver, href, out)   # ← 탭이 닫혀도 폴더 감시로 받는 전용 다운로더
            total += 1
            print(f"  [Day {i:02d}] 성공  {os.path.getsize(out)//1024} KB  {name[:50]}")
        except Exception as e:
            print(f"  [Day {i:02d}] 실패  {name[:50]}  -> {e}")
        time.sleep(1)

    driver.get(HSBC_HOME)
    WebDriverWait(driver, 45).until(
        EC.presence_of_element_located((By.ID, "outlooksReports")))
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#outlooksReports div.periodicalGroupItem")))
    except TimeoutException:
        pass
    hv_items = hsbc_collect_house_views(driver, since_days=1)
    print(f"  [House Views] 어제~오늘 업데이트 {len(hv_items)}개")
    for i, (href, name, dt) in enumerate(hv_items, 1):
        out = os.path.join(
            DOWNLOAD_DIR, safe_name(name, i, "HSBC_HouseViews", dt.strftime("%y%m%d")))
        try:
            hsbc_download(driver, href, out)   # ← 동일 전용 다운로더 사용
            total += 1
            print(f"  [HV {i:02d}] 성공  {dt}  {name[:40]}")
        except Exception as e:
            print(f"  [HV {i:02d}] 실패  {name[:40]}  -> {e}")
        time.sleep(1)

    print(f"  HSBC 완료: {total}개")
    return total


# ============================================================
#  실행
# ============================================================
def run_site(name, fn, driver):
    """한 사이트에서 에러가 나도 전체가 멈추지 않도록 격리 실행."""
    try:
        return fn(driver)
    except Exception as e:
        print(f"\n[!] {name} 단계 실패 → 건너뜀: {repr(e)[:200]}")
        # 남은 새 탭/창 정리 후 메인 창으로 복귀
        try:
            driver.switch_to.default_content()
            if len(driver.window_handles) > 1:
                main_h = driver.window_handles[0]
                for h in driver.window_handles[1:]:
                    driver.switch_to.window(h); driver.close()
                driver.switch_to.window(main_h)
        except Exception:
            pass
        return 0


def main():
    driver = make_driver()
    try:
        marquee_total = run_site("Marquee", marquee_main, driver)   # 1) Marquee (+ Portfolio Strategy)
        bofa_total    = run_site("BofA", bofa_main, driver)         # 2) BofA
        jpmm_total    = run_site("JPMM", jpmm_main, driver)         # 3) JPMM
        hsbc_total    = run_site("HSBC", hsbc_main, driver)         # 4) HSBC
        grand = marquee_total + bofa_total + hsbc_total + jpmm_total
        print(f"\n전체 완료: Marquee {marquee_total} + BofA {bofa_total} "
              f"+ HSBC {hsbc_total} + JPMM {jpmm_total} = {grand}개 → {DOWNLOAD_DIR}")
    finally:
        # 붙기 모드: quit()은 연결된 창을 닫으므로 호출하지 않음 (브라우저 유지)
        pass


if __name__ == "__main__":
    main()
