import os,json,html
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from youtube_transcript_api import YouTubeTranscriptApi
import requests
root=Path(r'C:\Users\infomax\Documents\python\QAE\youtube_openai_migration\chat_data')
os.environ['REQUESTS_CA_BUNDLE']=str(root/'ca-bundle.pem')
class Session(requests.Session):
 def request(self,*a,**kw):
  kw.setdefault('timeout',(10,20))
  return super().request(*a,**kw)
def fetch(vid):
 p=root/(vid+'.txt')
 if p.exists(): return vid,'cached'
 s=Session()
 try:
  tracks=YouTubeTranscriptApi(http_client=s).list(vid)
  for t in tracks:
   if t.language_code != 'en': continue
   try:
    r=s.get(t._url+'&fmt=json3');r.raise_for_status()
    d=r.json()
    txt=' '.join(html.unescape(seg.get('utf8','')) for ev in d.get('events',[]) for seg in ev.get('segs',[]))
    if len(txt)>5000:
     p.write_text(txt,encoding='utf-8');return vid,len(txt)
   except Exception as e: print(vid,'json3',type(e).__name__,flush=True)
  return vid,'failed'
 except Exception as e: return vid,type(e).__name__
with ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(fetch,['9OwwYtoXZK0','Be6aMTiJbJc','fRqX6wXg2EU']): print(result,flush=True)
