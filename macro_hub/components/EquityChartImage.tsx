'use client'

import { useMemo } from 'react'

type PlotSeries = { key: string; label: string; color: string }
type Row = Record<string, number | string | null>
const esc = (s: string) => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[c]!)

// Render actual observations as a standalone SVG image, also available to save.
export default function EquityChartImage({ rows, series, title }: { rows: Row[]; series: PlotSeries[]; title: string }) {
  const src = useMemo(() => {
    const width = 1400, left = 65, right = 25, top = 45, bottom = 345
    const height = 405 + Math.ceil(series.length / 4) * 24
    const values = rows.flatMap(r => series.map(s => r[s.key]).filter((v): v is number => typeof v === 'number' && Number.isFinite(v)))
    let lo = 100, hi = 100
    values.forEach(v => { lo = Math.min(lo, v); hi = Math.max(hi, v) })
    const pad = Math.max((hi - lo) * 0.06, 1)
    lo -= pad; hi += pad
    const times = rows.map(r => Date.parse(String(r.month)))
    const first = times[0] || 0, span = (times[times.length - 1] || first) - first || 1
    const x = (i: number) => left + (times[i] - first) / span * (width - left - right)
    const y = (v: number) => bottom - (v - lo) / (hi - lo) * (bottom - top)
    const parts = [`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial, Malgun Gothic, sans-serif" font-size="12" fill="#586271"><text x="${left}" y="23" font-size="16" fill="#172536">${esc(title)}</text>`]
    for (let i = 0; i <= 5; i++) {
      const v = lo + (hi - lo) * i / 5, py = y(v)
      parts.push(`<path d="M${left} ${py}H${width - right}" stroke="#e5e9ee"/><text x="${left - 10}" y="${py + 4}" text-anchor="end">${v.toFixed(0)}</text>`)
    }
    if (rows.length) {
      const indices = [...new Set(Array.from({ length: Math.min(7, rows.length) }, (_, i) => Math.round(i * (rows.length - 1) / Math.max(1, Math.min(7, rows.length) - 1))))]
      indices.forEach(i => parts.push(`<text x="${x(i)}" y="${bottom + 24}" text-anchor="${i === 0 ? 'start' : i === rows.length - 1 ? 'end' : 'middle'}">${esc(String(rows[i].month))}</text>`))
    }
    series.forEach((s, j) => {
      let d = '', active = false
      rows.forEach((r, i) => {
        const v = r[s.key]
        if (typeof v !== 'number' || !Number.isFinite(v)) { active = false; return }
        d += `${active ? 'L' : 'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`
        active = true
      })
      parts.push(`<path d="${d}" fill="none" stroke="${s.color}" stroke-width="1.6" stroke-linejoin="round"/>`)
      const lx = left + (j % 4) * 330, ly = 402 + Math.floor(j / 4) * 24
      const label = s.label.length > 40 ? s.label.slice(0, 37) + '…' : s.label
      parts.push(`<path d="M${lx} ${ly - 4}h18" stroke="${s.color}" stroke-width="2"/><text x="${lx + 24}" y="${ly}"><title>${esc(s.label)}</title>${esc(label)}</text>`)
    })
    if (!values.length) parts.push(`<text x="700" y="190" text-anchor="middle">표시할 데이터가 없습니다</text>`)
    parts.push('</g></svg>')
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(parts.join(''))}`
  }, [rows, series, title])

  return <div>
    {/* A real image element keeps browser save/copy-image actions available. */}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={src} alt={title} className="w-full h-auto" />
    <div className="text-right mt-1"><a href={src} download="equity-chart.svg" className="text-xs text-[var(--muted)] underline">그래프 이미지 저장</a></div>
  </div>
}
