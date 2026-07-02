'use client'
import { useMemo, useState } from 'react'
import {
  ComposedChart, Bar, Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import type { CaiMapData, CaiSeries } from '@/lib/types'

const SCOL: Record<string, string> = { Consumer: '#378ADD', Housing: '#1D9E75', Labor: '#BA7517', Manufacturing: '#D4537E', Other: '#888780' }
const TCOL: Record<string, string> = { Hard: '#378ADD', Soft: '#BA7517' }
const RANGES: [string, number][] = [['1Y', 12], ['2Y', 24], ['3Y', 36], ['5Y', 60], ['10Y', 120], ['All', 9999]]

function cutoffDate(last: string, months: number) {
  const d = new Date(last)
  d.setMonth(d.getMonth() - months)
  return d.toISOString().slice(0, 10)
}

// ── 히트맵 색상: 부호=색(초록 확장/빨강 둔화), 크기=진하기(화면 내 최대값 기준, sqrt로 저강도 강조) ──
const NEUTRAL = [244, 243, 241], C_GREEN = [26, 122, 76], C_RED = [192, 57, 43]
function mix(a: number[], b: number[], t: number) {
  return [Math.round(a[0] + (b[0] - a[0]) * t), Math.round(a[1] + (b[1] - a[1]) * t), Math.round(a[2] + (b[2] - a[2]) * t)]
}
function heatColor(v: number | null | undefined, maxAbs: number) {
  if (v == null || !maxAbs) return { bg: '#f4f3f1', fg: '#9aa0a6' }
  const t = Math.sqrt(Math.min(1, Math.abs(v) / maxAbs))
  const c = mix(NEUTRAL, v >= 0 ? C_GREEN : C_RED, t)
  const lum = (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255
  return { bg: `rgb(${c[0]},${c[1]},${c[2]})`, fg: lum > 0.55 ? '#14181f' : '#fff' }
}

export default function CaiMap({ data }: { data: CaiMapData }) {
  const [view, setView] = useState<'cai' | 'map'>('cai')
  const [months, setMonths] = useState(60)
  const pool = view === 'cai' ? data.cai : data.map
  const available = data.countries.filter((c) => pool[c.id])
  const [country, setCountry] = useState('US')

  const series: CaiSeries | undefined = pool[country] || pool[available[0]?.id]
  const activeId = pool[country] ? country : available[0]?.id

  const { rows, sectorKeys, typeRows, typeKeys } = useMemo(() => {
    if (!series) return { rows: [], sectorKeys: [], typeRows: [], typeKeys: [] }
    const last = series.dates[series.dates.length - 1]
    const cut = months >= 9999 ? '0000' : cutoffDate(last, months)
    const sk = Object.keys(series.sectors)
    const tk = series.types ? Object.keys(series.types) : []
    const rows: Record<string, number | string | null>[] = []
    const typeRows: Record<string, number | string | null>[] = []
    series.dates.forEach((d, i) => {
      if (d < cut) return
      const r: Record<string, number | string | null> = { date: d, headline: series.headline[i] }
      sk.forEach((s) => { r[s] = series.sectors[s][i] })
      rows.push(r)
      if (tk.length) {
        const tr: Record<string, number | string | null> = { date: d }
        tk.forEach((t) => { tr[t] = series.types![t][i] })
        typeRows.push(tr)
      }
    })
    return { rows, sectorKeys: sk, typeRows, typeKeys: tk }
  }, [series, months])

  // ── 섹터 히트맵 (CAI_HEATMAP_SECTOR_*) — 막대와 Hard/Soft 사이에 표시 ──
  const heat = useMemo(() => {
    if (!series || !series.heatmap) return null
    const last = series.dates[series.dates.length - 1]
    const cut = months >= 9999 ? '0000' : cutoffDate(last, months)
    const idx: number[] = []
    series.dates.forEach((d, i) => { if (d >= cut) idx.push(i) })
    const keys = data.sectors.filter((s) => series.heatmap![s])   // 섹터 순서 유지
    if (!keys.length || !idx.length) return null
    const dates = idx.map((i) => series.dates[i])
    let maxAbs = 0
    const matrix: Record<string, (number | null)[]> = {}
    keys.forEach((s) => {
      const vals = idx.map((i) => series.heatmap![s][i] ?? null)
      vals.forEach((v) => { if (v != null) maxAbs = Math.max(maxAbs, Math.abs(v)) })
      matrix[s] = vals
    })
    return { dates, keys, matrix, maxAbs: maxAbs || 1 }
  }, [series, months, data.sectors])

  const Btn = ({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) => (
    <button onClick={onClick}
      className={'rounded-md border px-3 py-1.5 text-xs font-semibold ' +
        (on ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white border-[var(--line)] hover:bg-[var(--head)]')}>
      {children}
    </button>
  )
  const axis = { tick: { fontSize: 10, fill: '#5a5f66' }, minTickGap: 28 } as const
  const label = data.countries.find((c) => c.id === activeId)?.label || activeId

  return (
    <section>
      <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h2 className="serif text-[18px] m-0">CAI · MAP — {label}</h2>
          <p className="text-xs text-[var(--muted)] mt-1">
            {view === 'cai' ? 'Current Activity Indicator (월별)' : 'MAP (일별)'} · 막대/선에 마우스를 올리면 값 표시
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex gap-1">
            <Btn on={view === 'cai'} onClick={() => setView('cai')}>CAI</Btn>
            <Btn on={view === 'map'} onClick={() => setView('map')}>MAP</Btn>
          </div>
          <select value={activeId} onChange={(e) => setCountry(e.target.value)}
            className="bg-[var(--head)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-medium">
            {available.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
          <div className="flex gap-1">{RANGES.map(([lab, m]) => <Btn key={m} on={months === m} onClick={() => setMonths(m)}>{lab}</Btn>)}</div>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--line)] bg-white p-3.5 mb-3.5">
        <h3 className="serif text-[15px] mb-2.5">Headline + 섹터 기여도</h3>
        <div style={{ height: 340 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 6, right: 12, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
              <XAxis dataKey="date" {...axis} />
              <YAxis tick={axis.tick} />
              <ReferenceLine y={0} stroke="rgba(0,0,0,.25)" />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {sectorKeys.map((s) => <Bar key={s} dataKey={s} stackId="s" fill={SCOL[s] || '#9aa0a6'} />)}
              <Line type="monotone" dataKey="headline" stroke="#1a1c1f" strokeWidth={1.8} dot={false} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {heat && (
        <div className="rounded-xl border border-[var(--line)] bg-white p-3.5 mb-3.5">
          <h3 className="serif text-[15px] mb-2.5">섹터 히트맵 (CAI_HEATMAP_SECTOR · 초록=확장 / 빨강=둔화)</h3>
          <div className="overflow-x-auto">
            <table className="border-separate" style={{ borderSpacing: 2, fontSize: 11, width: '100%' }}>
              <thead>
                <tr>
                  <th></th>
                  {heat.dates.map((d) => (
                    <th key={d} className="font-normal text-[var(--muted)] px-1 text-center whitespace-nowrap">{d.slice(2, 7)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heat.keys.map((s) => (
                  <tr key={s}>
                    <td className="text-left pr-2.5 font-medium whitespace-nowrap">{s}</td>
                    {heat.matrix[s].map((v, i) => {
                      const c = heatColor(v, heat.maxAbs)
                      return (
                        <td key={i} className="p-0 text-center">
                          <span className="block rounded px-1.5 py-1.5 font-semibold" style={{ background: c.bg, color: c.fg, minWidth: 30 }}>
                            {v == null ? '' : v.toFixed(1)}
                          </span>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-2 mt-2 text-[11px] text-[var(--muted)]">
            <span>둔화</span>
            <span style={{ display: 'inline-block', width: 160, height: 10, borderRadius: 3, background: 'linear-gradient(to right,#c0392b,#f4f3f1,#1a7a4c)' }} />
            <span>확장</span>
            <span className="ml-1">진하기 = 화면 내 상대 강도</span>
          </div>
        </div>
      )}

      {typeKeys.length > 0 && (
        <div className="rounded-xl border border-[var(--line)] bg-white p-3.5">
          <h3 className="serif text-[15px] mb-2.5">Hard vs Soft</h3>
          <div style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={typeRows} margin={{ top: 6, right: 12, left: -10, bottom: 0 }}>
                <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
                <XAxis dataKey="date" {...axis} />
                <YAxis tick={axis.tick} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,.25)" />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {typeKeys.map((t) => <Line key={t} type="monotone" dataKey={t} stroke={TCOL[t] || '#9aa0a6'} strokeWidth={1.6} dot={false} connectNulls />)}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  )
}
