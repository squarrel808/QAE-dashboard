'use client'
import { useMemo, useState } from 'react'
import {
  ComposedChart, Bar, Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import type { PcaData, PcaVersion } from '@/lib/types'

const CONTRIB_COLORS: Record<string, string> = { Capex: '#378ADD', Consumer: '#1D9E75', Export: '#BA7517', Housing: '#D4537E', Other: '#888780' }
const PALETTE = ['#378ADD', '#1D9E75', '#BA7517', '#D4537E', '#9b8cff', '#46b0c9', '#e0833b', '#cf5fd0', '#6fcf6f', '#d24b4a', '#5fa8ff', '#9aa0a6']
const RANGE_OPTS: [number, string][] = [[12, '1Y'], [24, '2Y'], [36, '3Y'], [60, '5Y'], [120, '10Y'], [9999, 'All']]
// 경제지표(econ)에서 수집하는 국가 목록. 현재 PCA 데이터는 US만 존재 → 나머지는 '준비중'.
const PCA_COUNTRIES: [string, string][] = [
  ['US', '미국'], ['GB', '영국'], ['FR', '프랑스'], ['DE', '독일'], ['IT', '이탈리아'],
  ['JP', '일본'], ['CA', '캐나다'], ['AU', '호주'], ['CN', '중국'], ['KR', '한국'],
]

function tail<T>(arr: T[], months: number) {
  return months >= 9999 ? arr : arr.slice(Math.max(0, arr.length - months))
}

export default function Pca({ data }: { data: PcaData }) {
  const yoy = data.versions['YoY']
  const mom = data.versions['Momentum']
  const cats = useMemo(() => Object.keys(yoy.categories).filter((c) => c !== 'LEI'), [yoy])

  const [pcaCountry, setPcaCountry] = useState('US')
  const ready = pcaCountry === 'US'   // 현재 US만 실제 데이터 존재
  const countryLabel = PCA_COUNTRIES.find((c) => c[0] === pcaCountry)?.[1] || pcaCountry
  const [tab, setTab] = useState<'gdp' | 'lei'>('gdp')
  const [gdpMonths, setGdpMonths] = useState(120)
  const [leiMonths, setLeiMonths] = useState(120)
  const [drillCat, setDrillCat] = useState(cats[0])
  const [drillVer, setDrillVer] = useState<'YoY' | 'Momentum'>('YoY')
  const [leiVer, setLeiVer] = useState<'YoY' | 'Momentum'>('YoY')

  const axis = { tick: { fontSize: 9, fill: '#5a5f66' }, minTickGap: 24 } as const

  const Card = ({ title, control, children }: { title: string; control?: React.ReactNode; children: React.ReactNode }) => (
    <div className="rounded-xl border border-[var(--line)] bg-white p-3.5 mb-3.5">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2.5">
        <h3 className="serif text-[15px] m-0">{title}</h3>{control}
      </div>{children}
    </div>
  )
  const RangeSel = ({ value, onChange }: { value: number; onChange: (n: number) => void }) => (
    <span className="flex items-center gap-2">
      <span className="text-xs text-[var(--muted)]">기간</span>
      <select value={value} onChange={(e) => onChange(+e.target.value)} className="bg-white border border-[var(--line)] rounded-md px-2 py-1 text-xs">
        {RANGE_OPTS.map(([m, lab]) => <option key={m} value={m}>{lab}</option>)}
      </select>
    </span>
  )
  const VerToggle = ({ ver, set }: { ver: string; set: (v: 'YoY' | 'Momentum') => void }) => (
    <span className="flex gap-1">
      {(['YoY', 'Momentum'] as const).map((vv) => (
        <button key={vv} onClick={() => set(vv)}
          className={'rounded-md border px-3 py-1 text-xs font-semibold ' +
            (ver === vv ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white border-[var(--line)] hover:bg-[var(--head)]')}>
          {vv}
        </button>
      ))}
    </span>
  )

  // ── GDP 기여도 (스택 막대 + 지수 라인) ──
  function Contrib({ v, months, title }: { v: PcaVersion; months: number; title: string }) {
    const keys = Object.keys(v.gdp.contrib)
    const dates = tail(v.dates, months)
    const start = v.dates.length - dates.length
    const rows = dates.map((d, i) => {
      const gi = start + i
      const r: Record<string, number | string | null> = { date: d, '지수': v.gdp.index[gi] }
      keys.forEach((k) => { r[k] = v.gdp.contrib[k][gi] })
      return r
    })
    return (
      <Card title={title}>
        <div style={{ height: 290 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 6, right: 10, left: -12, bottom: 0 }}>
              <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
              <XAxis dataKey="date" {...axis} /><YAxis tick={axis.tick} />
              <ReferenceLine y={0} stroke="rgba(0,0,0,.25)" />
              <Tooltip contentStyle={{ fontSize: 11 }} /><Legend wrapperStyle={{ fontSize: 11 }} />
              {keys.map((k) => <Bar key={k} dataKey={k} stackId="g" fill={CONTRIB_COLORS[k] || '#9aa0a6'} />)}
              <Line type="monotone" dataKey="지수" stroke="#1a1c1f" strokeWidth={1.6} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Card>
    )
  }

  // ── 카테고리별 지수: YoY vs Momentum 오버레이 (소형) ──
  function CatDual({ cat, months }: { cat: string; months: number }) {
    const yd = tail(yoy.dates, months); const ys = yoy.dates.length - yd.length
    const md = tail(mom.dates, months); const ms = mom.dates.length - md.length
    const map = new Map<string, Record<string, number | string | null>>()
    yd.forEach((d, i) => map.set(d, { date: d, YoY: yoy.categories[cat].index[ys + i] }))
    md.forEach((d, i) => { const e = map.get(d) || { date: d }; e.Momentum = mom.categories[cat].index[ms + i]; map.set(d, e) })
    const rows = [...map.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)))
    return (
      <div className="border border-[var(--line)] rounded-lg p-2">
        <div className="text-xs font-semibold mb-1">{cat}</div>
        <div style={{ height: 150 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="rgba(0,0,0,.06)" vertical={false} />
              <XAxis dataKey="date" {...axis} /><YAxis tick={axis.tick} width={28} />
              <ReferenceLine y={0} stroke="rgba(0,0,0,.2)" />
              <Tooltip contentStyle={{ fontSize: 10 }} /><Legend wrapperStyle={{ fontSize: 9 }} />
              <Line type="monotone" dataKey="YoY" stroke="#378ADD" strokeWidth={1.3} dot={false} connectNulls />
              <Line type="monotone" dataKey="Momentum" stroke="#BA7517" strokeWidth={1.3} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    )
  }

  // ── 개별 지표 z-score 소형 차트 (단일 라인) ──
  function MiniZ({ name, dates, vals }: { name: string; dates: string[]; vals: (number | null)[] }) {
    const rows = dates.map((d, i) => ({ date: d, z: vals[i] }))
    return (
      <div className="border border-[var(--line)] rounded-lg p-2">
        <div className="text-[11px] font-medium mb-1 truncate" title={name}>{name}</div>
        <div style={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="rgba(0,0,0,.06)" vertical={false} />
              <XAxis dataKey="date" {...axis} /><YAxis tick={axis.tick} width={28} />
              <ReferenceLine y={0} stroke="rgba(0,0,0,.2)" />
              <Tooltip contentStyle={{ fontSize: 10 }} />
              <Line type="monotone" dataKey="z" name={name} stroke="#6e1f1f" strokeWidth={1.2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    )
  }

  // 드릴다운 / LEI z-score 용 윈도우 슬라이스
  function indicatorList(v: PcaVersion, catKey: string) {
    const node = v.categories[catKey]
    if (!node) return [] as { name: string; dates: string[]; vals: (number | null)[] }[]
    const dates = tail(v.dates, tab === 'lei' ? leiMonths : gdpMonths)
    const start = v.dates.length - dates.length
    return Object.keys(node.indicators).map((nm) => ({ name: nm, dates, vals: node.indicators[nm].slice(start) }))
  }

  function LeiLine({ v, months, title }: { v: PcaVersion; months: number; title: string }) {
    const dates = tail(v.dates, months); const start = v.dates.length - dates.length
    const rows = dates.map((d, i) => ({ date: d, LEI: v.lei.index[start + i] }))
    return (
      <Card title={title}>
        <div style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 6, right: 10, left: -12, bottom: 0 }}>
              <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
              <XAxis dataKey="date" {...axis} /><YAxis tick={axis.tick} />
              <ReferenceLine y={0} stroke="rgba(0,0,0,.25)" />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="LEI" name={`LEI ${title.includes('Momentum') ? 'Momentum' : 'YoY'}`} stroke="#6e1f1f" strokeWidth={1.8} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
    )
  }

  const drillItems = indicatorList(drillVer === 'YoY' ? yoy : mom, drillCat)
  const leiItems = indicatorList(leiVer === 'YoY' ? yoy : mom, 'LEI')

  return (
    <section>
      <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
        <div>
          <h2 className="serif text-[18px] m-0">{ready ? data.country : countryLabel} — Activity Index</h2>
          <p className="text-xs text-[var(--muted)] mt-1">Category PCA · Equal-Weight GDP Proxy · EWM z-score · 막대/선 호버 시 값 표시</p>
        </div>
        <span className="flex items-center gap-2">
          <span className="text-xs text-[var(--muted)]">국가</span>
          <select value={pcaCountry} onChange={(e) => setPcaCountry(e.target.value)}
            className="bg-[var(--head)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-medium">
            {PCA_COUNTRIES.map(([id, lab]) => (
              <option key={id} value={id}>{lab}{id === 'US' ? '' : ' (준비중)'}</option>
            ))}
          </select>
        </span>
      </div>

      {!ready ? (
        <div className="rounded-xl border border-[var(--line)] bg-white p-8 text-center text-sm text-[var(--muted)]">
          {countryLabel} PCA 데이터는 준비 중입니다. 현재는 미국(US)만 제공됩니다.
        </div>
      ) : (
      <>
      {/* 탭 */}
      <div className="flex gap-2 mb-4">
        {([['gdp', '경기지수'], ['lei', 'LEI']] as const).map(([t, lab]) => (
          <button key={t} onClick={() => setTab(t)}
            className={'rounded-lg border px-4 py-2 text-sm font-semibold ' +
              (tab === t ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white border-[var(--line)] hover:bg-[var(--head)]')}>
            {lab}
          </button>
        ))}
      </div>

      {tab === 'gdp' && (
        <>
          <div className="mb-2.5"><RangeSel value={gdpMonths} onChange={setGdpMonths} /></div>
          <Contrib v={yoy} months={gdpMonths} title="GDP Proxy — YoY (Contributions)" />
          <Contrib v={mom} months={gdpMonths} title="GDP Proxy — Momentum 3m/3m (Contributions)" />

          <Card title="카테고리별 지수 (YoY vs Momentum)">
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
              {cats.map((c) => <CatDual key={c} cat={c} months={gdpMonths} />)}
            </div>
          </Card>

          <Card title="카테고리 드릴다운 — 개별 지표 z-score"
            control={
              <span className="flex items-center gap-2">
                <select value={drillCat} onChange={(e) => setDrillCat(e.target.value)} className="bg-white border border-[var(--line)] rounded-md px-2 py-1 text-xs">
                  {cats.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <VerToggle ver={drillVer} set={setDrillVer} />
              </span>
            }>
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
              {drillItems.map((it, j) => <MiniZ key={j} name={it.name} dates={it.dates} vals={it.vals} />)}
            </div>
          </Card>
        </>
      )}

      {tab === 'lei' && (
        <>
          <div className="mb-2.5"><RangeSel value={leiMonths} onChange={setLeiMonths} /></div>
          <LeiLine v={yoy} months={leiMonths} title="LEI — YoY" />
          <LeiLine v={mom} months={leiMonths} title="LEI — Momentum 3m/3m" />
          <Card title="LEI 구성 지표 z-score" control={<VerToggle ver={leiVer} set={setLeiVer} />}>
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
              {leiItems.map((it, j) => <MiniZ key={j} name={it.name} dates={it.dates} vals={it.vals} />)}
            </div>
          </Card>
        </>
      )}
      </>
      )}
    </section>
  )
}
