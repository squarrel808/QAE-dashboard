"""Check the six comparison panels, data tables and real browser rendering."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
B=Path(__file__).resolve().parents[1]/'outputs/pca_cfna_comparison'
url=sys.argv[1] if len(sys.argv)>1 else (B/'index.html').as_uri()
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,channel='msedge')
    page=browser.new_page(viewport={'width':1440,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url);page.wait_for_selector('#levelChart svg')
    d=json.loads(page.locator('#comparison-data').text_content())
    assert page.locator('#summary tbody tr').count()==6
    for model in ['I','II','III']:
        page.locator('#model').select_option(model)
        for cc in ['US','UK']:
            page.locator('#country').select_option(cc)
            v=d['models'][model][cc];last=v['latest']
            for measure in ['level','momentum']:
                assert f"{v['new_'+measure][last]:+.3f}" in page.locator('#'+measure+'Latest').text_content()
                assert page.locator('#'+measure+'Chart path').count()==2
            page.locator('#axis').select_option('all')
            assert page.locator('#loads tbody tr').count()==len(v['loadings'])
    page.locator('#model').select_option('II');page.locator('#country').select_option('UK')
    page.locator('#axis').select_option('Consumer');page.locator('#search').fill('unemployment')
    assert '-0.071' in page.locator('#loads').text_content()
    page.locator('#search').fill('');page.locator('#levelChart').scroll_into_view_if_needed()
    page.screenshot(path=str(B/'comparison_preview.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth')<=392
    assert not errors,errors
    browser.close()
print('PASS: 6 model/country panels, old/new endpoints, all loadings, UK unemployment coefficient, browser errors and mobile width')
