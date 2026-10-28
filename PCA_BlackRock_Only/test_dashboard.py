"""Check paired values, last-month visibility, missing sectors and cycle UI."""
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
    assert page.title().startswith('PCA III')
    assert not page.locator('#yoy').is_visible() and not page.locator('#momentum').is_visible()
    assert page.locator('[data-c]').count()==7 and page.locator('[data-c="FR"]').count()==0
    assert page.locator('#momentumChart svg').count()==1
    assert page.locator('#mainchart').bounding_box()['y']<page.locator('#momentumChart').bounding_box()['y']
    for country in d['countries']:
        page.locator(f'[data-c="{country}"]').click()
        c=d['countries'][country]
        for version,chart in [('YoY','mainchart'),('Momentum','momentumChart')]:
            endpoint=page.locator(f'#{chart} .endpoint')
            assert abs(float(endpoint.get_attribute('data-value'))-c['versions'][version]['latest_value'])<1e-12
            for axis in c['active_axes']:
                v=c['versions'][version];value=v['blocks'][axis][v['dates'].index(v['latest'])]
                actual=page.locator(f'[data-latest-measure="{axis}"][data-version="{version}"]').text_content()
                assert abs(float(actual)-value)<.000501
        assert page.locator('#blockcharts svg').count()==2*len(c['active_axes'])
        for axis in c['missing_axes']:assert page.locator(f'[data-sector="{axis}"] .missing').count()==1
    page.locator('[data-c="ALL"]').click()
    assert page.locator('#drillCharts .mini-card').count()==len(d['indicators'])
    assert page.locator('#blockcharts .sector-heatmap').count()==4
    assert page.locator('#blockcharts svg').count()==0
    for section in page.locator('#blockcharts .sector-heatmap').all():
        assert section.locator('[data-sector-version]').count()==2
        a=section.locator('[data-sector-version="YoY"]').bounding_box()
        b=section.locator('[data-sector-version="Momentum"]').bounding_box()
        assert b['y']>=a['y']+a['height']
    for control in ['sectorWindow','heatWindow']:
        for value in ['12','24','36']:
            page.locator('#'+control).select_option(value)
            selector='#blockcharts .scroll' if control=='sectorWindow' else '.heat-pair .scroll'
            assert page.locator(selector).evaluate_all('(xs)=>xs.every(x=>x.scrollWidth<=x.clientWidth+1)')
        page.locator('#'+control).select_option('12')
    a=page.locator('#heatLevel').bounding_box();b=page.locator('#heatMomentum').bounding_box()
    assert b['y']>=a['y']+a['height']
    month=page.locator('#cycleDate').input_value()
    for measure in ['headline','Housing']:
        page.locator('#cycleMeasure').select_option(measure)
        members=[c for c in d['countries'] if measure=='headline' or measure in d['countries'][c]['active_axes']]
        dot=page.locator(f'#cycleChart circle[data-country="DM"][data-month="{month}"]')
        for version,attr in [('YoY','data-level'),('Momentum','data-momentum')]:
            def val(cc):
                v=d['countries'][cc]['versions'][version];i=v['dates'].index(month)
                return v['headline'][i] if measure=='headline' else v['blocks'][measure][i]
            expected=sum(map(val,members))/len(members)
            assert abs(float(dot.get_attribute(attr))-expected)<1e-12
    page.locator('[data-cycle-toggle="UK"]').click()
    assert page.locator('#cycleChart circle[data-country="UK"]').count()==0
    page.locator('[data-cycle-toggle="UK"]').click()
    page.locator('[data-cycle-toggle="DM"]').click()
    assert page.locator('#cycleChart circle[data-country="DM"]').count()==0
    page.locator('[data-cycle-toggle="DM"]').click()
    page.locator('#blockcharts').scroll_into_view_if_needed();page.screenshot(path=str(B/'overview_preview.png'))
    page.locator('[data-c="UK"]').click();page.locator('#mainchart').scroll_into_view_if_needed();page.screenshot(path=str(B/'uk_preview.png'))
    page.set_viewport_size({'width':390,'height':844});page.locator('[data-c="ALL"]').click()
    assert page.evaluate('document.documentElement.scrollWidth')<=392
    page.locator('#heatSection').scroll_into_view_if_needed()
    page.wait_for_function("[...document.querySelectorAll('.heat-pair .scroll')].every(x=>Math.abs(x.scrollLeft+x.clientWidth-x.scrollWidth)<2)")
    assert not errors,errors
    browser.close()
print('PASS: six-country navigation, two simultaneous metrics and endpoints, vertical sector/Level/Momentum heatmaps, desktop latest-month visibility, six/four-country fixed DM, legend toggle, mobile width')
