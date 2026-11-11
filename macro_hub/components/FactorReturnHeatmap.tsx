'use client'
import { useMemo, useState } from 'react'
import type { Series } from '@/lib/types'
import { factorReturns } from '@/lib/factorHeatmap'

export default function FactorReturnHeatmap({ series, frequency, country }: { series: Series[]; frequency: 'daily' | 'monthly'; country: string }) {
  const daily = frequency === 'daily'
  const title = daily ? 'Daily' : 'Monthly'
  const [window, setWindow] = useState(daily ? 20 : 12)
  const [selectedEnd, setSelectedEnd] = useState('')
  const dates = useMemo(() => [...new Set(series.flatMap(s => s.dates))].sort(), [series])
  const end = selectedEnd && selectedEnd <= (dates.at(-1) || '') ? selectedEnd : dates.at(-1) || ''
  const data = useMemo(() => factorReturns(series, frequency, end), [series, frequency, end])
  const offset = window ? Math.max(0, data.columns.length - window) : 0
  const columns = data.columns.slice(offset)
  return <article className="rounded-xl border border-[var(--line)] bg-white p-4 mb-4" aria-label={`${title} 팩터 히트맵`}>
    <div className="flex flex-wrap justify-between items-center gap-3 mb-3">
      <h3 className="serif text-lg">{country} · FACTOR {title} 수익률 (%)</h3>
      <div className="flex flex-wrap gap-3 text-sm">
        <label>기간 <select aria-label={`${title} 히트맵 기간`} value={window} onChange={e => setWindow(+e.target.value)} className="border rounded p-1.5 bg-white">
          {(daily ? [5, 10, 20, 60, 120] : [6, 12, 24, 36, 60, 120]).map(n => <option key={n} value={n}>{n}{daily ? '거래일' : '개월'}</option>)}
        </select></label>
        <label>기준일 <input type="date" aria-label={`${title} 히트맵 기준일`} min={dates[0]} max={dates.at(-1)} value={end} onChange={e => setSelectedEnd(e.target.value)} className="border rounded p-1.5" /></label>
        <button className="underline" onClick={() => setSelectedEnd('')}>최신</button>
      </div>
    </div>
    <p className="text-xs text-[var(--muted)] mb-3">{daily ? '전 거래일 대비 수익률' : '전월 말 대비 수익률 · 마지막 표시 월은 기준일까지의 MTD'} · 녹색 + / 적색 − · 회색은 비교 자료 없음 · 고특성·저특성 바스켓은 각각 표시</p>
    <div className="overflow-x-auto max-h-[640px]">
      <table className="border-separate border-spacing-1 text-xs w-full" aria-label={`${title} 팩터 수익률`}>
        <thead><tr><th className="sticky left-0 bg-white z-10 text-left min-w-52">팩터 / 바스켓</th>{columns.map(c => <th className="min-w-20 font-medium" key={c}>{c}{!daily && c === data.latest.slice(0, 7) ? ' (MTD)' : ''}</th>)}</tr></thead>
        <tbody>{series.map((s, row) => <tr key={s.bbid}><th className="sticky left-0 bg-white z-10 text-left font-medium whitespace-nowrap p-2" title={s.bbid}>{s.label}</th>{columns.map((c, col) => {
          const value = data.values[row][offset + col]
          const color = value == null ? '#eef1f0' : `rgba(${value >= 0 ? '37,136,117' : '198,95,81'},${.06 + .62 * Math.min(1, Math.abs(value) / (daily ? .02 : .08))})`
          return <td className="text-center rounded p-2 tabular-nums" style={{ background: color }} key={c} title={`${s.label} · ${c} · ${value == null ? '비교 자료 없음' : (value * 100).toFixed(3) + '%'}`}>{value == null ? '—' : `${value > 0 ? '+' : ''}${(value * 100).toFixed(2)}`}</td>
        })}</tr>)}</tbody>
      </table>
      {!series.length && <p className="p-4">해당 국가의 팩터 자료가 없습니다.</p>}
    </div>
  </article>
}
