'use client'

import { useEffect, useState } from 'react'
import ChartImage from './EquityChartImage'
import { rankFactors, rankingRows } from '@/lib/equityFactors'
import type { Series } from '@/lib/types'

type FactorEntry = { country: string; factor: string; bbids: string[]; kind: string; note: string }
type MajorData = { checkedAt: string; catalog: FactorEntry[]; series: Series[] }
const COUNTRIES = [['US', '미국'], ['EU', '유럽'], ['JP', '일본'], ['CN', '중국'], ['KR', '한국'], ['TW', '대만'], ['HK', '홍콩'], ['GB', '영국'], ['AU', '호주'], ['CA', '캐나다']]
const FACTORS = ['Value', 'Momentum', 'Size', 'Volatility', 'Dividend', 'High Beta']
const PERIODS: [string, number][] = [['5D', -5], ['1M', 1], ['3M', 3], ['6M', 6], ['12M', 12], ['3Y', 36], ['5Y', 60], ['10Y', 120]]
const LABELS: Record<string, string> = { Value: '가치', Momentum: '모멘텀', Size: '규모', Volatility: '변동성', Dividend: '배당', 'High Beta': '고베타' }

export default function MajorFactors() {
  const [data, setData] = useState<MajorData | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [country, setCountry] = useState('US')
  const [period, setPeriod] = useState(12)
  useEffect(() => {
    const controller = new AbortController()
    setFailed(false)
    fetch('/data/major_factors.json', { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error('load failed'); return response.json() })
      .then(value => { if (!controller.signal.aborted) setData(value) })
      .catch(() => { if (!controller.signal.aborted) setFailed(true) })
    return () => controller.abort()
  }, [attempt])
  if (failed) return <div role="alert">국가별 팩터를 불러오지 못했습니다. <button className="underline" onClick={() => setAttempt(value => value + 1)}>다시 시도</button></div>
  if (!data) return <p role="status">국가별 주요 팩터를 불러오는 중입니다…</p>
  const byId = new Map(data.series.map(series => [series.bbid, series]))
  const selected = data.catalog.filter(entry => entry.country === country)
  const periodLabel = PERIODS.find(([, value]) => value === period)?.[0]
  const countryLabel = COUNTRIES.find(([code]) => code === country)?.[1]
  const freshnessDate = new Date(data.checkedAt).getTime() - 7 * 86400000
  const available = (entry: FactorEntry) => entry.bbids.map(id => byId.get(id)).filter((series): series is Series => !!series)

  return <section aria-label="국가별 주요 팩터" className="mb-6">
    <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
      <h2 className="serif text-xl">국가별 주요 팩터</h2>
      <label className="text-sm flex items-center gap-2">주요 팩터 기간
        <select aria-label="주요 팩터 기간" className="border rounded px-3 py-1.5 bg-white" value={period} onChange={event => setPeriod(+event.target.value)}>
          {PERIODS.map(([label, value]) => <option key={value} value={value}>{label}</option>)}
        </select>
    </label></div>
    <div className="overflow-x-auto border border-[var(--line)] rounded-xl bg-white mb-3">
      <table className="w-full text-sm text-center" aria-label="국가별 주요 팩터 제공 여부">
        <thead className="bg-[var(--head)]"><tr><th className="p-3 text-left">국가·지역</th>{FACTORS.map(factor => <th className="p-3 whitespace-nowrap" key={factor}>{factor}<span className="block text-xs font-normal text-[var(--muted)]">{LABELS[factor]}</span></th>)}</tr></thead>
        <tbody>{COUNTRIES.map(([code, label]) => <tr key={code} className={country === code ? 'bg-emerald-50' : ''}>
          <th className="p-2 text-left"><button className="underline underline-offset-4 whitespace-nowrap" aria-pressed={country === code} onClick={() => setCountry(code)}>{label}</button></th>
          {FACTORS.map(factor => {
            const entry = data.catalog.find(item => item.country === code && item.factor === factor)
            const histories = entry ? available(entry) : []
            const complete = entry && histories.length === entry.bbids.length
            const stale = histories.some(item => Date.parse(item.dates.at(-1) || '') < freshnessDate)
            return <td key={factor} className="p-2 border-t border-[var(--line)]" title={entry ? `${entry.note}\n${histories.map(item => `${item.bbid} · ${item.dates.at(-1)}`).join('\n')}` : '조회한 GS 바스켓 범위에서 계열 미확인'}>
              {complete ? <button onClick={() => setCountry(code)} className={stale ? 'text-amber-700' : 'text-emerald-800'}>{entry.kind === 'pair' ? '롱/숏' : entry.kind === 'legs' ? '양쪽 바스켓' : '바스켓'}{stale ? ' · 지연' : ''}</button> : <span className="text-[var(--muted)]">{entry ? '자료 미확보' : '미확인'}</span>}
            </td>
          })}
        </tr>)}</tbody>
      </table>
    </div>
    <p className="text-xs text-[var(--muted)] mb-4">GS 제공 목록 확인 {data.checkedAt.slice(0, 10)} · 롱/숏은 GS 페어 지수, 양쪽 바스켓은 고특성·저특성 각각의 가격 추이입니다. Volatility는 고변동성 / 저변동성 방향이며, 미확인은 조회한 GS 바스켓 범위 기준입니다.</p>
    <h3 className="serif text-lg mb-3">{countryLabel} · 주요 팩터 추이</h3>
    {!selected.length && <p className="p-4 border rounded bg-white">조회한 GS 바스켓 범위에서 해당 국가의 주요 팩터 계열을 확인하지 못했습니다.</p>}
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-3.5">
      {selected.map(entry => {
        const histories = available(entry)
        const ranking = rankFactors(histories, period)
        const chartSeries = histories.map((item, i) => ({ key: item.bbid, label: `${entry.kind === 'legs' ? (i === 0 ? '고특성' : '저특성') : entry.kind === 'pair' ? '롱/숏' : '바스켓'} · ${item.bbid}`, color: i === 0 ? '#2563a5' : '#bd6842' }))
        return <article key={entry.factor} className="rounded-xl border border-[var(--line)] bg-white p-4">
          <h4 className="font-semibold">{entry.factor} {LABELS[entry.factor] && `· ${LABELS[entry.factor]}`}</h4>
          <p className="text-xs text-[var(--muted)] my-1">{entry.note}</p>
          <p className="text-xs text-[var(--muted)]">{histories.map(item => `${item.bbid} · 최종 ${item.dates.at(-1)}`).join(' / ')}</p>
          {histories.length === entry.bbids.length && ranking.ranked.length === histories.length ? <ChartImage compact rows={rankingRows(ranking.ranked, ranking.start, ranking.end)} series={chartSeries} title={`${countryLabel} ${entry.factor} · ${periodLabel} · 시작값 100`} /> : <p className="py-12 text-center text-sm text-[var(--muted)]">선택 기간에 비교 가능한 자료가 부족합니다.</p>}
        </article>
      })}
    </div>
  </section>
}
