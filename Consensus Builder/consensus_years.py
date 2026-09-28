# -*- coding: utf-8 -*-
"""Shared helpers for multi-year ECFC consensus workbooks."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping

from pyxlsb import open_workbook as open_xlsb


COUNTRIES = ('미국', '영국', '일본', '독일', '프랑스', '호주', '중국', '캐나다')
COUNTRY_NAMES = {
    '미국': 'US', '영국': 'UK', '일본': 'JP', '독일': 'DE',
    '프랑스': 'FR', '호주': 'AU', '중국': 'CN', '캐나다': 'CA',
}
YEAR_SUFFIXES = {'2026': '26', '2027': '27'}
SOURCE_PREFIXES = {
    'growth': ('ECFC_Growth_Consensus', 'ECFC_Growth Consesus'),
    'inflation': ('ECFC_Inflation_Consensus', 'ECFC_Inflation Consesus'),
}


def _rawdata_module():
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_dir not in sys.path:
        sys.path.insert(0, repo_dir)
    import rawdata
    return rawdata


def find_source(kind: str, fallback: str, extra_dirs=()) -> str:
    """Prefer the newest matching raw xlsb, retaining the accumulated xlsx fallback."""
    rawdata = _rawdata_module()
    hit = rawdata.find_any(SOURCE_PREFIXES[kind], exts=('.xlsb',), extra_dirs=extra_dirs)
    return hit or fallback


def workbook_sheet_names(path: str) -> list[str]:
    if path.lower().endswith('.xlsb'):
        with open_xlsb(path) as wb:
            return list(wb.sheets)
    import pandas as pd
    with pd.ExcelFile(path) as xl:
        return list(xl.sheet_names)


def sheet_file_map(path: str) -> dict[str, str]:
    """Map source sheet names to a file, supporting country, country26 and country27."""
    names = set(workbook_sheet_names(path))
    mapped = {}
    for year, suffix in YEAR_SUFFIXES.items():
        for country in COUNTRIES:
            sheet = f'{country}{suffix}'
            if sheet in names:
                mapped[sheet] = path
    if mapped:
        return mapped
    return {country: path for country in COUNTRIES if country in names}


def split_sheet_name(sheet: str) -> tuple[str, str]:
    """Return (four-digit year, country) for old and new ECFC sheet names."""
    for year, suffix in YEAR_SUFFIXES.items():
        if sheet.endswith(suffix) and sheet[:-len(suffix)] in COUNTRIES:
            return year, sheet[:-len(suffix)]
    return '2026', sheet


def nest_flat_data(flat: Mapping[str, object]) -> dict[str, dict[str, object]]:
    years: dict[str, dict[str, object]] = {}
    for sheet, value in flat.items():
        year, country = split_sheet_name(sheet)
        if country not in COUNTRIES:
            continue
        years.setdefault(year, {})[country] = value
    return {
        year: {country: values[country] for country in COUNTRIES if country in values}
        for year, values in sorted(years.items())
    }


def source_sheet_for_country(country: str, available: set[str], year: str = '2026') -> str | None:
    """Resolve an old unsuffixed sheet or the requested year's suffixed sheet."""
    if country in available:
        return country
    candidate = f"{country}{YEAR_SUFFIXES[year]}"
    return candidate if candidate in available else None
