# -*- coding: utf-8 -*-
"""
리서치 리포트 통합 다운로더 (Marquee + BofA + HSBC + JPMM + UBS)
[Marquee/GS] 4개 섹션 × (1d) × 10개 = 최대 40개  + Portfolio Strategy 5개
[BofA]       Trending Research Reports 상위 10개
[HSBC]       Most Read(Day) 10개 + House Views(어제~오늘)
[JPMM/JPM]   Research 폴더 중 "3d ago" 이내(3일 이하)만
전제: 'C:\\selenium_profile' 전용 프로필을 사용. 첫 실행 때 각 사이트에 1회만
      수동 로그인하면, 이후로는 세션이 저장돼 로그인 상태가 계속 유지됩니다.
      (평소 쓰는 크롬과 별개라 충돌 없고, 크롬을 종료할 필요도 없음)
필요 패키지: pip install selenium
"""
import os
import re
import sys
import time
import json
import base64
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ============================================================
#  계정정보 (.env)
# ============================================================
# 계정/비밀번호는 코드가 아니라 이 스크립트와 같은 폴더의 .env 에 둔다.
#   BOFA_USERID / BOFA_PASSWORD / UBS_EMAIL / UBS_PASSWORD
# python-dotenv 가 없는 파이썬으로 실행돼도 돌아가도록 간단 파서를 폴백으로 둔다.
# (이미 환경변수로 들어와 있으면 그쪽이 우선 — dotenv 기본 동작과 동일)
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

def load_env(path=ENV_PATH):
    try:
        from dotenv import load_dotenv
        load_dotenv(path)
        return
    except ImportError:
        pass
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        print(f"[env] {path} 없음 → 자동 로그인 불가(저장된 세션에만 의존)")

load_env()

# ============================================================
#  공통 설정
# ============================================================
BASE = "https://marquee.gs.com"
TRENDING_URL = f"{BASE}/content/site/trending.html"
DOWNLOAD_DIR = os.path.join(r"C:\Users\infomax\Desktop\보따리", datetime.now().strftime("%y%m%d"))
PER_SECTION = 10                 # Marquee: 한 시간 탭당 받을 개수
TIMEFRAMES = ["1d"]              # Marquee: 1d만 순회
# 리포트 1건당 PDF가 뜨기를 기다리는 최대 시간(초). PDF 버튼/뷰어가 랜덤하게 늦게 뜨는 경우 대비.
PDF_WAIT_MAX = 120               # ← 2분
# 로그인 유지용 전용 프로필 폴더 (없으면 자동 생성됨)
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
# UBS Neo: 왼쪽 탭 3개가 각각 별도 URL. 각 페이지 맨 아래 'All ~ Research' 패널이 목록(최신순).
UBS_SECTIONS = {
    "UBS_MacroStrategy":  "https://neo.ubs.com/macrostrategy",
    "UBS_EquityStrategy": "https://neo.ubs.com/macrostrategyequity",
    "UBS_Economics":      "https://neo.ubs.com/economics",
}
UBS_PER_SECTION  = 10            # 섹션당 받을 최대 개수
UBS_MAX_AGE_DAYS = 2             # 주말/공휴일 끼면 1일로는 놓쳐서 2일. 중복은 파일명의 리포트 날짜로 구분됨
UBS_LOGIN_URL = "https://neo.ubs.com/static/login.html?origin=%2fmacrostrategy"
UBS_EMAIL     = os.environ.get("UBS_EMAIL", "")      # ← .env
UBS_PASSWORD  = os.environ.get("UBS_PASSWORD", "")   # ← .env
# Citi Velocity: Content Feeds > Trending 탭. 목록/리포트 모두 iframe#Main 안에서 렌더된다.
CITI_HOME        = "https://www.citivelocity.com/cv2/go/Content_Feeds"
CITI_PER_SECTION = 20            # Trending 상위 N개 (비디오 제외 후 기준)
CITI_PDF_WAIT    = 60            # 리포트 1건당 PDF 대기 최대(초)
CITI_LOGIN_URL = "https://www.citivelocity.com/login/"
CITI_USERNAME  = os.environ.get("CITI_USERNAME", "")   # ← .env (예: jkim7701)
CITI_PASSWORD  = os.environ.get("CITI_PASSWORD", "")   # ← .env
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

def err1(e, limit=120):
    """
    예외를 '한 줄'로 압축한다.
    셀레니움 예외는 str(e)에 chromedriver Stacktrace 20여 줄이 통째로 붙어서,
    실패 1건마다 로그가 20줄씩 불어난다. 그래서 Stacktrace를 잘라내고
    예외 타입 + 메시지 첫 줄만 남긴다.
    """
    msg = str(e).split("Stacktrace:")[0]
    msg = re.sub(r"^(?:\s*Message:\s*)+", "", msg)      # 셀레니움 'Message: ' 머리말 제거
    msg = re.sub(r"\s+", " ", msg).strip()
    if msg in ("", "None"):                            # TimeoutException() 처럼 메시지가 없는 경우
        return type(e).__name__
    return f"{type(e).__name__}: {msg}"[:limit]

def wait_manual(prompt):
    """사람이 보고 있을 때만 Enter 를 기다린다. 무인 실행이면 즉시 넘어간다.

    [2026-08-19 실측] 작업 스케줄러로 돌 때 stdin 은 EOF 가 아니라 '아무것도 안 오는' 상태다.
      그래서 input() 이 EOFError 를 던지지 않고 **영원히 멈춘다.** 실제로 08:00 실행이
      1시간 50분째 여기 매달려 있었고, 그 프로세스가 로그 파일을 붙잡고 있어서
      그 뒤 수동 실행까지 전부 '>> 로그' 리다이렉트 실패로 **python 이 아예 안 떴다.**
      로그가 안 남으니 "셀레니움이 고장났다"로 보일 뿐 원인을 찾을 수가 없다.
    → 사람이 있을 때(isatty)만 묻고, 무인 실행이면 그 사이트만 포기하고 다음으로 넘어간다.
    반환: 사람이 Enter 를 눌렀으면 True, 무인이라 건너뛰었으면 False.
    """
    try:
        interactive = bool(sys.stdin) and sys.stdin.isatty()
    except Exception:
        interactive = False
    if not interactive:
        print("       (무인 실행 → 수동 로그인 단계 건너뜀)")
        return False
    try:
        input(prompt)
        return True
    except (EOFError, RuntimeError):
        return False

def ensure_debug_tab(timeout=60):
    """9222 에 '붙을 수 있는 페이지 탭'이 생길 때까지 기다린다. 포트만 살아있고 탭이 없으면 하나 만든다.

    [2026-08-19 실측] 포트는 열려 있는데 쓸 수 있는 탭이 없는 상태가 존재한다
      (전날 실행이 남긴 크롬이 창을 다 닫은 경우 등). 그 상태로 붙으면 첫 driver.get 부터
      NoSuchWindowException: target window already closed 가 터지고 5개 사이트가 전멸한다.
      2026-08-13 / 08-19 아침 실행이 정확히 이 증상이었다.
    또한 bat 의 고정 5초 대기로는 크롬이 덜 떴을 때 연결 실패가 나므로 여기서 함께 기다린다.
    """
    import urllib.request
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=3) as r:
                targets = json.load(r)
            pages = [t for t in targets
                     if t.get("type") == "page"
                     and not (t.get("url") or "").startswith("chrome-extension://")]
            if pages:
                return True
            # 포트는 살아있는데 탭이 없다 → 빈 탭을 하나 만든다 (Chrome 111+ 는 PUT)
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:9222/json/new?about:blank", method="PUT")
                urllib.request.urlopen(req, timeout=5).close()
            except Exception:
                pass
        except Exception:
            pass                       # 아직 크롬이 안 떴다 → 계속 기다림
        time.sleep(2)
    return False

