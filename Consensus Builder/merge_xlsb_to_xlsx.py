# -*- coding: utf-8 -*-
"""
ECFC Consensus xlsb -> xlsx 병합 스크립트
============================================
- 회사 PC에서 xlsb가 안 열리는 환경 우회용.
- xlsb에는 최근 약 60일치만 들어있고, xlsx에는 누적 시계열이 들어있음.
- 두 파일의 양식(시트명/헤더 R1~R13/티커 컬럼)이 동일하다는 전제 하에,
  xlsx의 마지막 유효 날짜 다음날부터의 xlsb 행만 이어붙여서
  새 파일 `ECFC_..._YYYYMMDD.xlsx`로 저장.

쉽게 비유:
- xlsx = 두꺼운 가계부 본책 (작년부터 쭉)
- xlsb = 최근 60일치 영수증 묶음
- 본책 맨 뒤 페이지(=마지막 기록일)부터 그 다음 날 영수증만 풀로 붙여 넣고,
  본책 이름을 오늘 날짜로 갈아서 새 카피본을 만든다.

사용법:
    python "merge_xlsb_to_xlsx.py"            # 오늘 날짜 사용
    python "merge_xlsb_to_xlsx.py" 20260519   # 명시적 날짜
"""

import os
import sys
from datetime import datetime, timedelta

from openpyxl import load_workbook
from pyxlsb import open_workbook as open_xlsb

# ============================================================
# CONFIG
# ============================================================
# 스크립트가 있는 폴더를 자동 기준으로 사용 (Windows/Linux 양쪽 모두 OK).
# 다른 폴더에서 돌리고 싶으면 환경변수 CONSENSUS_DIR로 override 가능.
BASE_DIR = os.environ.get(
    'CONSENSUS_DIR',
    os.path.dirname(os.path.abspath(__file__)),
)
HISTORY_DIR = os.path.join(BASE_DIR, 'history')

# (원본 xlsx, xlsb, 출력 파일 prefix). 모두 BASE_DIR 안에 있다고 가정.
TARGETS = [
    {
        'xlsx': 'ECFC_Growth Consesus_수정.xlsx',
        'xlsb': 'ECFC_Growth Consesus_수정.xlsb',
        'out_prefix': 'ECFC_Growth Consesus',
    },
    {
        'xlsx': 'ECFC_Inflation Consesus_수정.xlsx',
        'xlsb': 'ECFC_Inflation Consesus_수정.xlsb',
        'out_prefix': 'ECFC_Inflation Consesus',
    },
]

HEADER_ROWS = 13  # R14부터 실제 일자별 데이터가 시작
# ============================================================


def serial_to_datetime(value):
    """엑셀 시리얼 number -> datetime. datetime이면 그대로 반환."""
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime(1899, 12, 30) + timedelta(days=float(value))
    except (TypeError, ValueError):
        return None


def read_xlsb_sheet(xlsb_path, sheet_name):
    """xlsb의 한 시트를 2D list로 반환."""
    with open_xlsb(xlsb_path) as wb:
        with wb.get_sheet(sheet_name) as sh:
            return [[c.v for c in row] for row in sh.rows()]


def find_xlsx_last_data_row(ws, header_rows=HEADER_ROWS):
    """A열 기준으로 마지막 유효 데이터 행(1-indexed)을 반환."""
    last_row = header_rows
    for r in range(header_rows + 1, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v in (None, ''):
            # 다음 5행 연속 비면 종료 (단일 빈 행 방어)
            empty_run = True
            for rr in range(r, min(r + 5, ws.max_row + 1)):
                if ws.cell(rr, 1).value not in (None, ''):
                    empty_run = False
                    break
            if empty_run:
                break
            else:
                continue
        last_row = r
    return last_row


def find_last_data_col(ws, header_rows=HEADER_ROWS):
    """R12(티커 행 = header_rows-1) 기준으로 마지막 비어있지 않은 컬럼 인덱스."""
    ticker_row = header_rows - 1
    last_col = 1
    for c in range(2, ws.max_column + 1):
        if ws.cell(ticker_row, c).value not in (None, ''):
            last_col = c
    return max(last_col, 2)


def merge_one(target, out_date_str, base_dir=BASE_DIR, out_dir=HISTORY_DIR):
    xlsx_path = os.path.join(base_dir, target['xlsx'])
    xlsb_path = os.path.join(base_dir, target['xlsb'])
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, target['out_prefix'] + '_' + out_date_str + '.xlsx')

    if not os.path.exists(xlsx_path):
        raise FileNotFoundError(xlsx_path)
    if not os.path.exists(xlsb_path):
        raise FileNotFoundError(xlsb_path)

    print("[Load] " + os.path.basename(xlsx_path))
    wb = load_workbook(xlsx_path)

    total_appended = 0
    for sn in wb.sheetnames:
        ws = wb[sn]
        last_row = find_xlsx_last_data_row(ws)
        last_col = find_last_data_col(ws)

        last_date_raw = ws.cell(last_row, 1).value
        last_date = last_date_raw if isinstance(last_date_raw, datetime) else serial_to_datetime(last_date_raw)
        if last_date is None:
            print("  [" + sn + "] WARN: xlsx 마지막 날짜를 인식 못함. 스킵.")
            continue

        template_cells = [ws.cell(last_row, c) for c in range(1, last_col + 1)]

        try:
            xlsb_rows = read_xlsb_sheet(xlsb_path, sn)
        except Exception as e:
            print("  [" + sn + "] WARN: xlsb 시트 읽기 실패 (" + str(e) + "). 스킵.")
            continue

        data_block = xlsb_rows[HEADER_ROWS:]

        appended = 0
        new_row = last_row + 1
        for row_data in data_block:
            if not row_data:
                continue
            d_raw = row_data[0]
            if d_raw is None or d_raw == '':
                break
            d = d_raw if isinstance(d_raw, datetime) else serial_to_datetime(d_raw)
            if d is None:
                continue
            if d <= last_date:
                continue

            ws.cell(new_row, 1).value = d
            try:
                ws.cell(new_row, 1).number_format = template_cells[0].number_format
            except Exception:
                pass

            for c in range(2, last_col + 1):
                v = row_data[c - 1] if (c - 1) < len(row_data) else None
                ws.cell(new_row, c).value = v
                try:
                    ws.cell(new_row, c).number_format = template_cells[c - 1].number_format
                except Exception:
                    pass

            new_row += 1
            appended += 1

        total_appended += appended
        new_last = ws.cell(new_row - 1, 1).value if appended else last_date
        new_last_disp = new_last.date() if isinstance(new_last, datetime) else new_last
        print("  [" + sn + "] last_row=" + str(last_row) +
              " (" + str(last_date.date()) + ") -> +" + str(appended) +
              " rows, new last = " + str(new_last_disp))

    print("[Save] " + os.path.basename(out_path) + " (총 추가 행: " + str(total_appended) + ")")
    wb.save(out_path)
    return out_path


def main():
    if len(sys.argv) >= 2 and sys.argv[1].isdigit() and len(sys.argv[1]) == 8:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime('%Y%m%d')
    print("=== Output date suffix: " + date_str + " ===")

    outs = []
    for t in TARGETS:
        try:
            outs.append(merge_one(t, date_str))
        except Exception as e:
            print("!! 실패: " + t['xlsx'] + " -> " + str(e))

    print("\n=== Done ===")
    for o in outs:
        print("  - " + o)


if __name__ == '__main__':
    main()
