"""Behavior and numerical checks for the published PCA II analysis tools."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
B=Path(__file__).resolve().parent
url=sys.argv[1] if len(sys.argv)>1 else (B/'index.html').as_uri()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,channel='msedge')
 page=browser.new_page(viewport={'width':1440,'height':1100})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(url)
 page.wait_for_selector('#cycleChart svg')
 d=page.locator('#payload').text_content();d=json.loads(d)
 assert page.title().startswith('PCA II')
 month=page.locator('#cycleDate').input_value()
 for c in d['countries']:
  page.locator(f'[data-c="{c}"]').click()
  circle=page.locator(f'#cycleChart circle[data-country="{c}"][data-month="{month}"]')
  i=d['countries'][c]['versions']['YoY']['dates'].index(month)
  for ver,attr in [('YoY','data-level'),('Momentum','data-momentum')]:
   expected=d['countries'][c]['versions'][ver]['headline'][i]
   assert abs(float(circle.get_attribute(attr))-expected)<1e-12
  assert page.locator('#heatLevel tbody tr').count()==5
  assert page.locator('#heatMomentum tbody tr').count()==5
  assert page.locator('#drillCharts .mini-card').count()==sum(r['country']==c for r in d['indicators'])
 page.locator('[data-c="ALL"]').click()
 assert page.locator('#cycleChart circle[data-month="'+month+'"]').count()==8
 assert page.locator('#blockcharts .sector-heatmap').count()==4
 assert page.locator('#blockcharts svg').count()==0
 assert page.locator('#heatLevel tbody tr').count()==7
 assert page.locator('#drillCharts .mini-card').count()==288
 page.locator('#cycleMeasure').select_option('Capex')
 for cell in page.locator('#heatLevel td[data-month="'+month+'"]').all():
  c=cell.get_attribute('data-country');i=d['countries'][c]['versions']['YoY']['dates'].index(month)
  assert abs(float(cell.get_attribute('data-value'))-d['countries'][c]['versions']['YoY']['blocks']['Capex'][i])<1e-12
 page.locator('#drillAxis').select_option('Capex')
 assert page.locator('#drillCharts .mini-card').count()==sum(r['axis']=='Capex' for r in d['indicators'])
 page.locator('#drillSearch').fill('usecon:napmc');assert page.locator('#drillCharts .mini-card').count()==1
 page.locator('#drillView').select_option('raw')
 card=page.locator('#drillCharts .mini-card');card.scroll_into_view_if_needed()
 page.wait_for_selector('#drillCharts svg')
 assert 'NaN' not in card.inner_html()
 # Raw display uses the original data rather than an already transformed index.
 raw=d['input_series']['US']['series']['usecon:napmc']['raw'];last=next(x for x in reversed(raw) if x is not None)
 assert f'{last:.3f}' in card.inner_text()
 page.locator('#drillSearch').fill('');page.locator('#drillAxis').select_option('all')
 page.locator('#cycleMeasure').select_option('headline');page.locator('[data-c="US"]').click()
 page.locator('#cycleSection').scroll_into_view_if_needed();page.screenshot(path=str(B/'pca_ii_cycle_preview.png'))
 page.locator('#drillSection').scroll_into_view_if_needed();page.screenshot(path=str(B/'pca_ii_inputs_preview.png'))
 page.set_viewport_size({'width':390,'height':844});page.evaluate('window.scrollTo(0,0)')
 assert page.evaluate('document.documentElement.scrollWidth')<=392, page.evaluate("[...document.querySelectorAll('body *')].map(e=>({id:e.id,tag:e.tagName,w:e.getBoundingClientRect().width,r:e.getBoundingClientRect().right})).filter(e=>e.r>395).slice(0,12)")
 page.screenshot(path=str(B/'pca_ii_mobile_preview.png'))
 assert not errors,errors
 browser.close()
print('PASS: paired-date swirlogram values, both heatmaps, all-country toggle, 288 input cards, raw switch, lazy charts and mobile width')