def make_driver():
    if not ensure_debug_tab():
        raise RuntimeError(
            "[연결 실패] 9222 포트에 붙을 수 있는 크롬 탭이 60초 안에 안 생김 → 바탕화면 "
            "'크롬_연동.bat'으로 Chrome 을 켜고 로그인한 뒤 다시 실행하세요.")
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
            % err1(e, 100))
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

def findpdf_clickable(driver):
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
                el = findpdf_clickable(driver)
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
    for h in driver.find_elements(By.CSS_SELECTOR, "div#content-card-header"):
        if h.text.strip().lower().startswith(title.lower()):
            return h.find_element(By.XPATH, "..")
    raise RuntimeError(f"섹션을 못 찾음: {title}")

def select_timeframe(driver, card, label):
    # Marquee 페이지 양식 변경(2026-07): a.nav-link -> a[role='tab'] / gs-uitk-nav__link
    for a in card.find_elements(By.CSS_SELECTOR, "a[role='tab'], a.gs-uitk-nav__link"):
        if a.text.strip() == label:
            if "active" not in (a.get_attribute("class") or ""):   # 'gs-uitk-nav__link--active' 도 포함 매칭
                driver.execute_script("arguments[0].click();", a)
                time.sleep(2)
            return True
    return False

def collect_links(card, css, limit=PER_SECTION):
    items, seen = [], set()
    for a in card.find_elements(By.CSS_SELECTOR, css):
        href = a.get_attribute("href")
        if not href or href.endswith("#") or href in seen:
            continue
        seen.add(href)
        items.append((href, a.text.strip()))
        if len(items) >= limit:
            break
    return items

def download_research(driver, href, out_path):
    driver.get(href)
    pdf_link = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//a[normalize-space()='PDF']")))
    before = set(os.listdir(BROWSER_DL_DIR))
    driver.execute_script("arguments[0].click();", pdf_link)
    fname = wait_new_pdf(before)
    if not fname:
        raise RuntimeError("PDF 다운로드 대기 시간 초과")
    os.replace(os.path.join(BROWSER_DL_DIR, fname), out_path)

def download_beyond(driver, href, out_path):
    driver.get(href)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='PDF']")))
    time.sleep(2)
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
            print(f"  [1d {i:02d}] 실패  {name[:50]}  -> {err1(e)}")
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
            card = find_card(driver, title)
            if not select_timeframe(driver, card, tf):
                print(f"  ('{tf}' 탭 없음 → 건너뜀)")
                continue
            card = find_card(driver, title)
            items = collect_links(card, css)
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
                    print(f"  [{tf} {i:02d}] 실패  {name[:50]}  -> {err1(e)}")
                time.sleep(1)
            open_trending(driver)
    # 4개 섹션 끝난 뒤 Portfolio Strategy Research 5개를 이어서 받는다.
    open_trending(driver)
    try:
        total += marquee_portfolio_strategy(driver)
    except Exception as e:
        print(f"  ({PORTFOLIO_TITLE} 건너뜀: {err1(e, 80)})")
    print(f"\nMarquee 완료: 총 {total}개")
    return total

# ============================================================
#  BofA Markets - Login
# ============================================================
# 전용 프로필 세션이 풀리면 대시보드 URL이 로그인 페이지로 바뀌어 계속 타임아웃 남.
# → 매 실행 시 자동 로그인 시도. (이미 로그인돼 있으면 로그인 버튼이 없으므로 자동 건너뜀)
BOFA_LOGIN_URL = BOFA_DASHBOARD   # 미로그인 시 이 URL이 로그인 폼으로 리다이렉트됨
BOFA_USERID    = os.environ.get("BOFA_USERID", "")    # ← .env (자동완성 실패 시에만 사용)
BOFA_PASSWORD  = os.environ.get("BOFA_PASSWORD", "")  # ← .env
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
#  [구버전/미사용] BofA - Trending Research Reports (Highcharts 차트 클릭 방식)
# ============================================================
# 2026-08-11부터 BofA는 아래 '섹터별 목록' 방식으로 대체됐다. 이 블록의 함수들
# (bofa_open_dashboard / _bofa_chart_js / bofa_report_points / bofa_fire_point /
#  bofa_find_report_bars / bofa_download_report_from_newtab / bofa_set_time_24h /
#  bofa_set_products)은 어디서도 호출되지 않는다.
# 지우지 않고 남기는 이유: 'Highcharts는 좌표 클릭이 안 먹어 firePointEvent 발화가
# 필요하다', 'TIME 슬라이더는 프로그램 드래그가 안 먹는다' 같은 시행착오 기록이라
# 차트 방식으로 되돌릴 일이 생기면 다시 쓴다.

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
        print(f"  (TIME 24h 설정 실패 → 기본값 사용: {err1(e, 80)})")

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

# ============================================================
#  BofA Global Research - 섹터별 / ET 기준 '어제' 발행분
# ============================================================
# [다운로드 규칙]
#   Inv Strategy / Rates & FX / Economics : 어제치 전부
#   Credit                                : 어제치 중 제목이 'Situation Room' 인 것만
#   Commodities                           : 어제치 중 'Global Energy Weekly' / 'Metals Weekly'
#
# ※ 공통 헬퍼(err1 / wait_new_pdf / looks_like_pdf_viewer /
#   download_current_pdf_via_fetch / findpdf_clickable / PDF_ANCHOR_CSS /
#   PDF_BTN_XPATH / _MONTHS)는 이 파일 위쪽 것을 그대로 쓴다.
#   파일명 규칙만 BofA가 달라서(타임프레임 없음) bofa_safe_name 을 따로 둔다.

# [미사용] BofA 발행 날짜는 미국 동부시간(ET) 기준이라 '어제'를 계산할 때 썼으나,
# 2026-08-13부터 목록의 실제 최신 발행일을 쓰므로 더는 시간대 계산을 하지 않는다.
US_TZ = ZoneInfo("America/New_York")

BOFA_BASE    = "https://markets.ml.com/researchlibrary/macro-research"
BOFA_PORTLET = "multiDataReports_WAR_researchlibrary_portlet_INSTANCE_RlfzZF2lLxaA"
BOFA_P       = f"_{BOFA_PORTLET}_"           # URL 파라미터 접두사

# 섹터별 규칙: island(내부명) + title_filter(None이면 전부)
BOFA_SECTIONS = [
    # (라벨,          tabname,        island,                title_filter)
    ("Inv_Strategy",  "Inv Strategy", "Investment Strategy", None),
    ("Rates_FX",      "Rates & FX",   "Rates & FX",          None),
    ("Economics",     "Economics",    "Economics",           None),
    ("Credit",        "Credit",       "Credit",
        lambda t: "situation room" in t.lower()),
    ("Commodities",   "Commodities",  "Commodities",
        lambda t: ("global energy weekly" in t.lower()
                   or "metals weekly" in t.lower())),
]

# 목록의 최신 발행일부터 '서로 다른 날짜' 몇 개를 받을지. (달력일이 아니라 목록에 있는 날짜)
# 2 = 최신일 + 그 직전 발행일. 1로 두면 그날 늦게 올라온 리포트를 놓친다(bofa_run_section 주석 참고).
BOFA_RECENT_DAYS = 2

def parse_bofa_date(text):
    """'10-Aug-2026 08:58:30 PM' -> date(2026, 8, 10). 형식 아니면 None."""
    m = re.search(r"(\d{2})-([A-Za-z]{3})-(\d{4})", text or "")
    if not m:
        return None
    d, mon, y = m.group(1), m.group(2).title(), m.group(3)
    if mon not in _MONTHS:
        return None
    return date(int(y), _MONTHS[mon], int(d))

