'use client'
import { useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import type { PairBasketsData, Series, SectorItem } from '@/lib/types'

const PALETTE = ['#378ADD', '#1D9E75', '#BA7517', '#D4537E', '#9b8cff', '#46b0c9', '#e0833b', '#cf5fd0', '#6fcf6f', '#d24b4a']
const RANGES: [string, number][] = [['1M', 1], ['3M', 3], ['6M', 6], ['12M', 12], ['2Y', 24], ['3Y', 36], ['5Y', 60], ['10Y', 120]]
const POS = '#1a7a4c', NEG = '#c0392b'

// m개월 수익률: 마지막 값 / m개월 전 값 - 1
function chgN(close: number[], m: number): number | null {
  const n = close.length
  if (n < 2) return null
  let bi = n - 1 - m
  if (bi < 0) bi = 0
  const a = close[bi], z = close[n - 1]
  return a && z != null && a !== 0 ? z / a - 1 : null
}

// 초록(+)/빨강(-) 히트맵 색 — scale 기준으로 정규화
function heatColor(pct: number | null, scale = 0.08): string {
  if (pct == null || isNaN(pct)) return '#f4f3f1'
  const t = Math.max(-1, Math.min(1, pct / scale))
  const lerp = (a: number, b: number, x: number) => Math.round(a + (b - a) * x)
  if (t >= 0) {
    return `rgb(${lerp(238, 26, t)},${lerp(243, 122, t)},${lerp(239, 76, t)})`
  }
  return `rgb(${lerp(247, 192, -t)},${lerp(238, 57, -t)},${lerp(236, 59, -t)})`
}

export default function EquityFactors({ data }: { data: PairBasketsData }) {
  const realSectors = useMemo(
    () => [...new Set((data.sector?.sectors || []).filter((s) => !/^VIP vs Short/.test(s)))],
    [data]
  )
  const factors = useMemo(
    () => [...new Set((data.sector?.factors || []).filter((f) => f !== 'HF Positioning'))],
    [data]
  )

  // universe: 있으면 그대로, 없으면 groups + sector 로 대체 (원본 HTML과 동일한 fallback)
  const universe: Series[] = useMemo(() => {
    if (data.universe?.length) return data.universe
    const out: Series[] = []
    const seen = new Set<string>()
    Object.values(data.groups || {}).forEach((arr) =>
      arr.forEach((p) => { if (!seen.has(p.bbid)) { seen.add(p.bbid); out.push(p) } })
    )
    ;(data.sector?.items || []).forEach((it) => {
      if (/^VIP vs Short/.test(it.sector) || it.factor === 'HF Positioning') return
      if (!seen.has(it.bbid)) { seen.add(it.bbid); out.push({ ...it, label: `${it.sector} · ${it.factor}` }) }
    })
    return out
  }, [data])

  const [rHeat, setRHeat] = useState(3)
  const [sector, setSector] = useState(realSectors[0] || '')
  const [rLines, setRLines] = useState(36)
  const [rTop, setRTop] = useState(12)

  // ── 히트맵 셀 조회
  const cell = (sec: string, fac: string): number | null => {
    const it = data.sector.items.find((x) => x.sector === sec && x.factor === fac)
    return it ? chgN(it.close, rHeat) : null
  }

  // ── 라인차트용: 선택 섹터의 팩터별 100-리베이스 시계열
  const lineData = useMemo(() => {
    const its = data.sector.items.filter((x) => x.sector === sector)
    const allMonths = Array.from(new Set(its.flatMap((it) => it.dates))).sort()
    const months = allMonths.slice(-(rLines + 1))
    return months.map((mo) => {
      const row: Record<string, number | string | null> = { month: mo }
      its.forEach((it) => {
        const idx = it.dates.indexOf(it.dates.filter((d) => d <= mo).slice(-1)[0])
        const baseIdx = it.dates.indexOf(months[0])
        const base = baseIdx >= 0 ? it.close[baseIdx] : it.close[0]
        row[it.factor] = idx >= 0 && base ? +(it.close[idx] / base * 100).toFixed(1) : null
      })
      return row
    })
  }, [data, sector, rLines])

  const sectorFactors = useMemo(
    () => [...new Set(data.sector.items.filter((x) => x.sector === sector).map((x) => x.factor))],
    [data, sector]
  )

  // ── TOP/BOTTOM 랭킹
  const ranked = useMemo(() => {
    return universe
      .map((p) => ({ label: p.label, v: chgN(p.close, rTop) }))
      .filter((r): r is { label: string; v: number } => r.v != null)
      .sort((a, b) => b.v - a.v)
  }, [universe, rTop])
  const top10 = ranked.slice(0, 10)
  const bottom10 = ranked.slice(-10).reverse()

  const Sel = ({ value, onChange }: { value: number; onChange: (n: number) => void }) => (
    <select
      value={value}
      onChange={(e) => onChange(+e.target.value)}
      className="bg-white border border-[var(--line)] rounded-md px-2 py-1 text-xs"
    >
      {RANGES.map(([lab, m]) => <option key={m} value={m}>{lab}</option>)}
    </select>
  )

  const Bars = ({ rows }: { rows: { label: string; v: number }[] }) => {
    const mx = Math.max(...rows.map((r) => Math.abs(r.v)), 0.0001)
    return (
      <div className="flex flex-col gap-1.5">
        {rows.map((r, i) => {
          const w = (Math.abs(r.v) / mx) * 50
          const col = r.v >= 0 ? POS : NEG
          return (
            <div key={`${r.label}-${i}`} className="grid items-center gap-2 text-xs" style={{ gridTemplateColumns: '230px 1fr 60px' }}>
              <span className="text-right text-[var(--muted)] truncate">{r.label}</span>
              <span className="relative h-3.5">
                <span className="absolute left-1/2 top-0 bottom-0 w-px bg-[var(--line)]" />
                <span className="absolute top-0.5 h-2.5 rounded-sm" style={{ background: col, ...(r.v >= 0 ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }) }} />
              </span>
              <span className="text-right" style={{ color: col }}>{r.v >= 0 ? '+' : ''}{(r.v * 100).toFixed(1)}%</span>
            </div>
          )
        })}
      </div>
    )
  }

  const Card = ({ title, control, children }: { title: string; control?: React.ReactNode; children: React.ReactNode }) => (
    <div className="rounded-xl border border-[var(--line)] bg-white p-3.5 mb-3.5">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2.5">
        <h2 className="serif text-[15px] m-0">{title}</h2>
        {control}
      </div>
      {children}
    </div>
  )

  return (
    <section>
      <h2 className="serif text-[15px] mb-3.5">Equity Factors · GS Pair Baskets</h2>

      <Card title="① 섹터 × 팩터 · 수익률(%)" control={<Sel value={rHeat} onChange={setRHeat} />}>
        <div className="overflow-x-auto">
          <table className="border-separate text-[11px] w-full" style={{ borderSpacing: 2 }}>
            <thead>
              <tr>
                <th></th>
                {factors.map((f) => <th key={f} className="text-[var(--muted)] font-semibold px-1 whitespace-nowrap">{f}</th>)}
              </tr>
            </thead>
            <tbody>
              {realSectors.map((sec) => (
                <tr key={sec}>
                  <td className="text-left px-2 whitespace-nowrap">{sec}</td>
                  {factors.map((f) => {
                    const pc = cell(sec, f)
                    return (
                      <td key={f} className="text-center">
                        <span className="block py-1.5 rounded font-bold" style={{ background: heatColor(pc), minWidth: 26 }}>
                          {pc == null ? '' : (pc * 100).toFixed(0)}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        title="② 섹터별 팩터 추이 · 100 리베이스"
        control={
          <span className="flex items-center gap-2">
            <select value={sector} onChange={(e) => setSector(e.target.value)} className="bg-white border border-[var(--line)] rounded-md px-2 py-1 text-xs">
              {realSectors.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <Sel value={rLines} onChange={setRLines} />
          </span>
        }
      >
        <div style={{ height: 300 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={lineData} margin={{ top: 6, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#5a5f66' }} minTickGap={32} />
              <YAxis tick={{ fontSize: 10, fill: '#5a5f66' }} domain={['auto', 'auto']} />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              {sectorFactors.map((f, i) => (
                <Line key={f} type="monotone" dataKey={f} stroke={PALETTE[i % PALETTE.length]} strokeWidth={1.5} dot={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-3.5" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
        <Card title="③ 수익률 TOP10" control={<Sel value={rTop} onChange={setRTop} />}>
          <Bars rows={top10} />
        </Card>
        <Card title="④ 수익률 BOTTOM10" control={<span className="text-xs text-[var(--muted)]">③ 기간 연동</span>}>
          <Bars rows={bottom10} />
        </Card>
      </div>

      <p className="text-[11px] text-[var(--muted)] mt-2">
        데이터: GS Marquee PAIR_BASKETS_LEVELS (월별){data.generatedAt ? ` · 생성 ${data.generatedAt}` : ''}
      </p>
    </section>
  )
}
