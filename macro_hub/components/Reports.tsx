'use client'
import { useMemo, useState } from 'react'
import type { HouseConfidence, HouseStance, HouseView, HouseViewData, ReportRec } from '@/lib/types'

// houseviews.json 이 아직 없을 때의 폴백 축. 데이터가 오면 그쪽 배열이 이긴다.
const DEFAULT_HOUSES = ['GS', 'JPM', 'BofA', 'Citi', 'HSBC', 'UBS']
const DEFAULT_ASSETS = ['매크로', '채권', '주식', '코모디티']
const DEFAULT_REGIONS = ['US', 'EU', 'JP', 'CN', 'KR', 'UK', 'AU', 'EM']
const REGION_KR: Record<string, string> = {
  US: '미국', EU: '유럽', JP: '일본', CN: '중국', KR: '한국', UK: '영국', AU: '호주', EM: '신흥', GLOBAL: '글로벌',
}
const ASSET_NOTE: Record<string, string> = {
  매크로: '통화정책·경기', 채권: 'rates view', 주식: 'equity', 코모디티: '유가 등',
}
// 권역 구분이 무의미한 자산군 — 열로 쪼개지 않고 한 줄에 몰아서 보여준다.
const NO_REGION_ASSETS = new Set(['코모디티'])
// 하우스 하나가 뷰를 1,000건 넘게 갖는다. 목록은 최신부터 잘라서 보여주고 나머지는 접는다.
const HV_LIST_MAX = 60

const STANCE_COLOR: Record<string, string> = { OW: '#1a7a4c', N: '#888780', UW: '#c0392b' }
const STANCE_KR: Record<string, string> = { OW: '비중확대', N: '중립', UW: '비중축소' }
const EMPTY_VIEWS: HouseView[] = []
const CLAMP2: React.CSSProperties = {
  display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
}

// 흰색과 섞어 옅게 (t=1 이면 원색)
function tint(hex: string, t: number) {
  const n = (i: number) => parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16)
  const m = (x: number) => Math.round(255 + (x - 255) * t)
  return `rgb(${m(n(0))},${m(n(1))},${m(n(2))})`
}
// OW=초록 / N=회색 / UW=빨강. confidence 가 낮을수록 옅고, low 는 점선으로 약하게.
function stanceStyle(stance: HouseStance | string, conf: HouseConfidence | string): React.CSSProperties {
  const c = STANCE_COLOR[stance] || STANCE_COLOR.N
  if (conf === 'low') return { background: '#fff', color: c, borderColor: tint(c, 0.5), borderStyle: 'dashed', opacity: 0.78 }
  if (conf === 'mid') return { background: tint(c, 0.13), color: c, borderColor: tint(c, 0.4), borderStyle: 'solid' }
  return { background: c, color: '#fff', borderColor: c, borderStyle: 'solid' }
}
const cellKey = (asset: string, region: string) => asset + '|' + (NO_REGION_ASSETS.has(asset) ? '*' : region)