def bofa_safe_name(text, idx, section, tf=""):
    """BofA 파일명. tf 자리에 '리포트 발행일'(YYMMDD)을 넣는다.

    [2026-08-13] 최신 N일치를 받게 되면서 같은 리포트가 이틀 연속 잡힐 수 있어졌다.
      날짜별 폴더가 달라 덮어쓰기는 안 나지만, 파일명만 보고는 중복인지 알 수 없어
      UBS와 같은 규칙(섹션_리포트날짜_번호_제목)으로 맞췄다.
    """
    text = "".join(c if c.isalnum() or c in " -_" else "_"
                   for c in (text or ""))[:70].strip()
    mid = f"{tf}_" if tf else ""
    return f"{section}_{mid}{idx:02d}_{text or 'report'}.pdf"

def bofa_section_url(tabname, island, pagesize=100, pageidx=1):
    from urllib.parse import quote
    return (f"{BOFA_BASE}?p_p_id={BOFA_PORTLET}&p_p_lifecycle=0&p_p_state=maximized"
            f"&p_p_mode=view"
            f"&{BOFA_P}pageidx={pageidx}&{BOFA_P}pagesize={pagesize}&{BOFA_P}action=more"
            f"&{BOFA_P}tabname={quote(tabname)}&{BOFA_P}island={quote(island)}")

# 목록 행에서 (report_id, 제목, 발행일) 을 뽑아내는 JS.
# - 제목/부제 셀이 같은 id를 공유하므로 id로 dedup
# - 날짜는 같은 행(tr) 안의 'dd-Mon-yyyy ...' 텍스트
_BOFA_COLLECT_JS = r"""
const anchors=[...document.querySelectorAll('a[onclick*="htmlIconClickOnCachedPortlet"]')];
const seen=new Set(); const rows=[];
for(const a of anchors){
  const m=(a.getAttribute('onclick')||'').match(/htmlIconClickOnCachedPortlet\('(\d+)'/);
  const id=m?m[1]:null; if(!id||seen.has(id)) continue; seen.add(id);
  const tr=a.closest('tr'); let d='';
  if(tr){const dm=tr.innerText.match(/\d{2}-[A-Za-z]{3}-\d{4}[^\n\t]*/); d=dm?dm[0].trim():'';}
  const title=a.textContent.trim().split('\n')[0];
  if(title) rows.push({id:id, title:title, date:d});
}
return rows;
"""

def bofa_collect_section_rows(driver, tabname, island):
    """섹터 maximized 목록에서 모든 행 [(id, title, date), ...] 수집(최신순)."""
    driver.get(bofa_section_url(tabname, island, pagesize=100))
    try:
        WebDriverWait(driver, 45).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[onclick*='htmlIconClickOnCachedPortlet']")))
    except TimeoutException:
        pass
    time.sleep(2)
    raw = driver.execute_script(_BOFA_COLLECT_JS) or []
    return [(r["id"], r["title"], parse_bofa_date(r["date"])) for r in raw]

def bofa_open_report_by_id(driver, report_id):
    """목록에서 해당 id의 리포트 앵커를 클릭 → 새 탭으로 열림.
    반환: 새 탭 핸들. 실패 시 None."""
    handles_before = set(driver.window_handles)
    els = driver.find_elements(
        By.CSS_SELECTOR,
        f"a[onclick*=\"htmlIconClickOnCachedPortlet('{report_id}'\"]")
    if not els:
        return None
    driver.execute_script("arguments[0].click();", els[0])
    try:
        WebDriverWait(driver, 25).until(
            lambda d: len(set(d.window_handles) - handles_before) >= 1)
    except TimeoutException:
        return None
    return list(set(driver.window_handles) - handles_before)[0]

def bofa_download_report_tab(driver, new_handle, out_path):
    """리포트가 열린 새 탭에서 PDF를 받아 out_path로 저장. 끝나면 그 탭을 닫는다."""
    main = driver.current_window_handle
    before = set(os.listdir(BROWSER_DL_DIR))
    driver.switch_to.window(new_handle)
    try:
        try:
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            pass
        time.sleep(2)

        deadline = time.time() + PDF_WAIT_MAX
        last_click = 0.0
        pre_click = None
        while time.time() < deadline:
            try:
                if driver.current_window_handle != new_handle and \
                        new_handle in driver.window_handles:
                    driver.switch_to.window(new_handle)
                driver.switch_to.default_content()
            except Exception:
                pass

            # (A) 탭 자체가 PDF 뷰어면 fetch로 저장
            try:
                if looks_like_pdf_viewer(driver):
                    download_current_pdf_via_fetch(driver, out_path, PDF_WAIT_MAX)
                    return True
            except Exception:
                pass

            # (C) 다운로드 폴더에 새 PDF가 떨어졌나
            fname = wait_new_pdf(before, timeout=1)
            if fname:
                os.replace(os.path.join(BROWSER_DL_DIR, fname), out_path)
                return True

            # (B') 클릭이 PDF 뷰어 새 탭을 열었으면 그 탭에서 fetch
            if pre_click is not None:
                for w in (set(driver.window_handles) - pre_click):
                    try:
                        driver.switch_to.window(w)
                        if looks_like_pdf_viewer(driver):
                            download_current_pdf_via_fetch(driver, out_path, PDF_WAIT_MAX)
                            return True
                    except Exception:
                        pass
                if new_handle in driver.window_handles:
                    try:
                        driver.switch_to.window(new_handle)
                    except Exception:
                        pass

            # (B) PDF 아이콘/버튼 클릭 (다운로드 잡힐 때까지 15초마다 재클릭)
            crd = [f for f in os.listdir(BROWSER_DL_DIR) if f.endswith(".crdownload")]
            if not crd and time.time() - last_click >= 15:
                el = findpdf_clickable(driver)
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

        raise RuntimeError(f"PDF가 {PDF_WAIT_MAX}초 안에 안 떨어짐")
    finally:
        # 리포트 탭(및 뷰어 탭) 정리 후 목록 탭 복귀
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

