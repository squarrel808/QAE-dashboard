"""Explicit period-end calendar for selected Haver UK rolling-quarter series.

Haver timestamps these series at the middle month of the published three-month
period. The model already shifts MGSX unemployment one month in core.prepare.
Employment and vacancies must use the same end-of-period convention.
This relabels observations; it does not impute or lag their economic reference.
"""
ALIGNMENTS={
    'g10:s112ele':{
        'shift_months':1,
        'note':'LFS 취업자: Haver 3개월 평균의 중앙월 → 기간말 월(+1개월)로 정렬. 예: Haver 2026-07의 34,577천명은 2026-06~08 평균.',
        'source':'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/employmentintheuk/october2026',
    },
    'uk:ap2y':{
        'shift_months':1,
        'note':'구인건수: Haver 3개월 평균의 중앙월 → 기간말 월(+1개월)로 정렬. 예: Haver 2026-08의 691천건은 2026-07~09 평균.',
        'source':'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/jobsandvacanciesintheuk/october2026',
    },
}

def align_uk_period_ends(wide,specs):
    for pk,rule in ALIGNMENTS.items():
        key='UK|'+pk
        if key not in specs:raise ValueError('Missing UK calendar input: '+pk)
        wide[pk]=wide[pk].shift(rule['shift_months'])
        series=wide[pk];s=specs[key]
        s.update(first=str(series.first_valid_index())[:10],last=str(series.last_valid_index())[:10],n=int(series.notna().sum()))
        s['note']=s.get('note','')+' | '+rule['note']
    return wide,specs
