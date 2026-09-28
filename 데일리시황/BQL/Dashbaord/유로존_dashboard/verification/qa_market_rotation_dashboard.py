from pathlib import Path
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


HERE = Path(__file__).resolve().parent
HTML = HERE.parent / "Market_Rotation_Dashboard_17_Indices.html"
OUT = HERE

options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--allow-file-access-from-files")
options.add_argument("--hide-scrollbars")
options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

driver = webdriver.Chrome(options=options)
try:
    driver.get(HTML.as_uri())
    frame = WebDriverWait(driver, 20).until(lambda d: d.find_element(By.CSS_SELECTOR, "iframe"))
    driver.switch_to.frame(frame)
    WebDriverWait(driver, 20).until(lambda d: d.execute_script("return typeof d3 !== 'undefined'"))
    WebDriverWait(driver, 20).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#mrd-sector-heatmap svg")) == 1)

    for width, height in ((1024, 900), (736, 1100), (360, 1200)):
        driver.set_window_size(width, height)
        for tab in ("europe", "index", "index2", "groups", "price1", "price2", "valuation1", "valuation2", "quality", "coverage"):
            driver.find_element(By.CSS_SELECTOR, f"button[data-tab='{tab}']").click()
            time.sleep(0.25)
            panel = driver.find_element(By.CSS_SELECTOR, f"section[data-panel='{tab}']")
            assert panel.is_displayed(), f"{tab} panel is hidden at {width}px"
            assert driver.execute_script("return document.body.scrollWidth <= window.innerWidth + 1"), f"body overflow at {width}px in {tab}"
        driver.find_element(By.CSS_SELECTOR, "button[data-tab='index']").click()
        time.sleep(0.25)
        driver.save_screenshot(str(OUT / f"_mrd_index_{width}.png"))

    driver.set_window_size(1024, 900)
    driver.find_element(By.CSS_SELECTOR, "button[data-tab='valuation2']").click()
    time.sleep(0.35)
    assert len(driver.find_elements(By.CSS_SELECTOR, "#mrd-boxplot svg")) == 1
    driver.save_screenshot(str(OUT / "_mrd_valuation_1024.png"))

    driver.find_element(By.CSS_SELECTOR, "button[data-tab='quality']").click()
    time.sleep(0.35)
    assert len(driver.find_elements(By.CSS_SELECTOR, "#mrd-quality-scatter svg")) == 1
    driver.save_screenshot(str(OUT / "_mrd_quality_1024.png"))

    errors = [entry for entry in driver.get_log("browser") if entry.get("level") == "SEVERE"]
    if errors:
        raise RuntimeError(f"Browser console errors: {errors}")
    print("browser_tabs=PASS")
    print("responsive_widths=1024,736,360 PASS")
    print("console_errors=0")
finally:
    driver.quit()
