'use client'
import { useMemo, useState } from 'react'
import ChartImage from './EquityChartImage'
import { rankFactors, rankingRows } from '@/lib/equityFactors'
import MajorFactors from './MajorFactors'
import type { PairBasketsData, Series } from '@/lib/types'

const PALETTE = ['#378ADD', '#1D9E75', '#BA7517', '#D4537E', '#9b8cff', '#46b0c9', '#e0833b', '#cf5fd0', '#6fcf6f', '#d24b4a']
const RANGES: [string, number][] = [['1M', 1], ['3M', 3], ['6M', 6], ['12M', 12], ['2Y', 24], ['3Y', 36], ['5Y', 60], ['10Y', 120]]
const POS = '#1a7a4c', NEG = '#c0392b'

// Calendar periods remain valid for both daily and legacy monthly observations.
function cutoff(end: string, months: number): string {
  const d = new Date(end.length === 7 ? `${end}-01T00:00:00Z` : `${end}T00:00:00Z`)
  const day = d.getUTCDate()
  d.setUTCDate(1)
  d.setUTCMonth(d.getUTCMonth() - months)
  const last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate()
  d.setUTCDate(Math.min(day, last))
  return d.toISOString().slice(0, end.length)
}
function windowDates(dates: string[], months: number): string[] {
  if (!dates.length) return []
  const start = cutoff(dates[dates.length - 1], months)
  return dates.filter(d => d >= start)
}
function chgN(p: Series, m: number): number | null {
  if (p.close.length < 2) return null
  const start = cutoff(p.dates[p.dates.length - 1], m)
  let bi = -1
  p.dates.forEach((d, i) => { if (d <= start) bi = i })
  if (bi < 0) return null
  const a = p.close[bi], z = p.close[p.close.length - 1]
  return Number.isFinite(a) && Number.isFinite(z) && a !== 0 ? z / a - 1 : null
}

// 초록(+)/빨강(-) 히트맵 색 — scale 기준으로 정규화
function heatColor(pct: number | null, scale = 0.08): string {
  if (pct == null || !Number.isFinite(pct)) return '#f1f3f5'
  return `rgba(${pct >= 0 ? '37,136,117' : '198,95,81'},${.06+.62*Math.min(1,Math.abs(pct)/scale)})`
}

