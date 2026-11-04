"""Check the built web route, navigation, paired panels and preserved PCA II."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
B=Path(__file__).resolve().parent
base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8766'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,channel='msedge')
    page=browser.new_page(viewport={'width':1440,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    assert page.goto(base+'/pca-iii').status==200
    links=page.locator('nav a').all_text_contents()
    assert links.index('PCA III')==links.index('PCA II')+1
    assert 'text-white' in page.get_by_role('link',name='PCA III',exact=True).get_attribute('class')
    assert 'text-white' not in page.get_by_role('link',name='PCA',exact=True).get_attribute('class')
    frame=page.frame_locator('iframe')
    frame.locator('#momentumChart svg').wait_for()
    frame.locator('[data-c="ALL"]').click()
    assert frame.locator('#drillCharts .mini-card').count()==162
    assert frame.locator('#blockcharts [data-sector-version]').count()==8
    page.wait_for_function("document.querySelector('iframe').getBoundingClientRect().height>=document.querySelector('iframe').contentDocument.body.getBoundingClientRect().height-3")
    large=page.locator('iframe').bounding_box()['height']
    frame.locator('[data-c="UK"]').click()
    page.wait_for_function('document.querySelector("iframe").getBoundingClientRect().height<'+str(large-500))
    page.screenshot(path=str(B/'hub_preview.png'))
    assert page.goto(base+'/gdp-pca').status==200
    original=page.frame_locator('iframe');original.locator('#cycleChart svg').wait_for()
    assert original.locator('[data-c="FR"]').count()==1
    assert original.locator('#momentumChart').count()==0
    assert page.goto(base+'/pca').status==200
    assert page.get_by_text('CFNAI형 일반 PCA',exact=False).count()==1
    assert not errors,errors
    browser.close()
print('PASS: PCA III route after PCA II, active navigation, automatic iframe height, paired views, preserved PCA/PCA II')
