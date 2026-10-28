"""Wait for the exact committed PCA III snapshot on the production alias."""
import hashlib,json,time,urllib.request,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
site='https://macro-hub-nu.vercel.app'
revision=subprocess.check_output(['git','rev-parse','--short=8','HEAD'],cwd=ROOT,text=True).strip()
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'QAE-PCA-III-verification','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read()
def digest(value):return hashlib.sha256(value.replace(b'\r\n',b'\n')).hexdigest()
local=ROOT/'macro_hub/public/embeds/pca-iii'
expected={f:digest((local/f).read_bytes()) for f in ['index.html','indices.csv','classification_signs.csv','blackrock_coverage.html']}
old=ROOT/'macro_hub/public/embeds/gdp-weighted/index.html'
last=None
for attempt in range(24):
    try:
        status=json.loads(fetch('https://api.github.com/repos/squarrel808/QAE-dashboard/commits/'+revision+'/status'))
        state=status.get('state','pending')
        if state!=last:print('Deployment',state,flush=True);last=state
        if digest(fetch(site+'/embeds/pca-iii/index.html?revision='+revision))==expected['index.html']:
            for f,h in expected.items():assert digest(fetch(site+'/embeds/pca-iii/'+f+'?revision='+revision))==h,f
            route=fetch(site+'/pca-iii?revision='+revision).decode('utf8')
            assert 'PCA III' in route and '/embeds/pca-iii/index.html' in route
            assert digest(fetch(site+'/embeds/gdp-weighted/index.html?revision='+revision))==digest(old.read_bytes())
            assert fetch(site+'/pca?revision='+revision)
            print('PASS: production PCA III route and exact snapshot; PCA II unchanged; original PCA route available',flush=True)
            break
    except Exception as e:
        msg=type(e).__name__+': '+str(e)
        if msg!=last:print(msg,flush=True);last=msg
    time.sleep(20)
else:raise RuntimeError('PCA III production verification timed out')