export default function Reports({ rows, houseViews }: { rows: ReportRec[]; houseViews?: HouseViewData }) {
  const [q, setQ] = useState('')
  const [src, setSrc] = useState('ALL')
  const [date, setDate] = useState('ALL')
  const [open, setOpen] = useState<Record<string, boolean>>({})
  // 하우스뷰 영역 — 전체(하우스 합산 매트릭스) / 운용사별(하우스 선택)
  const [hvMode, setHvMode] = useState<'all' | 'byHouse'>('all')
  const [house, setHouse] = useState('ALL')
  const [expand, setExpand] = useState<Record<string, boolean>>({})
  const [listAll, setListAll] = useState(false)

  const sources = useMemo(() => [...new Set(rows.map((r) => r.source))].sort(), [rows])
  const dates = useMemo(() => [...new Set(rows.map((r) => r.date))].sort().reverse(), [rows])

  const filtered = useMemo(() => {
    const kw = q.trim().toLowerCase()
    return rows.filter((r) => {
      if (src !== 'ALL' && r.source !== src) return false
      if (date !== 'ALL' && r.date !== date) return false
      if (!kw) return true
      const hay = [r.title, r.source, r.section, r.summary.join(' '), r.keywords.join(' ')].join(' ').toLowerCase()
      return hay.includes(kw)
    }).sort((a, b) => b.date.localeCompare(a.date))
  }, [rows, q, src, date])

  // ── 하우스뷰 축 ──
  const views = useMemo(
    () => (houseViews && Array.isArray(houseViews.views) ? houseViews.views : EMPTY_VIEWS),
    [houseViews],
  )
  const houses = useMemo(() => {
    const base = houseViews && houseViews.houses.length ? [...houseViews.houses] : [...DEFAULT_HOUSES]
    views.forEach((v) => { if (v.house && !base.includes(v.house)) base.push(v.house) })
    return base
  }, [houseViews, views])
  const assets = useMemo(() => {
    const base = houseViews && houseViews.assets.length ? [...houseViews.assets] : [...DEFAULT_ASSETS]
    views.forEach((v) => { if (v.asset && !base.includes(v.asset)) base.push(v.asset) })
    return base
  }, [houseViews, views])
  // 코모디티(권역 없음)는 열을 만들지 않는다. GLOBAL 처럼 regions 밖의 값이 와도 열로 살려 준다.
  const regionCols = useMemo(() => {
    const base = houseViews && houseViews.regions.length ? [...houseViews.regions] : [...DEFAULT_REGIONS]
    views.forEach((v) => {
      if (NO_REGION_ASSETS.has(v.asset)) return
      const r = v.region || 'GLOBAL'
      if (!base.includes(r)) base.push(r)
    })
    return base
  }, [houseViews, views])

  const activeHouse = hvMode === 'byHouse' ? house : 'ALL'
  // 날짜 내림차순 — 한 칸에 여러 하우스가 겹치면 맨 앞(최신)이 대표가 된다.
  const hvRows = useMemo(() => {
    const pool = activeHouse === 'ALL' ? views : views.filter((v) => v.house === activeHouse)
    return [...pool].sort((a, b) => b.date.localeCompare(a.date))
  }, [views, activeHouse])
  // hvRows 는 날짜 내림차순 — 같은 (하우스, 권역) 은 맨 앞(최신) 한 건만 대표로 남긴다.
  // 원본이 1,880건이라 이 압축이 없으면 한 칸에 같은 하우스 뷰가 수백 개 쌓이고
  // '+N개 하우스' 라벨도 하우스 수가 아니라 뷰 수를 세게 된다.
  const cells = useMemo(() => {
    const m = new Map<string, HouseView[]>()
    const seen = new Set<string>()
    hvRows.forEach((v) => {
      const region = v.region || 'GLOBAL'
      const k = cellKey(v.asset, region)
      const dedup = k + '||' + v.house + '||' + region
      if (seen.has(dedup)) return
      seen.add(dedup)
      const arr = m.get(k)
      if (arr) arr.push(v)
      else m.set(k, [v])
    })
    return m
  }, [hvRows])

  const sel = 'bg-white border border-[var(--line)] rounded-lg px-3 py-2 text-sm'
  const btn = (on: boolean) =>
    'rounded-lg border px-3.5 py-1.5 text-xs font-semibold transition-colors ' +
    (on ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white text-[var(--ink)] border-[var(--line)] hover:bg-[var(--head)]')

  // 스탠스 배지 + rationale 1~2줄
  const Chip = ({ v, showRegion }: { v: HouseView; showRegion?: boolean }) => (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="rounded border px-1.5 py-[1px] text-[10px] font-bold leading-[1.35]"
          style={stanceStyle(v.stance, v.confidence)}
          title={(STANCE_KR[v.stance] || v.stance) + ' · 확신도 ' + v.confidence}>
          {v.stance}
        </span>
        <span className="text-[11px] font-semibold">{(v.house || '').toUpperCase()}</span>
        {showRegion && v.region && v.region !== 'GLOBAL' && (
          <span className="text-[10px] text-[var(--muted)] border border-[var(--line)] rounded px-1">{v.region}</span>
        )}
        <span className="text-[10px] text-[var(--muted)]">{(v.date || '').slice(5)}</span>
      </div>
      <p className="mt-0.5 mb-0 text-[11px] leading-snug text-[var(--muted)]" style={CLAMP2}
        title={[v.title, v.rationale].filter(Boolean).join(' — ')}>
        {v.rationale}
      </p>
    </div>
  )

  // 같은 칸에 여러 하우스가 겹치면 대표 1건만 펴고 나머지는 +N 으로 접는다.
  const Stack = ({ list, k }: { list: HouseView[]; k: string }) => {
    if (!list.length) return null
    const isOpen = !!expand[k]
    return (
      <div>
        <div className="space-y-2">
          {(isOpen ? list : list.slice(0, 1)).map((v) => <Chip key={v.id} v={v} />)}
        </div>
        {list.length > 1 && (
          <button onClick={() => setExpand((o) => ({ ...o, [k]: !isOpen }))}
            className="mt-1 text-[11px] font-semibold text-[var(--badge)]">
            {isOpen ? '접기' : '+' + (list.length - 1) + '개 하우스'}
          </button>
        )}
      </div>
    )
  }

  return (
    <section>
      {/* ── 하우스뷰 (자산군 × 권역) ── */}
      <div className="rounded-xl border border-[var(--line)] bg-white p-3.5 mb-4">
        <div className="flex items-center justify-between gap-2 flex-wrap mb-2.5">
          <h3 className="serif text-[15px] m-0">
            하우스뷰
            {houseViews && houseViews.generatedAt && (
              <span className="ml-2 text-[11px] font-normal text-[var(--muted)]">{houseViews.generatedAt} 기준</span>
            )}
          </h3>
          <div className="flex gap-1.5">
            <button onClick={() => setHvMode('all')} className={btn(hvMode === 'all')}>전체</button>
            <button onClick={() => setHvMode('byHouse')} className={btn(hvMode === 'byHouse')}>운용사별</button>
          </div>
        </div>

        {hvMode === 'byHouse' && (
          <div className="flex gap-1.5 flex-wrap mb-2.5 pb-2.5 border-b border-[var(--line)]">
            <button onClick={() => setHouse('ALL')} className={btn(house === 'ALL')}>전체</button>
            {houses.map((h) => (
              <button key={h} onClick={() => setHouse(h)} className={btn(house === h)}>{h.toUpperCase()}</button>
            ))}
          </div>
        )}

        {/* 범례 */}
        <div className="flex items-center gap-3 flex-wrap mb-2 text-[11px] text-[var(--muted)]">
          {(['OW', 'N', 'UW'] as const).map((s) => (
            <span key={s} className="flex items-center gap-1">
              <span className="rounded border px-1.5 py-[1px] text-[10px] font-bold" style={stanceStyle(s, 'high')}>{s}</span>
              {STANCE_KR[s]}
            </span>
          ))}
          <span className="flex items-center gap-1 ml-1">
            <span className="rounded border px-1.5 py-[1px] text-[10px] font-bold" style={stanceStyle('N', 'low')}>N</span>
            점선·옅은 색 = 확신도 low
          </span>
        </div>

        {/* 넓은 표 — 페이지가 아니라 이 컨테이너만 가로로 스크롤한다 */}
        <div className="overflow-x-auto border border-[var(--line)] rounded-lg">
          <table className="border-collapse text-left" style={{ minWidth: 140 + regionCols.length * 168 }}>
            <thead>
              <tr className="bg-[var(--head)]">
                <th className="px-3 py-2 text-xs font-semibold text-[var(--muted)] border-b border-[var(--line)]"
                  style={{ width: 140 }}>자산군</th>
                {regionCols.map((r) => (
                  <th key={r} className="px-2 py-2 text-xs font-semibold border-b border-l border-[var(--line)]"
                    style={{ width: 168 }}>
                    {r}
                    <span className="ml-1 font-normal text-[10px] text-[var(--muted)]">{REGION_KR[r] || ''}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => {
                const noRegion = NO_REGION_ASSETS.has(a)
                const flat = cells.get(cellKey(a, '*')) || []
                return (
                  <tr key={a} className="align-top">
                    <th className="px-3 py-2.5 text-left border-b border-[var(--line)] bg-[var(--head)]">
                      <div className="text-[13px] font-semibold">{a}</div>
                      {ASSET_NOTE[a] && <div className="text-[10px] font-normal text-[var(--muted)] mt-0.5">{ASSET_NOTE[a]}</div>}
                    </th>
                    {noRegion ? (
                      // 권역 구분이 없는 자산군 — 한 칸으로 펼쳐 가로 나열
                      <td colSpan={regionCols.length} className="px-2 py-2.5 border-b border-l border-[var(--line)]">
                        {flat.length ? (
                          <div className="flex flex-wrap gap-x-6 gap-y-2.5">
                            {flat.map((v) => (
                              <div key={v.id} className="max-w-[300px]"><Chip v={v} showRegion /></div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-[11px] text-[var(--muted)]">권역 구분 없음</span>
                        )}
                      </td>
                    ) : (
                      regionCols.map((r) => {
                        const k = cellKey(a, r)
                        const list = cells.get(k) || []
                        return (
                          <td key={r} className="px-2 py-2.5 border-b border-l border-[var(--line)]">
                            <Stack list={list} k={k} />
                          </td>
                        )
                      })
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {views.length === 0 && (
          <p className="text-[11px] text-[var(--muted)] mt-2 mb-0">
            하우스뷰 데이터(public/data/houseviews.json)가 아직 없습니다. 파일이 생성되면 자동으로 채워집니다.
          </p>
        )}
        {views.length > 0 && hvRows.length === 0 && (
          <p className="text-[11px] text-[var(--muted)] mt-2 mb-0">{activeHouse.toUpperCase()} 하우스의 뷰가 없습니다.</p>
        )}

        {/* 특정 하우스를 고르면 그 하우스 뷰만 원문 목록으로 */}
        {hvMode === 'byHouse' && activeHouse !== 'ALL' && hvRows.length > 0 && (
          <div className="mt-3 border-t border-[var(--line)] pt-3">
            <div className="text-xs font-semibold text-[var(--muted)] mb-2">
              {activeHouse.toUpperCase()} 뷰 {hvRows.length}건
              {!listAll && hvRows.length > HV_LIST_MAX && (
                <span className="ml-1 font-normal">— 최신 {HV_LIST_MAX}건만 표시</span>
              )}
            </div>
            <div className="space-y-2">
              {(listAll ? hvRows : hvRows.slice(0, HV_LIST_MAX)).map((v) => (
                <div key={v.id} className="grid gap-2.5 items-start" style={{ gridTemplateColumns: '86px 150px 1fr' }}>
                  <div className="text-[11px] text-[var(--muted)]">{v.date}</div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="rounded border px-1.5 py-[1px] text-[10px] font-bold" style={stanceStyle(v.stance, v.confidence)}>{v.stance}</span>
                    <span className="text-[11px] font-semibold">{v.asset}</span>
                    <span className="text-[10px] text-[var(--muted)]">{v.region}</span>
                  </div>
                  <div className="min-w-0">
                    {v.title && <div className="text-[12px] font-semibold leading-snug">{v.title}</div>}
                    <div className="text-[11px] text-[var(--muted)] leading-snug">{v.rationale}</div>
                  </div>
                </div>
              ))}
            </div>
            {hvRows.length > HV_LIST_MAX && (
              <button onClick={() => setListAll((v) => !v)}
                className="mt-2 text-[11px] font-semibold text-[var(--badge)]">
                {listAll ? '접기' : '전체 ' + hvRows.length + '건 보기'}
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── 보고서 검색·목록 (기존) ── */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="보고서 검색 (제목, 기관, 내용)…"
          className="flex-1 min-w-[260px] bg-white border border-[var(--line)] rounded-lg px-4 py-2 text-sm" />
        <select value={src} onChange={(e) => setSrc(e.target.value)} className={sel + ' min-w-[160px]'}>
          <option value="ALL">전체 기관</option>
          {sources.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={date} onChange={(e) => setDate(e.target.value)} className={sel}>
          <option value="ALL">전체 날짜</option>
          {dates.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      <div className="rounded-xl border border-[var(--line)] bg-white overflow-hidden">
        <div className="grid items-center gap-3 px-4 py-3 text-xs font-semibold text-[var(--muted)] border-b border-[var(--line)] bg-[var(--head)]"
          style={{ gridTemplateColumns: '110px 130px 1fr 220px' }}>
          <div>날짜</div><div>기관</div><div>보고서 제목</div><div>키워드</div>
        </div>
        {filtered.map((r) => {
          const isOpen = open[r.id]
          const bullets = isOpen ? r.summary : r.summary.slice(0, 3)
          return (
            <div key={r.id} className="grid gap-3 px-4 py-4 border-b border-[var(--line)] last:border-0"
              style={{ gridTemplateColumns: '110px 130px 1fr 220px' }}>
              <div className="text-sm text-[var(--muted)]">{r.date}</div>
              <div>
                <div className="text-sm font-semibold">{r.source}</div>
                {r.section && <div className="text-[11px] text-[var(--muted)] mt-0.5">{r.section}</div>}
              </div>
              <div>
                <a href={r.file} download className="text-[15px] font-semibold text-[var(--ink)] hover:text-[var(--badge)] hover:underline">
                  {r.title}
                </a>
                <ul className="mt-1.5 space-y-1">
                  {bullets.map((b, i) => (
                    <li key={i} className="text-[13px] text-[var(--muted)] leading-snug flex gap-1.5">
                      <span className="text-[var(--line)]">▪</span><span>{b}</span>
                    </li>
                  ))}
                </ul>
                {r.summary.length > 3 && (
                  <button onClick={() => setOpen((o) => ({ ...o, [r.id]: !isOpen }))}
                    className="mt-1 text-xs font-semibold text-[var(--badge)]">
                    {isOpen ? '접기' : '더보기'}
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1 content-start">
                {r.keywords.map((k) => (
                  <span key={k} className="text-[11px] bg-[var(--head)] border border-[var(--line)] rounded px-1.5 py-0.5 text-[var(--muted)]">{k}</span>
                ))}
              </div>
            </div>
          )
        })}
        {filtered.length === 0 && <div className="px-4 py-10 text-center text-sm text-[var(--muted)]">검색 결과가 없습니다.</div>}
      </div>
      <p className="text-[11px] text-[var(--muted)] mt-2">제목을 클릭하면 원문 PDF가 다운로드됩니다. (현재 더미 데이터)</p>
    </section>
  )
}
