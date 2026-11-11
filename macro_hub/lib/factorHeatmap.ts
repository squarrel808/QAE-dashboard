import type { Series } from './types'

export function factorReturns(series: Series[], frequency: 'daily' | 'monthly', end: string) {
  const dates = [...new Set(series.flatMap(s => s.dates.filter(d => d.length === 10 && d <= end)))].sort()
  const maps = series.map(s => new Map(s.dates.map((d, i) => [d, s.close[i]])))
  const columns = frequency === 'daily' ? dates : [...new Set(dates.map(d => d.slice(0, 7)))]
  const monthEnds = new Map<string, string>()
  dates.forEach(d => monthEnds.set(d.slice(0, 7), d))
  const values = series.map((_, row) => columns.map((column, i) => {
    const current = frequency === 'daily' ? column : monthEnds.get(column)!
    let previous: string | undefined
    if (frequency === 'daily') previous = dates[i - 1]
    else {
      const d = new Date(`${column}-01T00:00:00Z`)
      d.setUTCMonth(d.getUTCMonth() - 1)
      previous = monthEnds.get(d.toISOString().slice(0, 7))
    }
    if (!previous) return null
    if (frequency === 'daily' && Date.parse(current) - Date.parse(previous) > 7 * 86400000) return null
    const a = maps[row].get(previous), b = maps[row].get(current)
    return a != null && b != null && Number.isFinite(a) && Number.isFinite(b) && a > 0 ? b / a - 1 : null
  }))
  return { columns, values, latest: dates.at(-1) || '' }
}