def bofa_run_section(driver, label, tabname, island, title_filter, days=BOFA_RECENT_DAYS):
    """섹터 목록에 실제로 있는 '최신 발행일부터 서로 다른 날짜 days개'를 받는다.

    [2026-08-13 변경] 이전에는 bofa_main이 ET 기준 '어제'를 계산해 넘겼는데,
      실행 시각(KST 08~09시 = ET 전날 19~20시)과 BofA 발행일이 어긋나 매칭이 0이
      되는 날이 있었다. 미국 공휴일이 끼면 '어제'에 아예 발행분이 없어서 더 확실히 0이 된다.
      → 달력 계산을 버리고 목록에 실제로 있는 날짜를 쓴다. 섹터마다 최신 발행일이
        다를 수 있으므로 대상 날짜도 섹터별로 따로 잡는다.

    [왜 하루가 아니라 days개인가] 최신 발행일이 '아직 발행 중인 날'이면, 그날 늦게
      올라온 리포트는 다음 실행이 그 다음 날짜를 최신으로 잡는 순간 영영 못 받는다.
      직전 날짜까지 같이 훑으면 그 뒤늦은 발행분을 다음 날 주워온다.
      대신 같은 리포트를 이틀 연속 받게 되므로 파일명에 리포트 발행일을 넣어 구분한다
      (bofa_safe_name). 달력일이 아니라 '목록에 있는 날짜' 기준이라 주말/공휴일에
      빈 날을 세느라 낭비하지 않는다.
    """
    print(f"\n--- BofA | {label} ---")
    try:
        rows = bofa_collect_section_rows(driver, tabname, island)
    except Exception as e:
        print(f"  (목록 수집 실패 → 건너뜀: {err1(e, 100)})")
        return 0

    dates = sorted({pub for _, _, pub in rows if pub}, reverse=True)[:max(1, days)]
    if not dates:
        # 목록 0행이면 세션이 풀려 로그인 화면으로 리다이렉트된 것일 가능성이 크다.
        # (그때도 예외가 아니라 '앵커 0개'로 조용히 끝나므로 행 수를 같이 찍는다)
        print(f"  (목록 {len(rows)}행, 날짜 있는 리포트 없음 → 건너뜀)")
        return 0
    targets = set(dates)

    # 대상 날짜에 나온 것만. 목록 정렬 순서에 의존하지 않도록 전부 훑는다.
    picked = [(rid, title, pub) for rid, title, pub in rows
              if pub in targets and (not title_filter or title_filter(title))]

    span = ", ".join(str(d) for d in dates)
    print(f"  {span} 발행분 → 목록 {len(rows)}행 중 대상 {len(picked)}개")
    total = 0
    for i, (rid, title, pub) in enumerate(picked, 1):
        out = os.path.join(
            DOWNLOAD_DIR, bofa_safe_name(title, i, label, pub.strftime("%y%m%d")))
        try:
            handle = bofa_open_report_by_id(driver, rid)
            if handle is None:
                raise RuntimeError("리포트 탭이 안 열림")
            bofa_download_report_tab(driver, handle, out)
            total += 1
            print(f"  [{i:02d}] 성공  {os.path.getsize(out)//1024} KB  {title[:50]}")
        except Exception as e:
            print(f"  [{i:02d}] 실패  {title[:50]}  -> {err1(e)}")
            # 남은 새 탭 정리 후 목록 탭 복귀
            if len(driver.window_handles) > 1:
                m = driver.window_handles[0]
                for h in driver.window_handles[1:]:
                    try:
                        driver.switch_to.window(h); driver.close()
                    except Exception:
                        pass
                driver.switch_to.window(m)
        time.sleep(1)
    print(f"  {label} 완료: {total}개")
    return total

def bofa_main(driver):
    # 발행일은 bofa_run_section이 섹터별 목록에서 직접 잡는다(달력 계산 안 함).
    print("\n=== BofA Global Research | 섹터별 (섹터별 최신 발행일 기준) ===")
    bofa_login(driver)            # ← 목록 열기 전에 먼저 로그인 (기존 로직 그대로)
    total, results = 0, []
    for label, tabname, island, tfilter in BOFA_SECTIONS:
        n = bofa_run_section(driver, label, tabname, island, tfilter)
        results.append((label, n))
        total += n
    detail = " + ".join(f"{l} {n}" for l, n in results)
    print(f"\n  BofA 완료: {detail} = {total}개")
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

def jpmmresearch_present(driver, timeout=8):
    """현재 컨텍스트(기본 or iframe 내부)에 Research 카드가 보이는지 확인."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[normalize-space()='Research']")))
        return True
    except TimeoutException:
        return False

def jpmm_enter_app(driver, max_login_wait_loops=1):
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
            if jpmmresearch_present(driver, 8):
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
            if jpmmresearch_present(driver, 10):
                print("[JPMM] iframe 전환 진입 성공")
                return "iframe"
        except TimeoutException:
            pass
        driver.switch_to.default_content()
        if attempt < max_login_wait_loops:
            print("\n[JPMM] 브라우저에서 직접 로그인(또는 화면 로딩 확인) 후 진행해 주세요.")
            wait_manual("       준비되면 Enter ▶ ")
    raise RuntimeError("JPMM Research 화면을 찾지 못했습니다 (로그인/셀렉터 확인 필요)")

def jpmm_collect_research(driver, max_age_days=JPMM_MAX_AGE_DAYS, max_items=JPMM_MAX_ITEMS):
    """날짜 전용 요소(div.cardDFormattedDate) 기준으로 수집.
    각 날짜에서 부모로 올라가 같은 카드의 title 링크(→ docId)를 찾는다.

    [2026-08-11 변경] 이전에는 제목 링크에서 부모를 거슬러 올라가며 'ago'가
      1번만 나오는 컨테이너를 찾아 날짜로 삼았는데, 카드 구조가 바뀌면
      조용히 0개가 됐다. 날짜 요소를 시작점으로 잡으면 그 문제가 없다.

    [유지되는 사실] 제목 링크 href 에 doc ID 가 들어 있다:
      https://jpmorganmarkets.com/research/content/GPS-5332387-0
      → doc ID 만 뽑으면 jpmm_main 이 PDF 직접 주소를 조립한다.

    반환: [(title, doc_id, age_days), ...]
    """
    items, seen = [], set()
    for d in driver.find_elements(By.CSS_SELECTOR, "div.cardDFormattedDate"):
        try:
            days = parse_relative_age_days(d.text)   # "9h ago" -> 0, "3d ago" -> 3
            if days is None or days > max_age_days:
                continue
            # 같은 카드의 제목 링크를 위로 올라가며 탐색
            link, node = None, d
            for _ in range(8):
                node = node.find_element(By.XPATH, "..")
                els = node.find_elements(
                    By.CSS_SELECTOR,
                    "a[data-testid='card-title-link'], a[href*='/content/']")
                if els:
                    link = els[0]
                    break
            if link is None:
                continue
            href = link.get_attribute("href") or ""
            m = re.search(r"/content/([A-Za-z0-9\-]+)", href)
            if not m:
                continue
            doc_id = m.group(1)
            if doc_id in seen:
                continue
            title = link.text.strip() or "report"
            seen.add(doc_id)
            items.append((title, doc_id, days))
            if len(items) >= max_items:
                break
        except Exception:
            continue
    return items

def jpmm_main(driver):
    print(f"\n=== JPMM | Research ({JPMM_MAX_AGE_DAYS}일 이내) ===")
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
    print(f"  {JPMM_MAX_AGE_DAYS}일 이내 Research {len(items)}개 수집")
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
            print(f"  [{i:02d}] 실패  {title[:50]}  -> {err1(e)}")
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
    wait_manual("       로그인 완료 후 Enter ▶ ")
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
            print(f"  [Day {i:02d}] 실패  {name[:50]}  -> {err1(e)}")
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
            print(f"  [HV {i:02d}] 실패  {name[:40]}  -> {err1(e)}")
        time.sleep(1)
    print(f"  HSBC 완료: {total}개")
    return total

# ============================================================
#  UBS Neo (Macro Strategy / Equity Strategy / Economics)
# ============================================================
# [페이지 구조]
#  - 왼쪽 탭 3개 = 별도 URL (UBS_SECTIONS)
#  - 각 페이지 맨 아래 'All ~ Research' 패널이 전체 목록이며 이미 최신순 정렬
#      div.pcc-client-stream-panel__wrapper
#        └ div.pcc-client-stream-panel__header      → 이름은 섹션마다 다름(All/Latest).
#                                                   이름 대신 '기사 최다 패널'로 고른다
#        └ li.pcc-client-stream-panel__article      → 항목 1건
#             a.pcc-client-stream-panel__article-title   제목 + 링크
#             time.pcc-client-stream-panel__date         datetime="2026-08-05T05:00:18+09:00"
#  - PDF 취득은 공통 헬퍼(download_in_new_tab)의
#    (A)뷰어 fetch / (B)PDF버튼 클릭 / (C)폴더 감시 / (D)printToPDF 폴백에 맡긴다.

def parse_iso_age_days(iso_text):
    """'2026-08-05T05:00:18+09:00' → 오늘 기준 경과일수. 형식 아니면 None."""
    t = (iso_text or "").strip()
    if not t:
        return None
    t = t.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", t)
        if not m:
            return None
        return (date.today() - date(*map(int, m.groups()))).days
    return (date.today() - dt.date()).days

def ubs_find_all_panel(driver):
    """리서치 목록 패널을 반환. UBS가 헤더명을 섹션마다 다르게 바꿔서
    ('All ~ Research' / 'Latest ~ Research' 혼재), 이름 대신
    '기사 수가 가장 많은 패널'을 집계 목록으로 본다. 없으면 None.

    [2026-08-11 확인] 개편 후 섹션별 패널 이름:
      Economics       → 'Fast Take...' + 'Latest Economic Research'   (All 없음)
      EquityStrategy  → 'Latest Equity Strategy Research'             (All 없음)
      MacroStrategy   → 'All Macro Strategy Research'
    이전처럼 헤더가 'All'로 시작하는 패널만 찾으면 3개 중 2개가 '패널 못 찾음'으로 실패한다.

    ※ 이 패널은 lazy-load라 호출 전에 반드시 ubs_scroll_to_load()로 바닥까지
      스크롤되어 있어야 한다. 안 그러면 article이 0개라 최다 판정이 무의미해진다."""
    best, best_count = None, 0
    for w in driver.find_elements(
            By.CSS_SELECTOR, "div.pcc-client-stream-panel__wrapper"):
        try:
            n = len(w.find_elements(
                By.CSS_SELECTOR, "li.pcc-client-stream-panel__article"))
        except Exception:
            continue
        if n > best_count:
            best, best_count = w, n
    return best

def ubs_scroll_to_load(driver, rounds=8, pause=0.7):
    """맨 아래 'All/Latest ~ Research' 패널은 스크롤해야 기사가 채워진다(lazy-load).
    바닥까지 여러 번 스크롤해 목록을 강제로 로드한다.
    (이게 없으면 패널은 찾아지는데 article 0개 → '0개 수집'으로 조용히 끝난다)"""
    last = 0
    for _ in range(rounds):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        h = driver.execute_script("return document.body.scrollHeight")
        if h == last:      # 더 안 늘어나면 다 로드된 것
            break
        last = h
    time.sleep(1.5)

def ubs_logged_in(driver, timeout=20):
    """현재 화면에 리서치 패널이 떴는지 = 로그인된 상태인지."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.pcc-client-stream-panel__wrapper")))
        return True
    except TimeoutException:
        return False

