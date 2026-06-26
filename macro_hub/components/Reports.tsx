'use client'
import { useMemo, useState } from 'react'
import type { ReportRec } from '@/lib/types'

export default function Reports({ rows }: { rows: ReportRec[] }) {
  const [q, setQ] = useState('')
  const [src, setSrc] = useState('ALL')
  const [date, setDate] = useState('ALL')
  const [open, setOpen] = useState<Record<string, boolean>>({})

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

  const sel = 'bg-white border border-[var(--line)] rounded-lg px-3 py-2 text-sm'

  return (
    <section>
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
