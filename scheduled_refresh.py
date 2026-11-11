"""Refresh each MacroHub module independently and retain failed modules' published files."""
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import run_qae as runner
import deploy_check

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'macro_hub/public'
HELD_OUTPUTS = ('data/policy.json', 'embeds/policy.html')

# Module name, commands (relative path, optional arguments), published outputs, copies.
MODULES = [
 ('경제지표', [('경제지표가져오기/weco_dashboard.py',)], ['embeds/econ.html'], [('경제지표가져오기/dashboard.html','embeds/econ.html')]),
 ('Context Macro', [('macro_hub/scripts/sync_context_macro.py',)], ['embeds/context-macro.html','embeds/context-indicators.html'], []),
 ('실적 캘린더', [('releasecalendar/build_earnings_calendar.py',)], ['embeds/earnings.html'], [('releasecalendar/earnings_dashboard.html','embeds/earnings.html')]),
 ('Report', [('report_pipeline/parse_daily_docx.py',),('report_pipeline/build_reports_json.py',)], ['data/reports.json'], []),
 ('PCA I', [('haver/haver-api_PCA/fetch_haver_to_excel.py',),('PCA/pca_gdp.py',),('macro_hub/scripts/build_pca_json.py',)], ['data/pca.json','embeds/pca.html'], [('PCA/pca_dashboard.html','embeds/pca.html')]),
 ('CPI 분포', [('haver/haver-api_CPI/fetch_haver_to_excel.py',),('Consensus Builder/CPI distribution.py',)], ['data/cpi_analysis.json','embeds/cpi_dist.html'], [('Consensus Builder/cpi_dashboard.html','embeds/cpi_dist.html')]),
 ('Consensus', [('Consensus Builder/merge_xlsb_to_xlsx.py',),('Consensus Builder/CPI consensus.py',),('Consensus Builder/GDP consensus.py',),('macro_hub/scripts/build_consensus_json.py',)], ['data/consensus_cpi.json','data/consensus_gdp.json','embeds/consensus_cpi.html','embeds/consensus_gdp.html'], [('Consensus Builder/cpi_consensus_dashboard.html','embeds/consensus_cpi.html'),('Consensus Builder/gdp_consensus_dashboard.html','embeds/consensus_gdp.html')]),
 ('PCA II·III·국가별 경제지표', [('PCA/PCA_Four_Axis/run_update.py',),('macro_hub/scripts/sync_country_indicators.mjs',),('macro_hub/scripts/sync_pca_iii.mjs',)], ['embeds/gdp-weighted','embeds/pca-iii','embeds/country-indicators'], []),
 ('CAI', [('gs_api/build_cai_map.py',),('macro_hub/scripts/build_caimap_json.py',)], ['data/caimap.json','embeds/caimap.html'], [('gs_api/cai_map_dashboard.html','embeds/caimap.html')]),
 ('Surprise Index', [('데일리시황/표_업데이트/surprise index/update_surprise.py',)], ['embeds/surprise.html'], []),
 ('PMI', [('macro_hub/scripts/build_pmi.py',)], ['embeds/pmi.html'], []),
 ('Factor', [('macro_hub/scripts/build_pairbaskets_json.py',)], ['data/pairbaskets.json','data/major_factors.json'], []),
 ('Theme', [('macro_hub/scripts/refresh_theme.py',)], ['embeds/theme.html'], []),
 ('Market Rotation', [('데일리시황/BQL/Dashbaord/유로존_dashboard/build_market_rotation_dashboard.py',)], ['embeds/market_rotation.html'], []),
]


def snapshot(outputs, public=PUBLIC):
    saved = {}
    for relative in outputs:
        path = public / relative
        for file in path.rglob('*') if path.is_dir() else [path]:
            if file.is_file():
                saved[file.relative_to(public).as_posix()] = file.read_bytes()
    return saved


def restore(outputs, saved, public=PUBLIC):
    # Only delete newly created files inside explicitly owned output locations.
    current = snapshot(outputs, public)
    for relative in current.keys() - saved.keys():
        (public / relative).unlink()
    for relative, content in saved.items():
        target = public / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def command(run_id, relative, *args):
    path = ROOT / relative
    executable = shutil.which('node') if path.suffix == '.mjs' else sys.executable
    if not executable:
        raise RuntimeError('Node.js 실행 파일을 찾지 못했습니다')
    started = datetime.now()
    name = path.name
    runner.log(f'───── ▶ {name} 실행 시작 ─────')
    with open(runner.DAILY_LOG, 'a', encoding='utf8') as log:
        process = subprocess.Popen([executable, str(path), *args], cwd=path.parent,
                                   env=runner._child_env(), stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            # Stop only this owned process tree before restoring its published files.
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=log, stderr=subprocess.STDOUT, check=False)
            else:
                process.kill()
            process.wait()
            runner.append_step(run_id, name, started, datetime.now(), 124)
            raise RuntimeError(f'{name}: 30분 실행 제한 초과')
    result = subprocess.CompletedProcess(process.args, code)
    runner.append_step(run_id, name, started, datetime.now(), result.returncode)
    runner.log(f'───── ◀ {name} 종료 (exit={result.returncode}) ─────')
    if result.returncode:
        raise RuntimeError(f'{name} exit {result.returncode} — {runner.DAILY_LOG}')