def ubs_login(driver, email=UBS_EMAIL, password=UBS_PASSWORD, timeout=20):
    """
    UBS Neo 로그인.
      1) 전용 프로필에 세션이 살아있으면 그대로 통과 (평소엔 이 경로)
      2) 세션이 풀렸으면 UBS_EMAIL/UBS_PASSWORD 로 자동 로그인 (BofA와 동일 방식)
      3) 2FA(OTP) 화면에서 멈추면 그때만 사람이 코드 입력

    [확정된 셀렉터]
      이메일   #email_input
      Next     button.verify-email-button
      비밀번호 input[name='password_input']
      제출     button.submit-1fa-password-button
    """
    first_url = next(iter(UBS_SECTIONS.values()))

    # 1) 세션이 살아있는지 먼저 확인
    driver.get(first_url)
    if ubs_logged_in(driver, timeout):
        print("[UBS] 로그인된 세션 감지 → 로그인 단계 건너뜀")
        return

    # 2) 자동 로그인
    if not email or not password:
        print("[UBS] UBS_EMAIL/UBS_PASSWORD 없음 → 수동 로그인 대기")
    else:
        try:
            driver.get(UBS_LOGIN_URL)
            el = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "email_input")))
            el.clear(); el.send_keys(email)
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button.verify-email-button"))).click()

            pw = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.NAME, "password_input")))
            pw.clear(); pw.send_keys(password)
            print("[UBS] ID/PW 입력 완료 → 제출")
            try:
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.submit-1fa-password-button"))).click()
            except TimeoutException:
                pw.submit()

            # 로그인 페이지를 벗어나면 성공
            WebDriverWait(driver, 30).until(
                lambda d: "login" not in (d.current_url or "").lower())
            driver.get(first_url)
            if ubs_logged_in(driver, 30):
                print("[UBS] 자동 로그인 완료")
                return
        except Exception as e:
            # 2FA(OTP) 화면이거나 폼 구조가 바뀐 경우 → 아래 수동 폴백
            print(f"[UBS] 자동 로그인 미완료({err1(e, 80)}) → 수동 로그인 대기")

    # 3) 수동 폴백 (2FA 등). 무인 실행이면 wait_manual 이 바로 False 로 돌아온다.
    print("\n[UBS] 열린 브라우저에서 로그인/인증을 완료해 주세요. (neo.ubs.com)")
    wait_manual("       완료 후 Enter ▶ ")
    driver.get(first_url)
    WebDriverWait(driver, 45).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div.pcc-client-stream-panel__wrapper")))

def ubs_collect_section(driver, url, max_age_days=UBS_MAX_AGE_DAYS,
                        limit=UBS_PER_SECTION):
    """한 섹션 페이지의 집계 리서치 목록에서 (href, title, age_days) 수집.
    날짜를 못 읽은 항목은 목록이 최신순이므로 '오늘'로 간주하지 않고 건너뛴다."""
    driver.get(url)
    try:
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "li.pcc-client-stream-panel__article")))
    except TimeoutException:
        pass
    ubs_scroll_to_load(driver)          # ★ lazy-load 패널을 먼저 채운다

    panel = ubs_find_all_panel(driver)
    if panel is None:
        raise RuntimeError("리서치 목록 패널을 찾지 못했습니다")

    items, seen = [], set()
    for li in panel.find_elements(
            By.CSS_SELECTOR, "li.pcc-client-stream-panel__article"):
        try:
            a = li.find_element(
                By.CSS_SELECTOR, "a.pcc-client-stream-panel__article-title")
            href = a.get_attribute("href")
            if not href or href in seen:
                continue
            name = a.text.strip() or a.get_attribute("title") or "report"

            days = None
            try:
                t = li.find_element(
                    By.CSS_SELECTOR, "time.pcc-client-stream-panel__date")
                days = parse_iso_age_days(t.get_attribute("datetime"))
                if days is None:
                    days = parse_relative_age_days(t.text)   # '2 hours ago' 형식 대비
            except Exception:
                pass
            if days is None or days > max_age_days:
                continue

            seen.add(href)
            items.append((href, name, days))
            if len(items) >= limit:
                break
        except Exception:
            continue    # 동적 렌더링으로 stale 된 요소 등은 건너뜀
    return items

def ubs_main(driver):
    print("\n=== UBS Neo | Macro / Equity Strategy / Economics ===")
    ubs_login(driver)
    total = 0
    for section, url in UBS_SECTIONS.items():
        print(f"\n--- {section} ---")
        try:
            items = ubs_collect_section(driver, url)
        except Exception as e:
            print(f"  (목록 수집 실패 → 섹션 건너뜀: {err1(e, 80)})")
            continue
        print(f"  {UBS_MAX_AGE_DAYS}일 이내 {len(items)}개 수집")
        for i, (href, name, days) in enumerate(items, 1):
            tf = (date.today() - timedelta(days=days)).strftime("%y%m%d")
            out = os.path.join(DOWNLOAD_DIR, safe_name(name, i, section, tf))
            try:
                download_in_new_tab(driver, out, href=href)
                total += 1
                print(f"  [{i:02d}] 성공  {os.path.getsize(out)//1024} KB  {name[:50]}")
            except Exception as e:
                print(f"  [{i:02d}] 실패  {name[:50]}  -> {err1(e)}")
            time.sleep(1)
    print(f"  UBS 완료: 총 {total}개")
    return total

