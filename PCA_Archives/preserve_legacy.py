"""Preserve the pre-CFNAI release without changing the active estimators."""
import hashlib,json,subprocess,zipfile
from pathlib import Path
from importlib.metadata import version

ROOT=Path(__file__).resolve().parent.parent
OLD='bb4f6ac7'
REF=subprocess.check_output(['git','rev-parse',OLD],cwd=ROOT,text=True).strip()
DEST=ROOT/'macro_hub/public/embeds/pca-legacy'
LOCAL=ROOT/'PCA_Archives/2026-10-29_pre_cfna'
BEFORE=ROOT/'outputs/pca_cfna_comparison/before'
snapshot=json.loads((BEFORE/'snapshot.json').read_text(encoding='utf8'))
def blob(path):return subprocess.check_output(['git','show',REF+':'+path],cwd=ROOT)
def paths(*roots):
    return subprocess.check_output(['git','ls-tree','-r','--name-only',REF,*roots],cwd=ROOT,text=True,encoding='utf8').splitlines()
def digest(data):return hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()
manifest={'stored_date_kst':'2026-10-29','source_commit':REF,'type':'immutable_previous_published_release',
    'method':'EWM Level half-life 24 months; time-varying loadings; II/III nonnegative constraints; I separate Momentum PCA with half-life 12 months',
    'automatic_refresh':False,'files':{}}
mapping={'macro_hub/public/data/pca.json':'i/data.json','macro_hub/public/embeds/pca.html':'i/index.html'}
for original,short in [('macro_hub/public/embeds/gdp-weighted','ii'),('macro_hub/public/embeds/pca-iii','iii')]:
    for path in paths(original):mapping[path]=short+'/'+Path(path).name
for source,target in mapping.items():
    content=blob(source);p=DEST/target;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
    manifest['files'][target]={'source_path':source,'sha256_lf_normalized':digest(content)}
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
# Preserve the original React presentation of PCA I as well as its data.
(ROOT/'macro_hub/components/PcaLegacy.tsx').write_bytes(blob('macro_hub/components/Pca.tsx'))

LOCAL.mkdir(parents=True,exist_ok=True)
bundle=LOCAL/'source_data_and_results.zip'
inputs=['haver/haver-api_PCA/Meta data_Raw data.xlsx','PCA_Four_Axis/source/raw_haver.csv',
    'PCA_Four_Axis/source/metadata.json','PCA_Four_Axis/values.csv','PCA_Four_Axis/metadata.json',
    'PCA_Four_Axis/blackrock_source/values.csv','PCA_Four_Axis/blackrock_source/metadata.json',
    'outputs/gdp_expenditure_review/report_data.json']
for path,expected in snapshot['raw_hashes'].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,('Raw vintage changed',path)
sources=paths('PCA','PCA_Four_Axis','PCA_BlackRock_Only','PCA_GDP_Weighted',
    'macro_hub/components/Pca.tsx','macro_hub/public/data/pca.json','macro_hub/public/embeds/pca.html',
    'macro_hub/public/embeds/gdp-weighted','macro_hub/public/embeds/pca-iii',
    'macro_hub/scripts/sync_gdp_weighted.mjs','macro_hub/scripts/sync_pca_iii.mjs','run_qae.py')
if not bundle.exists():
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sources:z.writestr('previous_commit/'+path,blob(path))
        for path in inputs:z.write(ROOT/path,'fixed_raw_data/'+path)
        for p in BEFORE.rglob('*'):
            if p.is_file():z.write(p,'before_comparison/'+p.relative_to(BEFORE).as_posix())
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('runtime.json',json.dumps({p:version(p) for p in ['numpy','pandas','scipy','openpyxl']},indent=2))
with zipfile.ZipFile(bundle) as z:
    assert z.testzip() is None
    for path in sources:assert digest(z.read('previous_commit/'+path))==digest(blob(path)),path
    for path in inputs:assert z.read('fixed_raw_data/'+path)==(ROOT/path).read_bytes(),path
    count=len(z.namelist())
record={**manifest,'local_bundle':str(bundle.relative_to(ROOT)),'bundle_sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),
    'bundle_entries':count,'raw_hashes':snapshot['raw_hashes'],'integrity':'verified'}
(ROOT/'PCA_Archives/legacy_20261029.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
print('Previous published files restored:',len(mapping))
print('Source/data/results bundle verified:',count,'entries;',round(bundle.stat().st_size/1024/1024,1),'MiB')
