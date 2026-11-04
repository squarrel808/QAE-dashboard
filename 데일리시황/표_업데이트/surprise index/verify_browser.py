from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((ROOT/'index.html').as_uri())
    assert page.locator('#economic .country').count()==18
    assert page.locator('#inflation .country').count()==16
    assert page.locator('svg.plot').count()==34
    assert page.locator('.heat tbody tr').count()==34
    before=page.locator('#economic .plot path').last.get_attribute('d')
    page.select_option('#period','1')
    after=page.locator('#economic .plot path').last.get_attribute('d')
    assert before!=after
    page.locator('#shared').uncheck()
    chart=page.locator('#economic .plot').first
    box=chart.bounding_box(); page.mouse.move(box['x']+box['width']/2,box['y']+80)
    assert '5DMA' in page.locator('#economic .hover').first.inner_text()
    with page.expect_download() as info: page.click('#download-economic')
    assert info.value.suggested_filename=='citi_economic.json'
    page.evaluate('window.scrollTo(0,0)'); page.screenshot(path=str(ROOT/'preview_desktop.png'))
    page.set_viewport_size({'width':390,'height':900})
    page.wait_for_timeout(250)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(ROOT/'preview_mobile.png'))
    page.goto((ROOT.parent/'index.html').as_uri())
    assert page.locator('a[href*="surprise index/index.html"]').count()==2
    assert not errors,errors
    browser.close()
print('Browser verified: 34 charts, 34 heatmap rows, period/Y-axis controls, hover, download, mobile layout, portal links.')