# ============================================================
#  Citi Velocity - Content Feeds > Trending
# ============================================================
# [페이지 구조]
#  - 목록/리포트 본문 모두 iframe#Main 안에서 렌더된다 (top 문서엔 카드가 없음)
#  - 탭: div.lmn-tab-item[role='tab'] (id가 '...-tab-Trending', aria-selected로 활성 판별)
#  - 카드 제목: a[class*='card-view-item-title'] — DOM 순서가 곧 트렌딩 랭킹 순서
#  - 비디오 항목은 href에 '/smartlink/video/' 가 들어감 → 받을 게 없으므로 제외
#  - 리포트 탭 안 iframe#Main 에 HTML/PDF 토글(img.HTML_PDF_switch)이 있고,
#    이걸 눌러야 PDF 렌디션이 뜬다 → 그 뒤는 공통 헬퍼와 같은 (뷰어 fetch / 폴더 감시) 경로

def citi_enter_feed_frame(driver, timeout=45):
    """Content Feeds 목록이 렌더되는 iframe#Main 컨텍스트로 진입."""
    driver.switch_to.default_content()
    frame = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.ID, "Main")))
    driver.switch_to.frame(frame)
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "div.lmn-tab-item[role='tab'], a[class*='card-view-item-title']")))

def citi_select_trending(driver):
    """iframe#Main 안에서 'Trending' 탭 활성화(이미 활성이면 그대로)."""
    tabs = driver.find_elements(By.CSS_SELECTOR, "div.lmn-tab-item[role='tab']")
    for t in tabs:
        try:
            label = (t.text or "").strip()
        except Exception:
            label = ""
        tid = (t.get_attribute("id") or "")
        if label == "Trending" or tid.endswith("-tab-Trending"):
            if (t.get_attribute("aria-selected") or "").lower() != "true":
                driver.execute_script("arguments[0].click();", t)
                time.sleep(3)
            return True
    return False

def citi_collect_trending(driver, limit=CITI_PER_SECTION):
    """Trending 카드 상위 limit개 (href, title) 수집. ★비디오(/smartlink/video/)는 제외.
    DOM 순서 = 트렌딩 랭킹 순서라 앞에서부터 채운다."""
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[class*='card-view-item-title']")))
    except TimeoutException:
        pass
    time.sleep(1)
    items, seen = [], set()
    for a in driver.find_elements(By.CSS_SELECTOR, "a[class*='card-view-item-title']"):
        href = a.get_attribute("href")            # 절대 URL
        if not href or href in seen:
            continue
        if "/smartlink/video/" in href:           # ★ 비디오 제외
            continue
        name = (a.text or a.get_attribute("title") or "report").strip()
        seen.add(href)
        items.append((href, name))
        if len(items) >= limit:
            break
    return items

CITI_NAV_MARKER = "__NAVIGATION_BASE64__"

def citi_rendition_url(driver, timeout=30):
    """리포트 래퍼 탭의 URL에서 '기사 본문(rendition) URL'을 뽑아낸다. 없으면 None.

    [2026-08-13 실측] 리포트를 열면 주소 마지막 경로가 URL-safe base64 다(패딩은 '.').
      디코드하면 '__NAVIGATION_BASE64__rendition/eppublic/documentService/<b64>/<b64>' 이고,
      표식을 떼고 도메인을 붙이면 그게 기사 본문 주소다. 최상위 탭으로 바로 열린다.
      (안쪽 b64 두 개는 각각 'user_id=...' / 'doc_id=...&channel=citivelocity&sub-channel=web')
    """
    end = time.time() + timeout
    while time.time() < end:
        seg = (driver.current_url or "").split("?")[0].rsplit("/", 1)[-1]
        if len(seg) > 40:
            s = seg.replace("-", "+").replace("_", "/").replace(".", "=")
            try:
                dec = base64.b64decode(s).decode("utf-8", "replace")
            except Exception:
                dec = ""
            if CITI_NAV_MARKER in dec:
                return ("https://www.citivelocity.com/"
                        + dec.split(CITI_NAV_MARKER, 1)[1].lstrip("/"))
        time.sleep(1)
    return None

def citi_download_report(driver, href, out_path, wait=CITI_PDF_WAIT):
    """리포트 href를 새 탭에서 열고 PDF 저장.
       (A) 래퍼 URL에서 기사 본문 URL을 뽑아 그 페이지로 이동 → printToPDF (기본 경로)
       (B) 도중에 진짜 PDF 뷰어/다운로드가 나오면 그쪽을 채택

    [2026-08-13 전면 교체] 원래는 iframe#Main 의 HTML/PDF 토글(img.HTML_PDF_switch)을
      눌러 PDF 렌디션을 받으려 했는데, 그 요소는 어느 리포트에서도 DIV.d-none 안에 있어
      항상 안 보인다(4건 확인). JS 클릭도 먹지 않아 wait 초를 다 쓰고 폴백으로 떨어졌다.
      게다가 본문은 iframe#Main 안에 동적으로 그려지고 iframe 의 src 가 비어 있어서,
      래퍼 탭 상태의 printToPDF 는 껍데기 1페이지(107KB)만 만들어 놓고 '성공'으로 찍혔다.
      본문 URL 로 갈아타고 렌더하면 같은 리포트가 8페이지(1.4MB)로 제대로 나온다.
    """
    before = set(os.listdir(BROWSER_DL_DIR))
    main = driver.current_window_handle
    handles_before = set(driver.window_handles)
    driver.execute_script("window.open(arguments[0], '_blank');", href)
    WebDriverWait(driver, 20).until(
        lambda d: len(set(d.window_handles) - handles_before) >= 1)
    new_handle = list(set(driver.window_handles) - handles_before)[0]
    driver.switch_to.window(new_handle)
    try:
        try:
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            pass

        # (A) 기사 본문 URL 로 갈아타기
        rend = citi_rendition_url(driver, timeout=30)
        if rend is None:
            # 여기서 그냥 렌더하면 껍데기 1페이지가 '성공'으로 남는다. 실패로 알린다.
            raise RuntimeError("기사 본문 URL을 못 뽑음(래퍼 주소 형식이 바뀌었을 수 있음)")
        try:
            driver.get(rend)
        except TimeoutException:
            pass
        try:
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            pass
        # 본문이 실제로 채워질 때까지 (빈 페이지를 렌더해 버리는 것 방지)
        try:
            WebDriverWait(driver, 20).until(
                lambda d: len(d.find_element(By.TAG_NAME, "body").text) > 500)
        except TimeoutException:
            pass

        # (B) 혹시 진짜 PDF 로 떨어졌으면 그쪽 우선
        try:
            if looks_like_pdf_viewer(driver):
                download_current_pdf_via_fetch(driver, out_path, timeout=wait)
                return
        except Exception:
            pass
        fname = wait_new_pdf(before, timeout=2)
        if fname:
            os.replace(os.path.join(BROWSER_DL_DIR, fname), out_path)
            return

        result = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True, "preferCSSPageSize": True})
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(result["data"]))
    finally:
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

def citi_logged_in(driver):
    """로그인 페이지(/login)로 안 튕기면 로그인된 상태로 본다."""
    return "/login" not in (driver.current_url or "").lower()

