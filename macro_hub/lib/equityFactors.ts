import type { Series } from './types'

export type RankedFactor = { series: Series; label: string; nameNote?: string; v: number; base: number }
export type FactorRow = Record<string, number | string | null>

export function periodStart(end: string, months: number): string {
  const date = new Date(end.length === 7 ? `${end}-01T00:00:00Z` : `${end}T00:00:00Z`)
  const day = date.getUTCDate()
  date.setUTCDate(1)
  date.setUTCMonth(date.getUTCMonth() - months)
  const last = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate()
  date.setUTCDate(Math.min(day, last))
  return date.toISOString().slice(0, end.length)
}

export function rankFactors(series: Series[], period: number) {
  const dates = [...new Set(series.flatMap(item => item.dates))].sort()
  const end = dates.at(-1) || ''
  const start = period === -5 ? dates.at(-6) || '' : end ? periodStart(end, period) : ''
  const ranked: RankedFactor[] = []
  if (!start) return { start, end, ranked }
  for (const item of series) {
    // Use the same observation date and baseline for ranking and its chart.
    if (item.dates.at(-1) !== end) continue
    let baseIndex = -1
    item.dates.forEach((date, i) => { if (date <= start) baseIndex = i })
    const base = item.close[baseIndex], last = item.close.at(-1)
    if (baseIndex < 0 || !Number.isFinite(base) || base <= 0 || last == null || !Number.isFinite(last)) continue
    ranked.push({ series: item, label: item.label, nameNote: item.nameNote, base, v: last / base - 1 })
  }
  ranked.sort((a, b) => b.v - a.v || a.series.bbid.localeCompare(b.series.bbid))
  return { start, end, ranked }
}

export function rankingRows(items: RankedFactor[], start: string, end: string): FactorRow[] {
  if (!items.length || !start) return []
  const dates = [...new Set([start, ...items.flatMap(item => item.series.dates.filter(date => date > start && date <= end))])].sort()
  const rows: FactorRow[] = dates.map(month => ({ month }))
  for (const item of items) {
    let cursor = -1
    dates.forEach((date, i) => {
      while (cursor + 1 < item.series.dates.length && item.series.dates[cursor + 1] <= date) cursor++
      const value = item.series.close[cursor]
      rows[i][item.series.bbid] = Number.isFinite(value) ? value / item.base * 100 : null
    })
  }
  return rows
}
