"""Check sector heatmap data, clickable legends and fixed-composition DM mean."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
B=Path(__file__).resolve().parent
url=sys.argv[1] if len(sys.argv)>1 else (B/'index.html').as_uri()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,channel='msedge')
 page=browser.new_page(viewport={'width':1440,'height':1100})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(url);page.wait_for_selector('#cycleChart svg')
 d=json.loads(page.locator('#payload').text_content())
 members=['US','UK','FR','DE','CA','JP','AU'];month=page.locator('#cycleDate').input_value()
 i=d['countries']['US']['versions']['YoY']['dates'].index(month)
 def expected(ver,measure='headline',index=i):
  return sum((d['countries'][c]['versions'][ver]['headline'] if measure=='headline' else d['countries'][c]['versions'][ver]['blocks'][measure])[index] for c in members)/7
 page.locator('[data-c="ALL"]').click()
 assert page.locator('#sectorControls').is_visible()
 assert page.locator('#blockcharts .sector-heatmap').count()==4
 assert page.locator('#blockcharts svg').count()==0
 assert page.locator('#blockcharts .scroll').evaluate_all('(xs)=>xs.every(x=>x.scrollWidth<=x.clientWidth+1)')
 for mode,button in [('YoY','yoy'),('Momentum','momentum')]:
  page.locator('#'+button).click()
  for axis in d['axes']:
   panel=page.locator(f'[data-sector="{axis}"]')
   assert panel.locator('tbody tr').count()==7
   for cell in panel.locator(f'td[data-month="{month}"]').all():
    c=cell.get_attribute('data-country')
    assert abs(float(cell.get_attribute('data-value'))-d['countries'][c]['versions'][mode]['blocks'][axis][i])<1e-12
 page.locator('#sectorWindow').select_option('24')
 assert page.locator('[data-sector="Consumer"] thead th').count()==25
 page.locator('#yoy').click()
 dm=page.locator(f'#cycleChart circle[data-country="DM"][data-month="{month}"]')
 assert abs(float(dm.get_attribute('data-level'))-expected('YoY'))<1e-12
 assert abs(float(dm.get_attribute('data-momentum'))-expected('Momentum'))<1e-12
 linear=sum(expected('YoY',index=j) for j in range(i-2,i+1))/3-sum(expected('YoY',index=j) for j in range(i-5,i-2))/3
 assert abs(float(dm.get_attribute('data-momentum'))-linear)<1e-12
 original_dm=dm.get_attribute('data-level')
 us=page.locator('[data-cycle-toggle="US"]');us.click()
 assert us.get_attribute('aria-pressed')=='false'
 assert page.locator('#cycleChart circle[data-country="US"]').count()==0
 assert page.locator('#cycleChart [data-cycle-series="US"]').count()==0
 assert dm.get_attribute('data-level')==original_dm
 page.locator('#cycleMeasure').select_option('Capex')
 assert page.locator('[data-cycle-toggle="US"]').get_attribute('aria-pressed')=='false'
 assert abs(float(dm.get_attribute('data-level'))-expected('YoY','Capex'))<1e-12
 page.locator('[data-cycle-toggle="US"]').click()
 assert page.locator('#cycleChart circle[data-country="US"]').count()>0
 page.locator('[data-cycle-toggle="DM"]').click()
 assert page.locator('#cycleChart circle[data-country="DM"]').count()==0
 page.locator('[data-cycle-toggle="DM"]').click()
 # A missing member cannot silently produce a different six-country composite.
 assert page.evaluate("""() => {const m=$('cycleDate').value,i=D.countries.JP.versions.YoY.dates.indexOf(m),saved=D.countries.JP.versions.YoY.headline[i];D.countries.JP.versions.YoY.headline[i]=null;dmSeriesCache.clear();const missing=atMonth('DM','YoY',m)===null;D.countries.JP.versions.YoY.headline[i]=saved;dmSeriesCache.clear();return missing;}""")
 page.locator('#cycleMeasure').select_option('headline')
 page.locator('#sectorWindow').select_option('12')
 page.locator('#blockcharts').scroll_into_view_if_needed();page.screenshot(path=str(B/'pca_ii_sector_heatmaps.png'))
 page.locator('#cycleSection').scroll_into_view_if_needed();page.screenshot(path=str(B/'pca_ii_dm_cycle.png'))
 page.locator('[data-c="US"]').click()
 assert not page.locator('#sectorControls').is_visible()
 assert page.locator('#blockcharts svg').count()==4
 assert page.locator('[data-cycle-toggle="DM"]').count()==1
 page.locator('[data-cycle-toggle="US"]').click();page.locator('[data-cycle-toggle="DM"]').click()
 assert page.locator('#cycleChart circle').count()==0
 page.locator('[data-cycle-toggle="DM"]').click()
 assert page.locator('#cycleChart circle[data-country="DM"]').count()>0
 page.set_viewport_size({'width':390,'height':844});page.locator('[data-c="ALL"]').click()
 assert page.evaluate('document.documentElement.scrollWidth')<=392
 assert not errors,errors
 browser.close()
print('PASS: sector heatmaps, country view preserved, legend hide/restore, fixed seven-country DM mean, momentum linearity, missing-member exclusion and mobile width')