def citi_set_input(driver, el, value):
    """입력칸에 값을 넣는다. send_keys 가 아니라 네이티브 setter + 이벤트 발화.

    [2026-08-13 실측] Citi 로그인칸(#userPwd)은 send_keys 가 전혀 안 먹는다.
      el.click() 으로 포커스를 준 뒤에 보내도 value 가 '' 그대로다. 그러면
      'ID를 입력해야 활성화되는' Continue(#btncontinue)가 비활성인 채로 남고,
      2단계 비번칸이 영영 안 떠서 로그인이 TimeoutException 으로 끝난다.
      (예외가 아니라 '입력이 조용히 무시되는' 형태라 로그만 봐선 2FA 로 오해하기 쉽다)
    → 프레임워크가 value 를 자기 상태로 들고 있으므로, 프로토타입의 네이티브 setter 로
      값을 밀어넣고 input/change 를 직접 쏴서 상태를 갱신시킨다. 이러면 버튼이 활성화된다.
    """
    driver.execute_script("""
      const el = arguments[0], v = arguments[1];
      const setter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, v);
      el.dispatchEvent(new Event('input',  {bubbles: true}));
      el.dispatchEvent(new Event('change', {bubbles: true}));
    """, el, value)

# 로그인 폼 셀렉터. '나열 순서'가 곧 우선순위다 (citi_find_first 가 앞에서부터 시도).
# [2026-08-13 실측] 전부 실제 DOM 에서 확인한 값. 범용 셀렉터(button[type=submit],
#   input[type=password])를 섞으면 안 되는 이유는 citi_find_first 주석 참고.
CITI_ID_INPUT  = ((By.ID, "userPwd"),                  # name=userId, aria='Login ID / Email'
                  (By.NAME, "userId"),
                  (By.CSS_SELECTOR, "input[aria-label='Login ID / Email']"))
CITI_PW_INPUT  = ((By.ID, "icgUpassword"),             # ★ type 이 'text' 다(password 아님)
                  (By.NAME, "inptsecpwd"),
                  (By.CSS_SELECTOR, "input[aria-label='Password']"),
                  (By.CSS_SELECTOR, "input[type='password']"))
CITI_LOGIN_BTN = ((By.ID, "btnSignin"),                # 'Log In' (type=button)
                  (By.XPATH, "//button[normalize-space()='Log In']"),
                  (By.XPATH, "//button[normalize-space()='Sign In']"))
# ※ #btnqrSignin('Sign Up', QR 등록)은 절대 후보에 넣지 말 것. 문서 순서상 btnSignin 보다
#   위에 있어서 범용 셀렉터를 쓰면 이쪽이 먼저 잡히고, 로그인 대신 QR 등록으로 넘어간다.

def citi_find_first(driver, candidates, timeout=20):
    """후보 (By, 셀렉터)를 '우선순위대로' 훑어 처음으로 보이고 눌리는 요소를 돌려준다.

    [왜 합집합 셀렉터를 안 쓰나] CSS 의 콤마 목록도, XPath 의 '|' 합집합도 매칭 결과를
      '내가 쓴 순서'가 아니라 '문서 순서'로 돌려준다. 이 로그인 페이지엔 위쪽에
      'Login Support'(type=submit)와 'Sign Up'(#btnqrSignin)이 있어서, 범용 셀렉터를
      섞으면 원하는 버튼 대신 그쪽이 잡힌다. 그래서 후보를 하나씩 순서대로 시도한다.
      is_enabled 까지 보는 이유: Continue 는 ID 를 넣기 전까지 비활성이다.
    """
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in candidates:
            try:
                for e in driver.find_elements(by, sel):
                    if e.is_displayed() and e.is_enabled():
                        return e
            except Exception:
                continue
        time.sleep(0.5)
    raise TimeoutException(f"후보 요소를 못 찾음: {candidates[0][1]} 외 {len(candidates)-1}개")

def citi_login(driver, username=CITI_USERNAME, password=CITI_PASSWORD, timeout=30):
    """Citi Velocity 로그인 (2단계: Login ID → Continue → Password → Log In).
       1) 전용 프로필 세션이 살아있으면 그대로 통과 (평소엔 이 경로)
       2) 세션 풀리면 CITI_USERNAME/CITI_PASSWORD 로 자동 로그인
       3) 폼 변경/2FA 로 막히면 수동 폴백(무인 실행이면 잠깐 대기 후 진행)

    [확정 셀렉터] ID칸 #userPwd(name=userId) / Continue #btncontinue
    [미확정(추정)] 2단계 비번칸은 input[type=password], 최종버튼은 제출버튼으로 잡음
                  → 회사망에서 한 번 돌려보고 안 되면 이 두 줄만 실제 id로 바꾸면 됨."""
    # 1) 세션 확인
    # [2026-08-13 확인] 세션이 죽어 /login 으로 리다이렉트될 때 이 get() 자체가
    #   TimeoutException('frame does not have execution context')로 터진다.
    #   여기서 예외가 그대로 나가면 아래 자동 로그인 단계를 통째로 건너뛰고
    #   run_site가 'Citi 단계 실패'로 사이트를 접어버린다(실측). → 확인 실패는
    #   '로그인 안 된 것'으로 보고 다음 단계로 넘긴다.
    try:
        driver.get(CITI_HOME)
        time.sleep(3)
        if citi_logged_in(driver):
            print("[Citi] 로그인된 세션 감지 → 로그인 단계 건너뜀")
            return
    except Exception as e:
        print(f"[Citi] 세션 확인 실패({err1(e, 80)}) → 로그인 단계로 진행")

    # 2) 자동 로그인
    if not username or not password:
        print("[Citi] CITI_USERNAME/CITI_PASSWORD 없음 → 수동 로그인 대기")
    else:
        try:
            driver.get(CITI_LOGIN_URL)
            # (쿠키 배너가 클릭을 가리면 제거 — 있으면 누르고 없으면 무시)
            try:
                ot = driver.find_elements(By.ID, "onetrust-accept-btn-handler")
                if ot:
                    driver.execute_script("arguments[0].click();", ot[0])
                    time.sleep(0.5)
            except Exception:
                pass

            # (1단계) Login ID 입력
            uid = citi_find_first(driver, CITI_ID_INPUT, timeout=20)
            citi_set_input(driver, uid, username)   # ← send_keys 안 먹음(위 주석 참고)
            time.sleep(0.5)
            # Continue (ID 입력하면 활성화됨)
            # [2026-08-13 실측] 여기서 '#btncontinue, button[type=submit]' 처럼 합집합으로
            #   잡으면 안 된다. CSS 셀렉터 목록은 '어느 쪽이 먼저 쓰였나'가 아니라 '문서 순서'로
            #   반환되는데, 이 페이지엔 Continue 보다 위에 'Login Support'(역시 type=submit)
            #   버튼이 있어서 그쪽이 잡힌다. → 지원 페이지로 넘어가 비번칸이 영영 안 뜨고
            #   2단계 대기가 TimeoutException 으로 끝난다(실제 이 증상으로 실패했음).
            cont = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "btncontinue")))
            driver.execute_script("arguments[0].click();", cont)

            # (2단계) 비밀번호 칸 등장 대기
            # [2026-08-13 실측] 이 칸은 type 이 'password' 가 아니라 'text' 다.
            #   (id=icgUpassword / name=inptsecpwd / aria-label='Password')
            #   그래서 input[type='password'] 로 기다리면 화면엔 비번칸이 멀쩡히 떠 있는데도
            #   20초를 꽉 채우고 TimeoutException 으로 끝난다 — 실제 이 증상으로 실패했음.
            pw = citi_find_first(driver, CITI_PW_INPUT, timeout=20)
            citi_set_input(driver, pw, password)    # ← 여기도 같은 이유로 JS 입력
            time.sleep(0.5)
            print("[Citi] ID/PW 입력 완료 → 로그인 제출")

            # 최종 로그인 버튼 (#btnSignin, 'Log In')
            try:
                btn = citi_find_first(driver, CITI_LOGIN_BTN, timeout=10)
                driver.execute_script("arguments[0].click();", btn)
            except TimeoutException:
                pw.submit()

            # 로그인 페이지를 벗어나면 성공
            WebDriverWait(driver, 30).until(
                lambda d: "/login" not in (d.current_url or "").lower())
            driver.get(CITI_HOME); time.sleep(3)
            if citi_logged_in(driver):
                print("[Citi] 자동 로그인 완료")
                return
        except Exception as e:
            print(f"[Citi] 자동 로그인 미완료({err1(e, 80)}) → 수동 로그인 대기")

    # 3) 수동 폴백 (2FA 등). 무인 실행이면 wait_manual 이 바로 False 로 돌아온다.
    print("\n[Citi] 열린 브라우저에서 로그인/인증을 완료해 주세요. (citivelocity.com)")
    wait_manual("       완료 후 Enter ▶ ")
    driver.get(CITI_HOME); time.sleep(3)

