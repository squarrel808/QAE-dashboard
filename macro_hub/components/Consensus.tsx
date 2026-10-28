'use client'
import { useEffect, useRef, useState } from 'react'
import { buildRidgeState, drawRidge, drawMedian } from '@/lib/consensus-draw'
import type { ConsensusBundle, ConsensusCountry } from '@/lib/types'

// 6M median 구간 토글 옵션 (개월)
const ML_RANGES: [string, number][] = [['1M', 1], ['3M', 3], ['6M', 6], ['12M', 12], ['All', 999]]

// ml 시계열을 마지막 날짜 기준 최근 N개월로 자른다
function sliceMl(ml: ConsensusCountry['ml'], months: number) {
  if (!ml?.length || months >= 999) return ml
  const last = new Date(ml[ml.length - 1].d)
  const cut = new Date(last)
  cut.setMonth(cut.getMonth() - months)
  const cutStr = cut.toISOString().slice(0, 10)
  const out = ml.filter((p) => p.d >= cutStr)
  return out.length >= 2 ? out : ml.slice(-2)
}

export default function Consensus({ cpi, gdp }: { cpi: ConsensusBundle; gdp: ConsensusBundle }) {
  const [overview, setOverview] = useState(true)
  const [ds, setDs] = useState<'cpi' | 'gdp'>('cpi')
  const [year, setYear] = useState('2026')
  const [country, setCountry] = useState('ALL')
  const [mlMonths, setMlMonths] = useState(999)
  const hostRef = useRef<HTMLDivElement>(null)

  const bundle = ds === 'cpi' ? cpi : gdp
  const yearData = bundle.years && Object.keys(bundle.years).length
    ? bundle.years
    : { [bundle.defaultYear || '2026']: bundle.data || {} }
  const years = Object.keys(yearData).sort()
  const resolvedYear = yearData[year] ? year : (bundle.defaultYear || years[0] || '2026')
  const D = yearData[resolvedYear] || {}
  const NM = bundle.names || {}
  const countries = Object.keys(D)
  const visible = country === 'ALL' ? countries : countries.filter((c) => c === country)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    visible.forEach((c, i) => {
      const d = D[c]
      if (!d) return
      const st2 = buildRidgeState(d['2w'] || [], d.bw)
      const st6 = buildRidgeState(d['6m'] || [], d.bw)
      const sharedMaxY = Math.max(st2?.maxY || 0, st6?.maxY || 0, 1e-6)
      const a = host.querySelector<HTMLCanvasElement>(`canvas[data-ci="${i}"][data-k="a"]`)
      const b = host.querySelector<HTMLCanvasElement>(`canvas[data-ci="${i}"][data-k="b"]`)
      const m = host.querySelector<HTMLCanvasElement>(`canvas[data-ci="${i}"][data-k="m"]`)
      if (a && st2) drawRidge(a, st2, 185, sharedMaxY)
      if (b && st6) drawRidge(b, st6, 185, sharedMaxY)
      if (m) drawMedian(m, sliceMl(d.ml || [], mlMonths))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ds, country, bundle, mlMonths, resolvedYear, overview])

  const Panel = ({ label, control, children }: { label: string; control?: React.ReactNode; children: React.ReactNode }) => (
    <div className="flex-1 min-w-[500px] bg-white border border-[var(--line)] rounded-[10px] p-4">
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <div className="text-[15px] font-semibold uppercase tracking-wide">{label}</div>
        {control}
      </div>
      {children}
    </div>
  )

  const MlToggle = () => (
    <div className="flex gap-1">
      {ML_RANGES.map(([lab, mo]) => (
        <button key={mo} onClick={() => setMlMonths(mo)}
          className={'rounded-md border px-2 py-1 text-xs font-semibold ' +
            (mlMonths === mo ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white border-[var(--line)] hover:bg-[var(--head)]')}>
          {lab}
        </button>
      ))}
    </div>
  )

  return (
    <section>
      <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h2 className="serif text-[18px] m-0">{ds === 'cpi' ? `${resolvedYear} CPI consensus` : `${resolvedYear} GDP growth consensus`}</h2>
          <p className="text-xs text-[var(--muted)] mt-1">
            Distribution of broker forecasts{bundle.generatedAt ? ` · updated ${bundle.generatedAt}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {[true, false].map(all => <button key={String(all)} onClick={() => setOverview(all)} className={'rounded-lg border px-3 py-2 text-sm font-semibold ' + (overview === all ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white border-[var(--line)]')}>{all ? '전체 Heatmap' : '국가별'}</button>)}
          {!overview && <>
          <div className="flex gap-1">
            {years.map((y) => (
              <button key={y} onClick={() => { setYear(y); setCountry('ALL') }}
                className={'rounded-lg border px-3 py-2 text-sm font-semibold ' +
                  (resolvedYear === y ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white border-[var(--line)] hover:bg-[var(--head)]')}>
                {y}
              </button>
            ))}
          </div>
          <div className="flex gap-1">
            {(['cpi', 'gdp'] as const).map((t) => (
              <button key={t} onClick={() => { setDs(t); setCountry('ALL') }}
                className={'rounded-lg border px-3 py-2 text-sm font-semibold ' +
                  (ds === t ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white border-[var(--line)] hover:bg-[var(--head)]')}>
                {t.toUpperCase()}
              </button>
            ))}
          </div>
          <select value={country} onChange={(e) => setCountry(e.target.value)}
            className="bg-[var(--head)] border border-[var(--line)] rounded-lg px-4 py-2 text-sm font-medium">
            <option value="ALL">All countries</option>
            {countries.map((c) => <option key={c} value={c}>{(NM[c] || c)} ({c})</option>)}
          </select>
          </>}
        </div>
      </div>

      {overview ? <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2"><p className="text-xs text-[var(--muted)]">Consensus median (%) · blue = lower / red = higher within each panel · — = no data</p><MlToggle /></div>
        {(['2026', '2027']).flatMap(y => (['cpi', 'gdp'] as const).map(metric => {
          const source = metric === 'cpi' ? cpi : gdp
          const entries = source.years?.[y] || (source.defaultYear === y ? source.data : {})
          const countryKeys = Object.keys(entries)
          const sliced = countryKeys.map(id => ({ id, points: sliceMl(entries[id].ml || [], mlMonths) || [] }))
          const dates = Array.from(new Set(sliced.flatMap(r => r.points.map(p => p.d)))).sort()
          const values = sliced.flatMap(r => r.points.map(p => p.med)).filter(Number.isFinite)
          const lo = values.length ? Math.min(...values) : 0
          const hi = values.length ? Math.max(...values) : 0
          return <div key={`${y}-${metric}`} className="rounded-xl border border-[var(--line)] bg-white p-4">
            <h3 className="serif text-base mb-3">{y} {metric.toUpperCase()} consensus · Median (%)</h3>
            {!dates.length ? <p className="text-xs text-[var(--muted)]">No data</p> : <div className="overflow-x-auto"><table style={{ borderCollapse: 'separate', borderSpacing: 2, fontSize: 11, width: '100%' }}>
              <thead><tr><th className="sticky left-0 bg-white">Country</th>{dates.map(d => <th key={d} className="whitespace-nowrap font-normal px-1">{d.slice(2)}</th>)}</tr></thead>
              <tbody>{sliced.map(row => { const lookup = new Map(row.points.map(p => [p.d, p.med])); return <tr key={row.id}><th scope="row" className="sticky left-0 bg-white whitespace-nowrap text-left pr-3">{source.names?.[row.id] || row.id}</th>{dates.map(d => {
                const v = lookup.get(d)
                const valid = v != null && Number.isFinite(v)
                const t = valid && hi > lo ? (v - lo) / (hi - lo) : 0.5
                const hue = t < 0.5 ? 215 : 5
                const light = 96 - Math.abs(t - 0.5) * 68
                return <td key={d} title={`${source.names?.[row.id] || row.id} · ${d}: ${valid ? v.toFixed(2) + '%' : 'No data'}`} style={{ background: valid ? `hsl(${hue} 60% ${light}%)` : '#f4f3f1', color: valid && light < 55 ? '#fff' : '#222', minWidth: 46, padding: '7px 4px', textAlign: 'center', borderRadius: 3 }}>{valid ? v.toFixed(2) : '—'}</td>
              })}</tr> })}</tbody>
            </table></div>}
          </div>
        }))}
      </div> : <div ref={hostRef}>
        {visible.map((c, i) => {
          const d = D[c]
          const lastN = d?.['2w']?.length ? d['2w'][d['2w'].length - 1].values.length : 0
          return (
            <div key={c} className="mb-7">
              <div className="serif text-base font-semibold mb-2">{(NM[c] || c)} ({c})</div>
              <div className="flex gap-3 flex-wrap">
                <Panel label={`2W chg (daily) · #${lastN}`}><canvas data-ci={i} data-k="a" className="w-full h-auto" /></Panel>
                <Panel label="6M chg (bi-weekly)"><canvas data-ci={i} data-k="b" className="w-full h-auto" /></Panel>
                <Panel label="Median + IQR (daily)" control={<MlToggle />}><canvas data-ci={i} data-k="m" className="w-full h-auto" /></Panel>
              </div>
            </div>
          )
        })}
      </div>}
    </section>
  )
}
