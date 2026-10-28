"""Verify the PCA II navigation and dynamic embedded dashboard height."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
B=Path(__file__).resolve().parent
base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8765'
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,channel='msedge')
 page=browser.new_page(viewport={'width':1440,'height':1000})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 response=page.goto(base+'/gdp-pca');assert response.status==200
 assert page.get_by_role('link',name='PCA II',exact=True).count()==1
 assert page.get_by_role('link',name='PCA',exact=True).count()==1
 frame=page.frame_locator('iframe')
 frame.locator('#cycleChart svg').wait_for()
 frame.locator('[data-c="ALL"]').click()
 assert frame.locator('#drillCharts .mini-card').count()==288
 page.wait_for_function("document.querySelector('iframe').getBoundingClientRect().height >= document.querySelector('iframe').contentDocument.body.getBoundingClientRect().height-3")
 large=page.locator('iframe').bounding_box()['height']
 frame.locator('[data-c="FR"]').click()
 page.wait_for_function("document.querySelector('iframe').getBoundingClientRect().height < "+str(large-500))
 assert frame.locator('#drillCharts .mini-card').count()==13
 page.evaluate('window.scrollTo(0,0)')
 page.screenshot(path=str(B/'pca_ii_hub_preview.png'))
 # Existing PCA stays on its original route and renders its native content.
 response=page.goto(base+'/pca');assert response.status==200
 assert page.get_by_text('Category PCA · Equal-Weight GDP Proxy',exact=False).count()==1
 assert not errors,errors
 browser.close()
print('PASS: PCA II navigation, iframe expansion/shrink, published input cards, and existing PCA route')
