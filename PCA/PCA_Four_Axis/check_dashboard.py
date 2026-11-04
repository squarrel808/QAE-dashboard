"""Browser smoke check of all regions, both modes, and the audit filters."""
from pathlib import Path
from playwright.sync_api import sync_playwright
B=Path(__file__).resolve().parent
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,channel='msedge')
    page=browser.new_page(viewport={'width':1440,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((B/'index.html').as_uri())
    assert page.locator('#countries button').count()==8
    assert page.locator('a[href="blackrock_coverage.html"]').count()==1
    for cc in ['US','UK','FR','DE','CA','JP','AU']:
        page.locator(f'button[data-c="{cc}"]').click()
        for mode in ['yoy','momentum']:
            page.locator('#'+mode).click()
            assert page.locator('#mainchart svg').count()==1
            assert page.locator('#blockcharts svg').count()==4
            assert 'NaN' not in page.locator('#mainchart').inner_html()
            assert 'undefined' not in page.locator('#cards').inner_text()
    page.locator('button[data-c="US"]').click();page.locator('#yoy').click()
    page.screenshot(path=str(B/'blackrock_union_preview.png'),full_page=True)
    page.goto((B/'blackrock_coverage.html').as_uri())
    assert page.locator('#mapping tbody tr').count()==198
    page.locator('#status').select_option(label='신규 편입')
    assert page.locator('#mapping tbody tr:visible').count()==101
    page.locator('#q').fill('캐나다')
    assert page.locator('#mapping tbody tr:visible').count()==8
    page.locator('#q').fill('');page.locator('#status').select_option(label='모든 처리')
    page.screenshot(path=str(B/'blackrock_coverage_preview.png'),full_page=True)
    assert not errors,errors
    browser.close()
print('PASS: seven region buttons, both modes, SVG charts, audit counts and filters, no browser errors')