// 한 시계열을 window(months) 구간에서 100-리베이스 (구간 첫 유효값 = 100)
function rebaseSeries(p: Series, months: string[]): (number | null)[] {
  let cursor = -1
  let base: number | null = null
  return months.map(day => {
    while (cursor + 1 < p.dates.length && p.dates[cursor + 1] <= day) cursor++
    if (cursor < 0 || day > p.dates[p.dates.length - 1]) return null
    const v = p.close[cursor]
    if (!Number.isFinite(v)) return null
    if (base == null) base = v
    return base ? +((v / base) * 100).toFixed(2) : null
  })
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
    if (data.universe?.length) return data.universe.map(p => ({ ...p, label: p.bbid === 'GSPURSVL' ? 'Residual Volatility · High / Low' : p.label?.trim() || p.bbid }))
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
    return it ? chgN(it, rHeat) : null
  }

  // ── 라인차트용: 선택 섹터의 팩터별 100-리베이스 시계열
  const lineData = useMemo(() => {
    const its = data.sector.items.filter((x) => x.sector === sector)
    const allMonths = Array.from(new Set(its.flatMap((it) => it.dates))).sort()
    const months = windowDates(allMonths, rLines)
    const rebased = its.map(it => ({ it, values: rebaseSeries(it, months) }))
    return months.map((mo, i) => {
      const row: Record<string, number | string | null> = { month: mo }
      rebased.forEach(({ it, values }) => { row[it.factor] = values[i] })
      return row
    })
  }, [data, sector, rLines])

  const sectorFactors = useMemo(
    () => [...new Set(data.sector.items.filter((x) => x.sector === sector).map((x) => x.factor))],
    [data, sector]
  )

  const ranking = useMemo(() => rankFactors(universe, rTop), [universe, rTop])
  const top10 = ranking.ranked.slice(0, 10)
  const bottom10 = ranking.ranked.slice(-10).reverse()
  const periodLabel = rTop === -5 ? '5D' : RANGES.find(([, value]) => value === rTop)?.[0] || ''

  const Sel = ({ value, onChange, ranking }: { value: number; onChange: (n: number) => void; ranking?: boolean }) => (
    <select
      aria-label={ranking ? "수익률·그래프 기간" : undefined}
      value={value}
      onChange={(e) => onChange(+e.target.value)}
      className="bg-white border border-[var(--line)] rounded-md px-2 py-1 text-xs"
    >
      {ranking && data.frequency === 'daily' && <option value={-5}>5D</option>}
      {RANGES.map(([lab, m]) => <option key={m} value={m}>{lab}</option>)}
    </select>
  )

  const Bars = ({ rows }: { rows: { label: string; nameNote?: string; v: number }[] }) => {
    const mx = Math.max(...rows.map((r) => Math.abs(r.v)), 0.0001)
    return (
      <div className="flex flex-col gap-1.5">
        {rows.map((r, i) => {
          const mixed = rows.some(r => r.v < 0) && rows.some(r => r.v >= 0)
          const w = (Math.abs(r.v) / mx) * (mixed ? 50 : 100)
          const col = r.v >= 0 ? POS : NEG
          return (
            <div key={`${r.label}-${i}`} className="grid items-center gap-2 text-xs" style={{ gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 3fr) 60px' }}>
              <span title={`${r.label}\n${r.nameNote || ''}`} className="text-right text-[var(--muted)] truncate">{r.label}</span>
              <span className="relative h-3.5">

                <span className="absolute top-0.5 h-2.5 rounded-sm" style={{ background: col, width: `${w}%`, ...(mixed ? (r.v >= 0 ? { left: '50%' } : { right: '50%' }) : { left: 0 }) }} />
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
      <MajorFactors />

      <Card title="섹터 × 팩터 · 수익률(%)" control={<Sel value={rHeat} onChange={setRHeat} />}>
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
                      <td key={f} className="text-center" title={`${sec} · ${f} · ${rHeat}개월: ${pc == null ? "자료 없음" : (pc*100).toFixed(2)+"%"}`}>
                        <span className="block py-1.5 rounded font-bold" style={{ background: heatColor(pc), minWidth: 26 }}>
                          {pc == null ? '—' : (pc * 100).toFixed(2)}
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
        title="섹터별 팩터 추이 · 100 리베이스"
        control={
          <span className="flex items-center gap-2">
            <select value={sector} onChange={(e) => setSector(e.target.value)} className="bg-white border border-[var(--line)] rounded-md px-2 py-1 text-xs">
              {realSectors.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <Sel value={rLines} onChange={setRLines} />
          </span>
        }
      >
        <ChartImage rows={lineData} series={sectorFactors.map((f, i) => ({ key: f, label: f, color: PALETTE[i % PALETTE.length] }))} title={`${sector} · ${rLines}M · 100 리베이스`} />
      </Card>

      <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
        <h2 className="serif text-lg">수익률 Top 10 / Bottom 10</h2>
        <label className="flex items-center gap-2 text-sm">수익률·그래프 기간 <Sel value={rTop} onChange={setRTop} ranking /></label>
      </div>
      <p className="text-xs text-[var(--muted)] mb-3">{ranking.start} ~ {ranking.end} · 동일 기준일 자료 {ranking.ranked.length}개 · 추이는 시작값 100 기준</p>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3.5">
        {[{ title: 'Top 10', items: top10 }, { title: 'Bottom 10', items: bottom10 }].map(({ title, items }) => (
          <Card key={title} title={`수익률 ${title} · ${periodLabel}`}>
            <Bars rows={items} />
            <ChartImage compact rows={rankingRows(items, ranking.start, ranking.end)} series={items.map((item, i) => ({ key: item.series.bbid, label: item.label, color: PALETTE[i % PALETTE.length] }))} title={`${title} 추이 · ${periodLabel} · 100 리베이스`} />
          </Card>
        ))}
      </div>

      <p className="text-[11px] text-[var(--muted)] mt-2">
        데이터: GS Marquee PAIR_BASKETS_LEVELS ({data.frequency === 'daily' ? '일별 종가' : '월별'}){data.generatedAt ? ` · 생성 ${data.generatedAt}` : ''}
      </p>
    </section>
  )
}