def refresh_module(module, run_id, execute=command, public=PUBLIC):
    name, commands, outputs, copies = module
    saved = snapshot(outputs, public)
    try:
        for step in commands:
            execute(run_id, *step)
        for source, target in copies:
            destination = public / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, destination)
        for relative in outputs:
            path = public / relative
            if not path.exists():
                raise RuntimeError('산출물 누락: ' + relative)
            if path.suffix == '.json':
                json.loads(path.read_text(encoding='utf8'))
        if name == 'Report':
            deploy_check.validate_reports(ROOT)
        return {'name': name, 'status': 'updated', 'completedAt': datetime.now().isoformat(timespec='seconds')}
    except Exception as error:
        restore(outputs, saved, public)
        runner.log(f'{name} 실패 — 해당 화면 이전 게시본 보존: {error}')
        return {'name': name, 'status': 'failed', 'error': str(error)}


def main(argv):
    flags = {a.lstrip('/-').lower() for a in argv}
    chosen = next((a.split('=',1)[1].split(',') for a in argv if a.startswith('--modules=')), None)
    modules = [module for module in MODULES if chosen is None or module[0] in chosen]
    if chosen and len(modules) != len(chosen):
        raise ValueError('알 수 없는 모듈 선택')
    if 'dryrun' in flags:
        for name, steps, outputs, copies in modules:
            print(name, ' -> '.join(step[0] for step in steps), '=>', ', '.join(outputs))
        print('주간 시황: 작성된 public/weekly 파일 배포. 새 보고서 작성은 입력·검토가 필요합니다.')
        print('Policy Tone: 사용자 요청에 따라 실행 보류, 원인 점검만 수행.')
        print('하우스뷰: 앱 예약이 작성한 지표·IB 해석 화면을 함께 게시합니다.')
        return 0
    start = datetime.now()
    run_id = start.strftime('%Y%m%d_%H%M%S')
    runner.log(f'========== QAE 모듈별 갱신 시작 (run_id={run_id}) ==========')
    results = [refresh_module(module, run_id) for module in modules]
    status = {'runId': run_id, 'startedAt': start.isoformat(timespec='seconds'), 'modules': results,
              'held': {'Policy Tone': '사용자 요청 — 원인 확인만'},
              'houseViews': '앱 예약이 작성한 지표·IB 해석 화면 재사용',
              'fileDependent': ['주간 시황','실적 캘린더','경제지표 WECO','Consensus ECFC','Market Rotation BQuant']}
    failures = [{'security': item['name'], 'status': item['error']} for item in results if item['status'] == 'failed']
    send_result, send_flag, send_exit = 'SKIPPED', '0', 'NA'
    if 'nogit' not in flags and any(item['status'] == 'updated' for item in results):
        try:
            public_status = {**status, 'modules': [{key: value for key, value in item.items() if key != 'error'} for item in results]}
            (PUBLIC/'data/refresh_status.json').write_text(json.dumps(public_status,ensure_ascii=False,indent=2),'utf8')
            report_ok = any(item['name']=='Report' and item['status']=='updated' for item in results)
            marker = deploy_check.prepare(run_id, validate_reports_now=report_ok, excluded_paths=HELD_OUTPUTS)
            send_result, send_flag, send_exit, _ = runner.run_git(run_id, 'nopush' not in flags, False,
                excluded_paths=tuple('macro_hub/public/' + path for path in HELD_OUTPUTS))
            if send_result == 'FAILED':
                raise RuntimeError('GitHub 전송 실패')
            if send_result == 'SENT' and not deploy_check.verify(marker, log=runner.log):
                raise RuntimeError('실제 사이트 반영 확인 실패')
        except Exception as error:
            failures.append({'security':'전송·검증','status':str(error)})
            send_result='FAILED'
    end = datetime.now()
    status.update(finishedAt=end.isoformat(timespec='seconds'),sendResult=send_result)
    status_path=ROOT/'logs'/f'scheduled_{run_id}.json'
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2),'utf8')
    runner.append_failures(run_id,failures)
    runner.append_history(dict(run_id=run_id,start_time=start.strftime('%Y-%m-%d %H:%M:%S'),end_time=end.strftime('%Y-%m-%d %H:%M:%S'),duration_sec=int((end-start).total_seconds()),collect_result='FAILED' if failures else 'OK',collect_exit=len(failures),ok_count=sum(item['status']=='updated' for item in results),total_count=len(results),fail_count=len(failures),trade_date=end.strftime('%Y-%m-%d'),send_flag=send_flag,send_result=send_result,send_exit=send_exit,error=' / '.join(item['security']+': '+item['status'] for item in failures)))
    runner.log(f'모듈별 갱신 종료: {len(results)-sum(item["status"]=="failed" for item in results)}/{len(results)} · 전송 {send_result}')
    runner.refresh_dashboard()
    return 1 if failures else 0
