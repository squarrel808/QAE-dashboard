"""Refresh the four local raw inputs, tables and review queue; no report writing or publication."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import html
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
DEFAULT_QAE = Path(r'C:\Users\infomax\Documents\python\QAE')


def process_is_alive(pid):
    """Return True only when the PID recorded in update.lock still exists."""
    try:
        pid = int(pid)
        if pid <= 0:
            return False
        os.kill(pid, 0)
        return True
    except (ValueError, TypeError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def acquire_lock(lock):
    try:
        return lock.open('x', encoding='utf-8')
    except FileExistsError:
        try:
            old_pid = lock.read_text(encoding='utf-8').strip()
        except OSError:
            old_pid = ''
        if process_is_alive(old_pid):
            raise RuntimeError(f'갱신이 이미 실행 중입니다(PID {old_pid}): {lock}')
        # A dead/malformed PID means the prior run ended before its finally block.
        lock.unlink(missing_ok=True)
        try:
            return lock.open('x', encoding='utf-8')
        except FileExistsError:
            raise RuntimeError(f'다른 갱신이 동시에 시작되었습니다: {lock}')


def load_module(path, name):
    path = Path(path)
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def discover(raw):
    specs = {'bquant': (('Bquant_',), ('.xlsb', '.xlsx')),
             'growth': (('ECFC_Growth_Consensus', 'ECFC_Growth Consesus'), ('.xlsb',)),
             'inflation': (('ECFC_Inflation_Consensus', 'ECFC_Inflation Consesus'), ('.xlsb',)),
             'weco': (('ecocal',), ('.xlsx',))}
    found = {}
    for key, (prefixes, suffixes) in specs.items():
        candidates = [p for p in raw.iterdir() if p.is_file() and not p.name.startswith('~$')
                      and any(p.name.lower().startswith(prefix.lower()) for prefix in prefixes)
                      and p.suffix.lower() in suffixes]
        if not candidates:
            raise FileNotFoundError(f'{raw} 에 {" 또는 ".join(prefixes)}* 파일이 없습니다.')
        found[key] = max(candidates, key=lambda p: (p.stat().st_mtime_ns, p.name))
    return found


def review_queue(events, previous, requested_at):
    previous = {e['id']: e for e in previous}
    queue = []
    for e in events:
        if not e['available_at_request']:
            continue
        old = previous.get(e['id'])
        changed = [k for k in ('actual', 'survey', 'prior', 'revised') if old and old.get(k) != e.get(k)]
        state = 'new_actual' if not old or old.get('actual') is None else 'revised' if changed else 'unchanged'
        queue.append({**e, 'change_status': state, 'changed_fields': changed,
                      'previous_actual': old.get('actual') if old else None,
                      'observed_at': requested_at,
                      'review_status': 'source_reviewed_ai_draft' if e.get('commentary') else 'awaiting_manual_or_requested_ai_review'})
    return queue


def build_market_tables(bql, out, cutoff, periods):
    import openpyxl
    sector = load_module(bql/'Theme/Material/Sector_Industry/Reports/build_sector_rotation_html.py', 'daily_sector')
    ai_html = load_module(bql/'Theme/Material/AI/build_ai_value_chain_html.py', 'daily_ai_html')
    master = bql/'Rawfile/BQuant_Master.xlsx'
    with contextlib.closing(openpyxl.load_workbook(master, read_only=True, data_only=True)) as wb:
        raws = [sector.load_market(wb, key) for key in sector.MARKETS]
    descriptions = sector.load_descriptions(sector.DEFAULT_DESCRIPTION_BOOK)
    markets = [sector.build_market(raw, periods[0], 5, cutoff) for raw in raws]
    # Markets can legitimately have different latest sessions because of local
    # holidays.  Preserve each market's own as-of date instead of stopping the
    # whole daily build when, for example, Japan is closed while the US trades.
    market_dates = {m['key']: m['asOf'] for m in markets}
    market_date = max(market_dates.values())
    outputs, details = [], {}
    for period in periods:
        if period != periods[0]:
            markets = [sector.build_market(raw, period, 5, cutoff) for raw in raws]
        target = out/'Sector_Industry'/f'sector_{period}.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        text = sector.render_combined_html(markets, period, descriptions).replace('보고서', '표').replace('Key Findings', '산업그룹 상·하위 순위')
        target.write_text(text, encoding='utf-8')
        save_json(target.with_suffix('.json'), {'primary': period, 'requestedCutoff': cutoff.isoformat(), 'asOf': market_date, 'marketAsOf': market_dates, 'markets': sector.sanitize_for_json(markets)})
        outputs.append(target)
        details[period] = [{k: m[k] for k in ('key','asOf','periodStart','coverage','capCoverage','sessionDates','memberCount')} for m in markets]
    raw = ai_html.ai.load_spx([master])
    keep = [i for i, d in enumerate(raw.dates) if d <= cutoff]
    raw.dates = [raw.dates[i] for i in keep]
    raw.metrics = {key: value[:, keep] for key, value in raw.metrics.items()}
    data = ai_html.ai.build_data(raw)
    sp500_date = market_dates.get('SP500')
    if data['meta']['asOf'] != sp500_date:
        raise ValueError(f'AI와 S&P 500 섹터의 마지막 실제 거래일이 일치하지 않습니다: AI={data["meta"]["asOf"]}, SP500={sp500_date}')
    # The legacy AI builder clamps short windows to its first date. Mark those unavailable.
    dates = data['dates']
    for period in ai_html.PERIODS:
        enough = len(dates) >= (2 if period == '1D' else 6) if period in ('1D','5D') else dates[0] <= ai_html.ai.shift_months(datetime.fromisoformat(dates[-1]).date(), -int(period[:-1])).isoformat()
        if not enough:
            data['periodStarts'][period] = None
            data['benchmark']['returns'][period] = None
            for mode in data['modes'].values():
                for stage in mode.values():
                    for key in ('return','relative','breadth','median','dispersion'):
                        stage['performance'][period][key] = None
            for stock in data['stocks']:
                stock['returns'][period] = None
    for period in periods:
        if data['periodStarts'][period] is None:
            raise ValueError(f'AI {period} 계산에 필요한 거래일이 부족합니다.')
    data['meta']['requestedCutoff'] = cutoff.isoformat()
    save_json(out/'AI/ai_data.json', data)
    for period in periods:
        target = out/'AI'/f'ai_{period}.html'
        target.write_text(ai_html.render(data, period), encoding='utf-8')
        outputs.append(target)
    details['AI'] = {'asOf': data['meta']['asOf'], 'periodStarts': data['periodStarts'], 'stages': len(data['stages']), 'stocks': len(data['stocks'])}
    return outputs, details


def build_consensus(qae, inputs, out, observed_date):
    """Reuse the existing country parser/renderer with this run's exact raw files.

    Read the entire raw snapshot. Historical consensus pipelines remain separate;
    these outputs never overwrite their accumulated xlsx histories.
    """
    import pandas as pd
    outputs, meta = [], {}
    for key, code in (('growth','GDP'), ('inflation','CPI')):
        mod = load_module(qae/f'Consensus Builder/{code} consensus.py', 'daily_consensus_'+key)
        data = {}
        with pd.ExcelFile(inputs[key], engine='pyxlsb') as xl:
            missing = set(mod.EXCEL_FILES) - set(xl.sheet_names)
            if missing:
                raise ValueError(f'{code} 원본 필수 국가 시트 누락: {missing}')
            for sheet in mod.EXCEL_FILES:
                df = xl.parse(sheet, header=None)
                off = mod.detect_header_offset(df)
                ds = mod.parse_dates(df, off)
                # Keep headers, exclude future observations from a daily snapshot.
                good = ds[ds.notna() & (ds.dt.date <= observed_date)].index
                trimmed = pd.concat([df.iloc[:off], df.loc[good]], ignore_index=True)
                result = mod.extract_country(trimmed)
                if not result or not result.get('2w'):
                    raise ValueError(f'{code} {sheet}: 최신 컨센서스를 읽지 못했습니다.')
                data[sheet] = result
        target = out/'Consensus'/f'{key}.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        generated = datetime.now(KST).strftime('%Y-%m-%d %H:%M')
        target.write_text(mod.generate_html(data, generated), encoding='utf-8')
        years = mod.nest_flat_data(data)
        default_year = '2026' if '2026' in years else next(iter(years), '2026')
        bundle = {'data': years.get(default_year, {}), 'years': years,
                  'defaultYear': default_year, 'names': mod.COUNTRY_NAMES, 'generatedAt': generated,
                  'source': str(inputs[key]), 'sourceSHA256': digest(inputs[key]),
                  'history_scope': '이번 원본에 수록된 기간. 별도의 누적 컨센서스 이력은 변경하지 않음.'}
        save_json(target.with_suffix('.json'), bundle)
        outputs.append(target)
        meta[key] = {year: {country: d['2w'][-1]['date'] for country, d in values.items()}
                     for year, values in years.items()}
    return outputs, meta


def render_index(manifest, outputs, dest):
    esc = html.escape
    labels = {'sector_1D.html':'글로벌 섹터·산업 1D', 'sector_5D.html':'글로벌 섹터·산업 5D',
              'ai_1D.html':'AI 밸류체인 1D', 'ai_5D.html':'AI 밸류체인 5D',
              'growth.html':'GDP 컨센서스', 'inflation.html':'CPI 컨센서스', 'index.html':'경제지표 · 지표 요약과 IB 코멘트',
              'macro_views.html':'IB 거시 맥락 뷰 · Growth / Inflation / 통화정책'}
    links = ''.join(f'<li><a href="{esc(os.path.relpath(p,dest.parent).replace(os.sep,"/"))}">{labels[p.name]}</a></li>' for p in outputs)
    rows = ''.join(f'<tr><td>{esc(k)}</td><td>{esc(v["name"])}</td><td>{esc(v["modified"])}</td></tr>' for k,v in manifest['inputs'].items())
    page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>데일리 표 업데이트</title><style>body{{font:16px/1.7 "Malgun Gothic",sans-serif;margin:40px auto;padding:0 22px;max-width:1040px;color:#203a33;background:#f7f8f4}}a{{color:#24694c}}li{{margin:12px 0}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #d3dfd6;text-align:left}}.box{{background:white;padding:22px;border:1px solid #d3dfd6;border-radius:10px}}small{{color:#667970}}</style><h1>데일리 표 업데이트</h1><p>요청 시점 {esc(manifest['requested_at'])}<br>주가 기준일 {esc(manifest['markets']['AI']['asOf'])} · WECO 누적 실제값 {manifest['weco']['available_at_request']}건 (최신 원본 {manifest['weco'].get('latest_calendar_reported',manifest['weco']['available_at_request'])}건)</p><div class="box"><ul>{links}</ul></div><p>경제지표 메뉴에서 과거 실제값과 최신 캘린더를 함께 볼 수 있습니다. 해석은 숫자 스냅샷이 일치하는 경우에만 표시합니다.</p><p><a href="{esc(os.path.relpath(Path(manifest['review_queue']),dest.parent).replace(os.sep,'/'))}">해석 검토 대상 데이터</a></p><h2>이번에 읽은 원본</h2><table><tr><th>구분</th><th>파일</th><th>수정 시각</th></tr>{rows}</table><p><small>최신 원본은 표시된 기간의 수치를 갱신하며, 기간 밖의 과거 실제값은 누적 이력에서 불러옵니다. ECFC 화면의 과거 구간은 이번 원본 수록 범위이며 기존 누적 이력은 별도로 유지됩니다.</small></p></html>'''
    if manifest['weco'].get('authored_event_count'):
        intro = f"경제지표 {manifest['weco']['authored_event_count']}개에 핵심 요약과 해석을 작성했습니다. IB 원문 요약·비교 코멘트 {manifest['weco']['authored_house_count']}건을 함께 표시하며, 긴 원문과 검색 후보는 접어 두었습니다. IB 요약과 AI 해석 초안은 구분해서 표시합니다."
        page = page.replace('경제지표 메뉴에서 과거 실제값과 최신 캘린더를 함께 볼 수 있습니다. 해석은 숫자 스냅샷이 일치하는 경우에만 표시합니다.', intro+' 과거 실제값과 최신 캘린더를 함께 볼 수 있습니다.')
    if manifest['weco'].get('macro_views'):
        m=manifest['weco']['macro_views']
        context_note=f"<p><b>IB 거시 맥락 뷰</b> — 5개 IB의 성장·물가·통화정책을 별도로 비교합니다. 저장 뷰 {m['current_views']}건 · 저장 뷰 최신 기준일 {esc(m['latest_view_date'])}. 지표별 코멘트와 구분해 볼 수 있습니다.</p>"
        page=page.replace('<h2>이번에 읽은 원본</h2>',context_note+'<h2>이번에 읽은 원본</h2>')
    if manifest.get('weco_refreshed_at'):
        note = f'<p><b>IB 자료 갱신</b> {esc(manifest["weco_refreshed_at"])} · 보고서 최신 발행일 {esc(manifest["weco"]["source_date_max"])}</p>'
        page = page.replace('<h2>이번에 읽은 원본</h2>', note + '<h2>이번에 읽은 원본</h2>')
    dest.write_text(page, encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description='원본 4개 → AI·섹터·컨센서스 표 + WECO 기존 근거. 새 AI 해석 없음.')
    p.add_argument('--qae', type=Path, default=DEFAULT_QAE)
    p.add_argument('--raw-dir', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--calendar-code', type=Path)
    p.add_argument('--period', choices=('1D','5D','both'), default='1D')
    p.add_argument('--skip-master-update', action='store_true', help='원본 해시가 이미 처리된 경우에만 기존 Master 사용')
    p.add_argument('--check', action='store_true', help='원본 매칭만 확인; 쓰기·갱신 없음')
    p.add_argument('--open', action='store_true')
    args = p.parse_args()
    requested = datetime.now(KST)
    qae = args.qae.resolve(); daily = qae/'데일리시황'; bql = daily/'BQL'
    research = daily/'Context/_macro/Research_Context'
    root = (args.output or daily/'표_업데이트').resolve()
    inputs = discover(args.raw_dir or qae/'____Rawdata___')
    input_meta = {k: {'path':str(v),'name':v.name,'sha256':digest(v),'modified':datetime.fromtimestamp(v.stat().st_mtime,KST).isoformat(timespec='seconds')} for k,v in inputs.items()}
    if args.check:
        print(json.dumps(input_meta, ensure_ascii=False, indent=2));return
    root.mkdir(parents=True, exist_ok=True)
    # Exclusive lock prevents overlapping daily runs using this output directory.
    lock = root/'update.lock'
    handle = acquire_lock(lock)
    with handle:
        handle.write(str(os.getpid())); handle.flush()
        try:
            run = root/'runs'/requested.strftime('%Y%m%d_%H%M%S_%f')
            run.mkdir(parents=True)
            periods = ('1D','5D') if args.period == 'both' else (args.period,)
            with (run/'update.log').open('w', encoding='utf-8') as log:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    manifest = {'requested_at':requested.isoformat(timespec='seconds'), 'mode':'tables_and_existing_evidence', 'inputs':input_meta, 'new_ai_interpretations':False}
                    if args.skip_master_update:
                        processed = json.loads((bql/'Rawfile/rawfile_manifest.json').read_text(encoding='utf-8'))['processed']
                        if input_meta['bquant']['sha256'] not in processed:
                            raise ValueError('새 BQuant 원본이 아직 Master에 병합되지 않았습니다.')
                    else:
                        subprocess.run([sys.executable,'-X','utf8',str(bql/'Rawfile/update_master.py'),str(inputs['bquant']),'--no-rawdata'],check=True,stdout=log,stderr=log)
                    outputs, manifest['markets'] = build_market_tables(bql,run,requested.date()-timedelta(days=1),periods)
                    more, manifest['consensus'] = build_consensus(qae,inputs,run,requested.date());outputs+=more
                    cal = load_module(args.calendar_code or research/'ecocal_dashboard/build_dashboard.py', 'daily_ecocal')
                    calout = run/'WECO'
                    manifest['weco'] = cal.build(inputs['weco'],research,calout,requested.date().isoformat(),False,manifest['requested_at'])
                    payload = json.loads((calout/'dashboard_data.json').read_text(encoding='utf-8'))
                    current_events = [e for e in payload['events'] if e.get('record_origin')=='current']
                    previous = json.loads((root/'last_events.json').read_text(encoding='utf-8')) if (root/'last_events.json').exists() else []
                    queue = review_queue(current_events,previous,manifest['requested_at'])
                    queue_path = calout/'review_queue.json'
                    save_json(queue_path,{'requested_at':manifest['requested_at'],'mode':'pending_review','events':queue})
                    manifest['review_queue'] = str(queue_path)
                    manifest['queue_changes'] = {s:sum(e['change_status']==s for e in queue) for s in ('new_actual','revised','unchanged')}
                    outputs.append(calout/'index.html')
                    if manifest['weco'].get('macro_views'):outputs.append(calout/'macro_views.html')
                    # Fail without publishing latest if an input changed while it was being read.
                    for k,v in inputs.items():
                        if digest(v) != input_meta[k]['sha256']:
                            raise RuntimeError(f'실행 중 원본이 변경되었습니다: {v}. 다시 실행하세요.')
                    manifest['outputs'] = [str(v) for v in outputs]
                    save_json(run/'manifest.json',manifest)
                    render_index(manifest,outputs,run/'index.html')
                    render_index(manifest,outputs,root/'index.next.html')
                    history_path = research/'ecocal_dashboard/indicator_history.json'
                    history_next = history_path.with_suffix('.next.json')
                    archive = cal.indicator_history.updated(cal.indicator_history.read(history_path),current_events)
                    save_json(history_next,archive)
                    history_next.replace(history_path)
                    (root/'index.next.html').replace(root/'index.html')
                    save_json(root/'last_events.json',current_events)
                    save_json(root/'latest.json',manifest)
            print(json.dumps({'dashboard':str(root/'index.html'),'manifest':str(run/'manifest.json'),'as_of':manifest['markets']['AI']['asOf'],'weco_actuals':len(queue),'queue_changes':manifest['queue_changes']},ensure_ascii=False,indent=2))
            if args.open: os.startfile(root/'index.html')
        finally:
            handle.close()
            lock.unlink()


if __name__ == '__main__':
    main()
