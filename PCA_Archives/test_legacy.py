"""Verify restored pages, original numerical payloads and version navigation."""
import hashlib,json,subprocess,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parent.parent
B=R/'macro_hub/public/embeds/pca-legacy'
manifest=json.loads((B/'manifest.json').read_text(encoding='utf8'))
for path,row in manifest['files'].items():
    assert hashlib.sha256((B/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==row['sha256_lf_normalized']
old_ui=subprocess.check_output(['git','show',manifest['source_commit']+':macro_hub/components/Pca.tsx'],cwd=R)
assert old_ui.replace(b'\r\n',b'\n')==(R/'macro_hub/components/PcaLegacy.tsx').read_bytes().replace(b'\r\n',b'\n')
base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8766'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,channel='msedge')
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    assert page.goto(base+'/pca-legacy').status==200
    for model in ['i','ii','iii']:assert page.locator(f'a[href="/pca-legacy/{model}"]').count()==1
    assert page.goto(base+'/pca-legacy/i').status==200
    assert page.get_by_text('Category PCA · Equal-Weight GDP Proxy',exact=False).count()==1
    assert page.get_by_text('반감기 24M',exact=False).count()>0
    page.locator('select').first.select_option('UK')
    assert page.get_by_text('United Kingdom — Activity Index',exact=False).count()==1
    for model,route in [('ii','/gdp-pca'),('iii','/pca-iii')]:
        assert page.goto(base+'/pca-legacy/'+model).status==200
        frame=page.frame_locator('iframe');frame.locator('#cycleChart svg').wait_for()
        d=json.loads(frame.locator('#payload').text_content())
        assert 'EWM half-life 24' in d['method'] and 'estimation' not in d
        assert all(r['loading'] is None or r['loading']>=0 for r in d['indicators'])
        frame.locator('[data-c="UK"]').click()
        assert frame.locator('#mainchart svg').count()==1
        if model=='iii':assert frame.locator('#momentumChart svg').count()==1
        assert page.get_by_role('link',name='현재 방식 보기',exact=True).get_attribute('href')==route
        page.screenshot(path=str(R/'PCA_Archives'/('legacy_'+model+'.png')))
        page.get_by_role('link',name='현재 방식 보기',exact=True).click()
        page.wait_for_url('**'+route)
        page.wait_for_function("""() => {
          const doc = document.querySelector('iframe')?.contentDocument;
          if (doc?.readyState !== 'complete') return false;
          const payload = doc.querySelector('#payload');
          try { return payload && JSON.parse(payload.textContent).estimation?.constraint === 'unrestricted'; }
          catch { return false; }
        }""")
        active=page.frame_locator('iframe');active.locator('#cycleChart svg').wait_for()
        assert json.loads(active.locator('#payload').text_content())['estimation']['constraint']=='unrestricted'
        assert page.get_by_role('link',name='기존 방식 보기',exact=True).get_attribute('href')=='/pca-legacy/'+model
    page.set_viewport_size({'width':390,'height':844});page.goto(base+'/pca-legacy')
    assert page.evaluate('document.documentElement.scrollWidth')<=392
    assert not errors,errors
    browser.close()
print('PASS: original file hashes and PCA I UI; three archived routes; old EWM/nonnegative policy; preserved current model; navigation and mobile layout')