def citi_main(driver):
    print(f"\n=== Citi Velocity | Content Feeds > Trending 상위 {CITI_PER_SECTION} (비디오 제외) ===")
    citi_login(driver)
    items = []
    for attempt in range(3):
        try:
            citi_enter_feed_frame(driver)
            citi_select_trending(driver)
            items = citi_collect_trending(driver)
            if items:
                break
        except Exception as e:
            print(f"  (피드 로드 재시도 {attempt + 1}/3: {err1(e, 80)})")
        driver.switch_to.default_content()
        driver.get(CITI_HOME)
        time.sleep(3)
    print(f"  Trending {len(items)}개 수집")
    driver.switch_to.default_content()
    total = 0
    for i, (href, name) in enumerate(items, 1):
        out = os.path.join(DOWNLOAD_DIR, safe_name(name, i, "Citi_Trending", "1d"))
        try:
            citi_download_report(driver, href, out)
            total += 1
            print(f"  [{i:02d}] 성공  {os.path.getsize(out)//1024} KB  {name[:50]}")
        except Exception as e:
            print(f"  [{i:02d}] 실패  {name[:50]}  -> {err1(e)}")
        time.sleep(1)
    print(f"  Citi 완료: {total}개")
    return total

# ============================================================
#  실행
# ============================================================

def run_site(name, fn, driver):
    """한 사이트에서 에러가 나도 전체가 멈추지 않도록 격리 실행."""
    try:
        return fn(driver)
    except Exception as e:
        print(f"\n[!] {name} 단계 실패 → 건너뜀: {err1(e, 200)}")
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

def check_credentials():
    """비어 있는 계정정보를 실행 첫머리에 알린다(.env 누락/오타 조기 발견)."""
    missing = [k for k in ("BOFA_USERID", "BOFA_PASSWORD", "UBS_EMAIL", "UBS_PASSWORD",
                           "CITI_USERNAME", "CITI_PASSWORD")
               if not os.environ.get(k)]
    if missing:
        print(f"[env] 값 없음: {', '.join(missing)}  ({ENV_PATH})")
        print("      해당 사이트는 저장된 로그인 세션이 있어야만 수집됩니다.")

# 실행 순서. 이름은 명령줄 인자와 대조하므로 대소문자 무관하게 매칭한다.
SITE_RUNNERS = [
    ("Marquee", marquee_main),   # 1) Marquee (+ Portfolio Strategy)
    ("BofA",    bofa_main),      # 2) BofA
    ("JPMM",    jpmm_main),      # 3) JPMM
    ("HSBC",    hsbc_main),      # 4) HSBC
    ("UBS",     ubs_main),       # 5) UBS Neo
    ("Citi",    citi_main),      # 6) Citi Velocity
]

# ┌──────────────────────────────────────────────────────────────────┐
# │ [현재 설정] 5개 사이트 전부 실행                                 │
# │                                                                  │
# │ 일부만 돌리려면 여기에 이름을 넣으세요. 예) ["BofA", "UBS"]      │
# │ 단, 작업 스케줄러('리서치 자동수집')도 이 설정을 따르므로        │
# │ 되돌리는 걸 잊으면 매일 아침 일부만 수집하게 됩니다.             │
# │ 한 번만 일부 실행할 거면 코드 대신 실행 인자를 쓰세요.           │
# │   예) python 이파일.py bofa ubs                                  │
# └──────────────────────────────────────────────────────────────────┘
ONLY_SITES = None                # ← 전부 실행 (일부만: ["BofA", "UBS"] 처럼)

def pick_sites(argv=None):
    """실행할 사이트 목록을 정한다. 우선순위: 명령줄 인자 > ONLY_SITES > 전체.

      python gs리서치자료모으기_....py            → ONLY_SITES 설정을 따름
      python gs리서치자료모으기_....py bofa ubs   → BofA, UBS Neo 만 (설정 무시)
      python gs리서치자료모으기_....py all        → 설정 무시하고 5개 전부
    """
    want = {a.strip().lower() for a in (argv if argv is not None else sys.argv[1:]) if a.strip()}
    if want == {"all"}:
        return list(SITE_RUNNERS)
    if not want:
        if not ONLY_SITES:
            return list(SITE_RUNNERS)
        want = {s.strip().lower() for s in ONLY_SITES}
    known = {name.lower() for name, _ in SITE_RUNNERS}
    unknown = want - known
    if unknown:
        print(f"[!] 모르는 사이트 이름 무시: {', '.join(sorted(unknown))} "
              f"(가능: {', '.join(n for n, _ in SITE_RUNNERS)})")
    picked = [(n, f) for n, f in SITE_RUNNERS if n.lower() in want]
    if not picked:
        print("[!] 실행할 사이트가 없습니다 → 전체 실행으로 대체")
        return list(SITE_RUNNERS)
    return picked

def main():
    check_credentials()
    runners = pick_sites()
    if len(runners) < len(SITE_RUNNERS):
        print(f"[실행 대상] {', '.join(n for n, _ in runners)} "
              f"(전체 {len(SITE_RUNNERS)}개 중 {len(runners)}개)")
        print("           ※ 전체로 되돌리려면 코드의 ONLY_SITES 를 None 으로 바꾸세요.")
    driver = make_driver()
    try:
        results = []
        for name, fn in runners:
            results.append((name, run_site(name, fn, driver)))
        grand = sum(v for _, v in results)
        detail = " + ".join(f"{n} {v}" for n, v in results)
        print(f"\n전체 완료: {detail} = {grand}개 → {DOWNLOAD_DIR}")
    finally:
        # 붙기 모드: quit()은 연결된 창을 닫으므로 호출하지 않음 (브라우저 유지)
        # 다만 chromedriver 는 반드시 정리한다.
        # [2026-08-19 실측] quit() 을 안 부르면 chromedriver 가 고아로 남는데, 이 프로세스가
        #   python 에서 상속받은 **로그 파일 핸들을 계속 붙잡고 있다.** python 을 죽여도 안 풀린다.
        #   그러면 다음 실행이 '>> 로그' 를 못 열어 python 이 아예 안 뜨고, 로그도 안 남아
        #   "셀레니움이 고장났다"로만 보인다. (08-19 아침에 실제로 이 상태였다)
        #   service.stop() 은 chromedriver 만 끝내고 9222 크롬은 그대로 살려둔다 — 확인함.
        try:
            driver.service.stop()
        except Exception:
            pass
if __name__ == "__main__":
    main()
