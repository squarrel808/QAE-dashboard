"""Loopback-only preview; PDF access is restricted to the dashboard's cited documents."""
import argparse,json,re
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from functools import partial

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        route=urlsplit(self.path).path
        if route.startswith('/source/'):
            ident=route.removeprefix('/source/')
            if not re.fullmatch('[a-f0-9]{64}',ident):return self.send_error(404)
            data=json.loads((Path(self.directory)/'dashboard_data.json').read_text(encoding='utf-8'))
            ref=next((s for s in data['sources'] if s['doc_id']==ident),None)
            if not ref:return self.send_error(404)
            source=Path(ref['path'])
            if not source.is_file() or source.suffix.lower()!='.pdf':return self.send_error(404)
            self.send_response(200);self.send_header('Content-Type','application/pdf');self.send_header('Content-Length',str(source.stat().st_size));self.send_header('Cache-Control','no-store');self.end_headers()
            with source.open('rb') as stream:self.copyfile(stream,self.wfile)
            return
        if route not in {'/','/index.html','/dashboard_data.json','/validation.json'}:return self.send_error(404)
        return super().do_GET()
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff');super().end_headers()

if __name__=='__main__':
    home=Path(__file__).resolve().parent
    default=home/'dist' if (home/'dist/index.html').is_file() else home.parent/'output/ecocal_dashboard'
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=default);p.add_argument('--port',type=int,default=8766);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),partial(Handler,directory=str(a.directory)))
    print(f'http://127.0.0.1:{a.port}/',flush=True)
    server.serve_forever()
