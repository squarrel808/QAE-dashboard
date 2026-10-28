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
  const [months, setMonths] = useState(12)
  const [overviewMode,setOverviewMode] = useState<'line'|'heat'|'sector'>('sector')
  const [overview, setOverview] = useState(true)
  const dm = [['US','미국'],['AU','호주'],['CA','캐나다'],['DE','독일'],['JP','일본'],['GB','영국'],['EAagg','유로존']]
  const overviewHeat = useMemo(() => {
    const dates = Array.from(new Set(dm.flatMap(([id]) => data.cai[id]?.dates || []))).sort()
    const selected = dates.slice(months >= 9999 ? 0 : -months)
    const matrix = dm.map(([id, label]) => {
      const series = data.cai[id]
      const lookup = new Map(series?.dates.map((d, i) => [d, series.headline[i]]) || [])
      return { id, label, values: selected.map(d => lookup.get(d) ?? null) }
    }).filter(row => row.values.some(value => value != null && Number.isFinite(value)))
    const maxAbs = Math.max(1, ...matrix.flatMap(r => r.values.map(v => Math.abs(v ?? 0))))
    return { dates: selected, matrix, maxAbs }
  }, [data, months])
  const summaryCards = dm.flatMap(([id,label],index)=>{
    const series=data.cai[id];if(!series)return [{id,label,points:[],last:undefined,previous:undefined,domain:[-1,1],color:'#576985'}]
    const dates=overviewHeat.dates
    const points=dates.map(date=>{const i=series.dates.indexOf(date);return {date,value:i<0?null:series.headline[i],completion:i<0?null:series.completion?.[i]??null}})
    const valid=points.filter(p=>p.value!=null),last=valid.at(-1),previous=valid.at(-2)
    const values=valid.map(p=>p.value as number),lo=Math.min(0,...values),hi=Math.max(0,...values),pad=Math.max(.2,(hi-lo)*.1)
    return [{id,label,points,last,previous,domain:[lo-pad,hi+pad],color:['#2d6bb0','#9169b1','#bb851c','#c3474b','#279486','#576985'][index%6]}]
  })
  const [hiddenCountries,setHiddenCountries] = useState<string[]>([])
  const comparisonCountries=dm.filter(([id])=>data.cai[id])
  const countryColors:Record<string,string>={US:'#2d6bb0',AU:'#c3474b',CA:'#279486',JP:'#bb851c',GB:'#576985',EAagg:'#9169b1'}
  const sectorComparison=data.sectors.map(sector=>{
    const matrix=comparisonCountries.map(([id,label])=>{
      const series=data.cai[id]
      const values=overviewHeat.dates.map(date=>{
        const i=series.dates.indexOf(date)
        const value=i<0?null:series.sectors[sector]?.[i]??null
        return value!=null && Number.isFinite(value)?value:null
      })
      return {id,label,values}
    })
    const maxAbs=Math.max(.01,...matrix.flatMap(row=>row.values.map(value=>Math.abs(value??0))))
    return {sector,matrix,maxAbs}
  })
  const pool = view === 'cai' ? data.cai : data.map
  const available = data.countries.filter((c) => pool[c.id])
  const [country, setCountry] = useState('US')

  const series: CaiSeries | undefined = pool[country] || pool[available[0]?.id]
  const activeId = pool[country] ? country : available[0]?.id

  const { rows, sectorKeys, typeRows, typeKeys } = useMemo(() => {
    if (!series) return { rows: [], sectorKeys: [], typeRows: [], typeKeys: [] }
    const last = series.dates[series.dates.length - 1]
    const cut = months >= 9999 ? '0000' : cutoffDate(last, months)
    // 국가별로 없는 섹터/타입은 null 로 들어오므로 배열인 것만 사용 (null 접근 시 크래시 → 빈 화면 방지)
    const sk = Object.keys(series.sectors).filter((s) => Array.isArray(series.sectors[s]))
    const tk = series.types ? Object.keys(series.types).filter((t) => Array.isArray(series.types![t])) : []
    const rows: Record<string, number | string | null>[] = []
    const typeRows: Record<string, number | string | null>[] = []
    series.dates.forEach((d, i) => {
      if (d < cut) return
      const r: Record<string, number | string | null> = { date: d, headline: series.headline[i] }
      sk.forEach((s) => { r[s] = series.sectors[s]![i] })
      rows.push(r)
      if (tk.length) {
        const tr: Record<string, number | string | null> = { date: d }
        tk.forEach((t) => { tr[t] = series.types![t]![i] })
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
      const vals = idx.map((i) => series.heatmap![s]![i] ?? null)
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
          <h2 className="serif text-[18px] m-0">CAI · MAP — {view === 'cai' && overview ? '주요 DM 전체' : label}</h2>
          <p className="text-xs text-[var(--muted)] mt-1">
            {view === 'cai' ? 'Current Activity Indicator (월별)' : 'MAP (일별)'} · 막대/선에 마우스를 올리면 값 표시
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex gap-1">
            <Btn on={view === 'cai' && overview} onClick={() => { setView('cai'); setOverview(true) }}>CAI 전체</Btn>
            <Btn on={view === 'cai' && !overview} onClick={() => { setView('cai'); setOverview(false) }}>CAI 국가별</Btn>
            <Btn on={view === 'map'} onClick={() => setView('map')}>MAP</Btn>
          </div>
          {!(view === 'cai' && overview) && <select value={activeId} onChange={(e) => setCountry(e.target.value)}
            className="bg-[var(--head)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-medium">
            {available.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>}
          <div className="flex gap-1">{RANGES.map(([lab, m]) => <Btn key={m} on={months === m} onClick={() => setMonths(m)}>{lab}</Btn>)}</div>
        </div>
      </div>

      {view === 'cai' && overview && <div className="flex gap-2 mb-4"><Btn on={overviewMode==='sector'} onClick={()=>setOverviewMode('sector')}>섹터별 히트맵</Btn><Btn on={overviewMode==='line'} onClick={()=>setOverviewMode('line')}>전체 선그래프</Btn><Btn on={overviewMode==='heat'} onClick={()=>setOverviewMode('heat')}>전체 히트맵</Btn></div>}
      {view === 'cai' && overview && overviewMode==='sector' ? <div>
        <p className="text-sm text-[var(--muted)] mb-3">CAI 섹터별 헤드라인 기여도 · 단위: CAI 기여도 포인트 · 초록 = 양수 / 빨강 = 음수 · 0 = 중립 · 진하기 = 섹터별 표시 기간 내 절대 크기 · 회색 — = 자료 없음</p>
        <div className="flex flex-wrap gap-2 mb-5">{comparisonCountries.map(([id,label])=><button key={id} aria-pressed={!hiddenCountries.includes(id)} onClick={()=>setHiddenCountries(old=>old.includes(id)?old.filter(v=>v!==id):[...old,id])} className="border rounded-lg px-3 py-2 text-base" style={{color:countryColors[id],opacity:hiddenCountries.includes(id)?.35:1}}>{label}</button>)}</div>
        <div className="flex flex-col gap-4">{sectorComparison.map(({sector,matrix,maxAbs})=><article key={sector} className="bg-white border border-[var(--line)] rounded-xl p-4" data-testid="cai-sector-comparison">
          <h3 className="text-lg font-semibold mb-3">{({Consumer:'소비',Housing:'주택',Labor:'고용',Manufacturing:'제조업',Other:'기타'} as Record<string,string>)[sector]} · {sector}</h3>
          <div className="overflow-x-auto"><table aria-label={`${sector} 국가별 기여도 히트맵`} style={{borderSpacing:2,borderCollapse:'separate',fontSize:16,width:'100%'}}>
            <thead><tr><th className="sticky left-0 z-10 bg-white text-left px-2 py-2">국가</th>{overviewHeat.dates.map(date=><th key={date} className="whitespace-nowrap font-normal px-2 py-2">{date.slice(2,7)}</th>)}</tr></thead>
            <tbody>{matrix.filter(row=>!hiddenCountries.includes(row.id)).map(row=><tr key={row.id}>
              <th scope="row" className="sticky left-0 z-10 bg-white text-left whitespace-nowrap px-2 py-2">{row.label}</th>
              {row.values.map((value,i)=>{const color=heatColor(value,maxAbs);return <td key={overviewHeat.dates[i]} title={`${row.label} · ${overviewHeat.dates[i]} · ${sector}: ${value==null?'자료 없음':value.toFixed(4)+' pt'}`} style={{background:value==null?'#e8edeb':color.bg,color:color.fg,minWidth:72,textAlign:'center',padding:'10px 8px',borderRadius:3,fontWeight:600}}>{value==null?'—':value.toFixed(2)}</td>})}
            </tr>)}</tbody>
          </table></div>
          {hiddenCountries.length===comparisonCountries.length && <p className="text-sm text-[var(--muted)] py-3">표시할 국가를 선택하세요.</p>}
        </article>)}</div>
      </div> : view === 'cai' && overview && overviewMode==='line' ? <div><p className="text-sm text-[var(--muted)] mb-4">CAI 성장 모멘텀 · 0 기준선 · 국가별 자동 Y축 · 구성지표 발표율은 각 카드 상단에 표시합니다.</p><div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">{summaryCards.map(c=><article key={c.id} className="rounded-xl border border-[var(--line)] bg-white p-4" data-testid="cai-summary-card"><h3 className="text-lg font-semibold mb-2">{c.label}</h3><div className="text-base mb-1">{[c.previous,c.last].filter(Boolean).map((p,i)=><span key={p!.date}>{i?' / ':''}{p!.date.slice(0,7)} <b>{p!.value!.toFixed(2)}</b></span>)}</div><p className="text-sm text-[var(--muted)] mb-2">구성지표 발표율 {[c.previous,c.last].filter(Boolean).map(p=>p!.completion==null?'미제공':p!.completion.toFixed(0)+'%').join(' / ')}</p><div className="h-[240px]">{!c.last?<div className="h-full flex items-center justify-center text-sm text-[var(--muted)]">독일 개별 CAI 원자료 없음 · 유로존은 별도 표시</div>:<ResponsiveContainer width="100%" height="100%"><LineChart data={c.points} margin={{top:8,right:15,bottom:5,left:0}}><CartesianGrid vertical={false} stroke="#edf0ee"/><XAxis dataKey="date" tickFormatter={v=>String(v).slice(2,7)} tick={{fontSize:12}} minTickGap={25}/><YAxis domain={c.domain} tick={{fontSize:12}} tickFormatter={v=>Number(v).toFixed(1)} width={54}/><ReferenceLine y={0} stroke="#80958d" strokeWidth={1.5}/><Tooltip formatter={v=>typeof v==='number'?v.toFixed(2):'—'}/><Line name="CAI" dataKey="value" type="linear" stroke={c.color} strokeWidth={2.4} dot={{r:2.5}} connectNulls={false} isAnimationActive={false}/></LineChart></ResponsiveContainer>}</div></article>)}</div></div> : view === 'cai' && overview ? <div className="rounded-xl border border-[var(--line)] bg-white p-3.5">
        <h3 className="serif text-[15px] mb-2">주요 DM · CAI 헤드라인</h3>
        <p className="text-xs text-[var(--muted)] mb-3">초록 = 양수 · 빨강 = 음수 · 진하기 = 표시 기간 내 상대 크기 · — = 데이터 없음</p>
        <div className="overflow-x-auto"><table style={{ borderSpacing: 2, borderCollapse: 'separate', fontSize: 11, width: '100%' }}>
          <thead><tr><th className="sticky left-0 bg-white">국가</th>{overviewHeat.dates.map(d => <th key={d} className="whitespace-nowrap font-normal px-1">{d.slice(2,7)}</th>)}</tr></thead>
          <tbody>{overviewHeat.matrix.map(r => <tr key={r.id}><th scope="row" className="sticky left-0 bg-white text-left whitespace-nowrap pr-3">{r.label}</th>{r.values.map((v,i) => { const c = heatColor(v, overviewHeat.maxAbs); return <td key={i} title={`${r.label} · ${overviewHeat.dates[i]}: ${v ?? '데이터 없음'}`} style={{ background: c.bg, color: c.fg, minWidth: 42, textAlign: 'center', padding: '8px 4px', borderRadius: 4 }}>{v == null ? '—' : v.toFixed(1)}</td> })}</tr>)}</tbody>
        </table></div>
      </div> : <>
      <div className="rounded-xl border border-[var(--line)] bg-white p-3.5 mb-3.5">
        <h3 className="serif text-[15px] mb-2.5">
          {view === 'cai' ? 'Headline + 섹터 기여도' : 'Headline + 섹터별 서프라이즈'}
        </h3>
        <div style={{ height: 340 }}>
          <ResponsiveContainer width="100%" height="100%">
            {view === 'cai' ? (
              /* CAI 섹터는 진짜 기여도라 합이 헤드라인과 정확히 일치한다(오차 0.000). 그래서 누적막대.
                 stackOffset="sign": 기본값(none)은 앞 섹터의 누적합 위에 그냥 얹어서, 앞쪽이
                 음수면 뒤에 오는 양수 기여도가 0선 아래에 그려진다. sign 은 양수는 0 위로,
                 음수는 0 아래로 나눠 쌓아 각 섹터의 부호와 막대 방향이 맞는다. */
              <ComposedChart data={rows} stackOffset="sign" margin={{ top: 6, right: 12, left: -10, bottom: 0 }}>
                <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
                <XAxis dataKey="date" {...axis} />
                <YAxis tick={axis.tick} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,.25)" />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {sectorKeys.map((s) => <Bar key={s} dataKey={s} stackId="s" fill={SCOL[s] || '#9aa0a6'} />)}
                <Line type="monotone" dataKey="headline" stroke="#1a1c1f" strokeWidth={1.8} dot={false} connectNulls />
              </ComposedChart>
            ) : (
              /* MAP 섹터는 기여도가 아니라 섹터별 서프라이즈 점수라 더할 수 없다.
                 실제로 합이 헤드라인의 2~3배로 벌어진다 (EAagg 7.29 vs 3.13, GB 6.72 vs 2.58,
                 US 는 -0.72 vs 0.34 로 부호까지 반대). 누적막대로 그리면 Other 같은 섹터가
                 실제보다 훨씬 커 보인다 → 원본 대시보드처럼 각각 선으로 그린다. */
              <LineChart data={rows} margin={{ top: 6, right: 12, left: -10, bottom: 0 }}>
                <CartesianGrid stroke="rgba(0,0,0,.07)" vertical={false} />
                <XAxis dataKey="date" {...axis} />
                <YAxis tick={axis.tick} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,.25)" />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {sectorKeys.map((s) => (
                  <Line key={s} type="monotone" dataKey={s} stroke={SCOL[s] || '#9aa0a6'}
                    strokeWidth={1.4} dot={false} connectNulls />
                ))}
                <Line type="monotone" dataKey="headline" stroke="#1a1c1f" strokeWidth={2} dot={false} connectNulls />
              </LineChart>
            )}
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
      </>}
    </section>
  )
}
