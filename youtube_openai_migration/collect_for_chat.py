"""Collect YouTube transcripts for chat summarization; no LLM API calls."""
import argparse
import ast
import html
import json
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import certifi
import httplib2
import requests
from dotenv import dotenv_values
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

BASE_DIR = Path(r'C:\Users\infomax\Documents\python\유투브 BBG')
OUTPUT = Path(r'C:\Users\infomax\Documents\python\QAE\youtube_openai_migration\chat_data')

class CaptionSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault('timeout', (10, 25))
        return super().request(*args, **kwargs)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recover', action='store_true')
    parser.add_argument('--hours', type=int, default=48)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO)
    config = dotenv_values(BASE_DIR / '.env')
    bundle = OUTPUT / 'ca-bundle.pem'
    bundle.write_text(Path(certifi.where()).read_text() + '\n' + (BASE_DIR / 'ssl.cer').read_text(), encoding='utf-8')
    os.environ['REQUESTS_CA_BUNDLE'] = str(bundle)
    tree = ast.parse((BASE_DIR / 'summurizer.py').read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in ('fetch_recent_videos', 'get_transcript')) or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CHANNELS' for t in n.targets))]
    ns = dict(globals(), CONFIG={'youtube_api_key': config['YOUTUBE_API_KEY']}, CA_BUNDLE=str(bundle), log=logging.getLogger('collector'))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'collector', 'exec'), ns)
    if args.recover:
        videos = []
        for date in ('2026-10-04', '2026-10-05', '2026-10-06'):
            folder = Path(r'C:\Users\infomax\Desktop\보따리\유투브') / date
            report = next(folder.glob('report_*.html'))
            content = report.read_text(encoding='utf-8')
            for vid, title in re.findall(r'<h2><a href="https://www.youtube.com/watch\?v=([^"&]+)"[^>]*>(.*?)</a></h2>', content):
                videos.append({'id':vid, 'title':html.unescape(title), 'report_date':date, 'source_report':str(report), 'channel_name':'Bloomberg'})
    else:
        # Read every page: Bloomberg can publish more than 50 videos in 72 hours.
        youtube = build('youtube', 'v3', developerKey=config['YOUTUBE_API_KEY'], http=httplib2.Http(ca_certs=str(bundle), timeout=30))
        after = (datetime.now(timezone.utc) - timedelta(hours=args.hours)).strftime('%Y-%m-%dT%H:%M:%SZ')
        videos = []
        for channel in ns['CHANNELS']:
            token = None
            count = 0
            while True:
                params = dict(part='snippet', channelId=channel['channel_id'], publishedAfter=after, order='date', maxResults=50, type='video')
                if token:
                    params['pageToken'] = token
                try:
                    response = youtube.search().list(**params).execute()
                except Exception as exc:
                    raise RuntimeError('YouTube collection failed: ' + channel['name'] + ' / ' + type(exc).__name__) from None
                for item in response.get('items', []):
                    count += 1
                    snippet = item['snippet']
                    title = html.unescape(snippet['title'])
                    keywords = channel.get('keywords', [])
                    if keywords and not any(k in title.lower() for k in keywords):
                        continue
                    videos.append(dict(id=item['id']['videoId'], title=title, published_at=snippet['publishedAt'], thumbnail=snippet['thumbnails']['high']['url'], channel_name=channel['name'], badge_label=channel['badge_label'], badge_bg=channel['badge_bg'], badge_color=channel['badge_color']))
                token = response.get('nextPageToken')
                if not token:
                    break
            logging.info('%s: scanned %s videos across all pages', channel['name'], count)
        done_path = OUTPUT / 'chat_completed.json'
        done = set(json.loads(done_path.read_text(encoding='utf-8'))) if done_path.exists() else set()
        # Keep failed videos even after they fall outside the rolling search window.
        pending = {}
        for previous in (OUTPUT / 'recovery_manifest.json', OUTPUT / 'latest_manifest.json'):
            if previous.exists():
                for video in json.loads(previous.read_text(encoding='utf-8')):
                    if video['id'] not in done:
                        pending[video['id']] = video
        for video in videos:
            pending.setdefault(video['id'], video)
        videos = list(pending.values())
        videos = [v for v in videos if v['id'] not in done]
    for video in videos:
        path = OUTPUT / (video['id'] + '.txt')
        text = path.read_text(encoding='utf-8') if path.exists() else None
        if not text:
            for attempt in range(4):
                try:
                    api = YouTubeTranscriptApi(http_client=CaptionSession())
                    if attempt < 2:
                        fetched = api.fetch(video['id'], languages=['en', 'en-US', 'en-GB'])
                    else:
                        fetched = api.list(video['id']).find_generated_transcript(['en']).fetch()
                    text = ' '.join(s.text for s in fetched)
                    break
                except Exception as exc:
                    logging.warning('%s attempt %s: %s', video['id'], attempt + 1, type(exc).__name__)
                    if type(exc).__name__ in ('IpBlocked', 'RequestBlocked'):
                        break
                    time.sleep(1)
        video['transcript_path'] = str(path) if text else None
        if text:
            path.write_text(text, encoding='utf-8')
        video['transcript_chars'] = len(text or '')
    manifest = OUTPUT / ('recovery_manifest.json' if args.recover else 'latest_manifest.json')
    manifest.write_text(json.dumps(videos, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'manifest':str(manifest), 'videos':[{k:v[k] for k in ('id','title','transcript_chars')} for v in videos]}, ensure_ascii=False))

if __name__ == '__main__':
    main()
