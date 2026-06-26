'use client'
import { useMemo, useState } from 'react'
import {
  ComposedChart, Bar, Cell, Line, LineChart, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Legend,
} from 'recharts'
import type { PolicyData } from '@/lib/types'

const HAWK = '#c0392b', DOVE = '#1a7a4c', NEUT = '#9aa0a6'
const BANKC: Record<string, string> = { FED: '#6e1f1f', BOJ: '#b8860b', ECB: '#3a5a8c', BOE: '#7a4a6e' }

function signColor(v: number, nb: number) {
  return v > nb ? HAWK : v < -nb ? DOVE : NEUT
}

export default function PolicyTone({ data }: { data: PolicyData }) {
  const banks = useMemo(() => Object.keys(data.banks), [data])
  const nb = data.neutralBand ?? 0.15
  const [sel, setSel] = useState<string>(banks.includes('FED') ? 'FED' : banks[0])

  // 선택 은행 1개: {date, bar, trend, events}
  const rows = useMemo(() => {
    if (sel === 'ALL') return []
    const b = data.banks[sel]
    return b.dates.map((d, i) => ({ date: d, bar: b.bar[i], trend: b.trend[i] }))
  }, [data, sel])

  // ALL 모드: 날짜축 합치고 은행별 추세선
  const allRows = useMemo(() => {
    if (sel !== 'ALL') return []
    const set = new Set<string>()
    banks.forEach((bk) => data.banks[bk].dates.forEach((d) => set.add(d)))
    const dates = [...set].sort()
    return dates.map((d) => {
      const row: Record<string, number | string | null> = { date: d }
      banks.forEach((bk) => {
        const b = data.banks[bk]
        const idx = b.dates.indexOf(d)
        row[bk] = idx >= 0 ? b.trend[idx] : null
      })
      return row
    })
  }, [data, banks, sel])

  const TipOne = ({ active, payload }: any) => {
    if (!active || !payload?.length || sel === 'ALL') return null
    const date = payload[0]?.payload?.date
    const evs = data.banks[sel].events?.[date] || []
    return (
      <div className="rounded-md border border-[var(--line)] bg-white p-2.5 text-xs max-w-md shadow-sm">
        <div className="font-semibold text-[var(--badge)] mb-1">📅 {date}</div>
        <div className="mb-1">raw stance: <b>{payload[0]?.payload?.bar}</b></div>
        {evs.map((e, i) => (
          <div key={i} className="mt-1.5">
            <div className="font-medium">👤 {e.sp} (stance {e.st > 0 ? '+' : ''}{e.st})</div>
            <div className="text-[var(--muted)] leading-snug">{e.rs}</div>
          </div>
        ))}
        {evs.length === 0 && <div className="text-[var(--muted)]">상세 코멘트 없음</div>}
      </div>
    )
  }

  return (
    <section>
      <div className="flex items-start justify-between gap-3 mb-1 flex-wrap">
        <div>
          <h2 className="serif text-[18px] m-0">Central bank hawk-dove stance</h2>
          <p className="text-xs text-[var(--muted)] mt-1">
            raw stance (-2 dovish ~ +2 hawkish) · 연설일 기준{data.generatedAt ? ` · updated ${data.generatedAt}` : ''}
          </p>
        </div>
        <select
          value={sel}
          onChange={(e) => setSel(e.target.value)}
          className="bg-[var(--head)] border border-[var(--line)] rounded-lg px-4 py-2 text-sm font-medium"
        >
          <option value="ALL">전체 추세 비교 (All)</option>
          {banks.map((b) => <option key={b} value={b}>{data.banks[b].label}</option>)}
        </select>
      </div>

      <div className="rounded-xl border border-[var(--line)] bg-white p-4">
        <div style={{ height: 460 }}>
          <ResponsiveContainer width="100%" height="100%">
            {sel === 'ALL' ? (
              <LineChart data={allRows} margin={{ top: 10, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#5a5f66' }} minTickGap={40} />
                <YAxis domain={[-2.2, 2.2]} tick={{ fontSize: 11, fill: '#5a5f66' }} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,.25)" />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {banks.map((b) => (
                  <Line key={b} type="monotone" dataKey={b} name={data.banks[b].label}
                    stroke={BANKC[b] || '#5a5f66'} strokeWidth={1.6} dot={false} connectNulls />
                ))}
              </LineChart>
            ) : (
              <ComposedChart data={rows} margin={{ top: 10, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#5a5f66' }} minTickGap={32} />
                <YAxis domain={[-2.2, 2.2]} ticks={[-2, -1, 0, 1, 2]} tick={{ fontSize: 11, fill: '#5a5f66' }} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,.25)" />
                <Tooltip content={<TipOne />} />
                <Bar dataKey="bar" name="raw stance" radius={[2, 2, 0, 0]} maxBarSize={14}>
                  {rows.map((r, i) => <Cell key={i} fill={signColor(r.bar, nb)} />)}
                </Bar>
                <Line type="monotone" dataKey="trend" name="추세(30일 가중)" stroke="#5a5f66"
                  strokeWidth={1.3} strokeDasharray="5 4" dot={false} />
              </ComposedChart>
            )}
          </ResponsiveContainer>
        </div>
        <p className="text-[11px] text-[var(--muted)] mt-2">
          막대 = 연설일 raw stance (▲매파 빨강 / ▼완화 초록 / 중립 회색) · 점선 = 위원 참여도 가중 30일 평균.
          막대에 마우스를 올리면 날짜·위원·핵심 요약. (전체 모드는 은행별 추세선 비교)
        </p>
      </div>
    </section>
  )
}
