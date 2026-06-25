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

# Windows 콘솔(cp949)에서 ✓ 같은 유니코드 출력 시 UnicodeEncodeError 방지
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# ─────────────────────────────────────────
# 타깃 국가 코드 (G7 + 호주 + 중국 + 한국)
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
    importance_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@class,'btn-calendar') and contains(.,'충격')]")
        )
    )
    importance_btn.click()
    time.sleep(0.8)

    wait.until(
        EC.presence_of_all_elements_located(
            (By.XPATH, "//a[@onclick and contains(@onclick,'setCalendarImportance')]")
        )
    )

    for level in ('1', '2', '3'):
        want_selected = (level == '3')
        for attempt in range(3):
            try:
                link = driver.find_element(
                    By.XPATH,
                    f"//a[@onclick and contains(@onclick,\"setCalendarImportance('{level}')\")]"
                )
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

    driver.find_element(By.TAG_NAME, 'body').click()
    time.sleep(1)
    print("[✓] 충격(중요도) 별3개 설정 완료")


def set_countries(driver, wait):
    """나라 드롭박스 → G7 + 호주 + 중국 + 한국만 선택"""
    country_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[@onclick='toggleMainCountrySelection();']")
        )
    )
    country_btn.click()
    time.sleep(1)

    wait.until(
        EC.visibility_of_element_located(
            (By.XPATH, "//li[@onclick and contains(@onclick,'calendarSelecting')]")
        )
    )

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

    target_codes_upper = [code.upper() for code in TARGET_COUNTRIES.keys()]

    available_codes = []
    for li in driver.find_elements(By.XPATH, "//li[contains(@onclick,'calendarSelecting')]"):
        onclick_attr = li.get_attribute('onclick')
        if not onclick_attr:
            continue
        m = re.search(r"'([A-Z0-9]+)'", onclick_attr)
        if m and m.group(1) in target_codes_upper:
            available_codes.append(m.group(1))

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


def main():
    driver = setup_driver(headless=False)
    wait = WebDriverWait(driver, 15)

    try:
        print("[1] 사이트 접속 중...")
        driver.get('https://ko.tradingeconomics.com/calendar')
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'tr')))
        time.sleep(2)

        print("[2] 충격 드롭박스 설정 중...")
        set_importance_3stars(driver, wait)
        time.sleep(1.5)

        print("[3] 나라 드롭박스 설정 중...")
        set_countries(driver, wait)
        time.sleep(2)

        print("[4] 테이블 데이터 추출 중...")
        data = extract_table(driver, wait)

        if not data:
            print("[!] 데이터가 없습니다. 필터 설정을 확인하세요.")
            return

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

        csv_path = 'tradingeconomics_calendar.csv'
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"\n[✓] CSV 저장 완료: {csv_path}")

        return df

    finally:
        input("\n[종료하려면 Enter를 누르세요...]")
        driver.quit()


if __name__ == '__main__':
    df = main()