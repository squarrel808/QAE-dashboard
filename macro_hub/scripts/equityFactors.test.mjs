import assert from 'node:assert/strict'
import test from 'node:test'
import { rankFactors, rankingRows, periodStart } from '../lib/equityFactors.ts'
const series = (bbid, dates, close) => ({bbid, label: bbid, dates, close})
test('ranking and chart endpoints use the same calendar baseline', () => {
  const dates = ['2026-07-30', '2026-08-31', '2026-09-30', '2026-10-30']
  const input = [series('A', dates, [100, 140, 150, 160]), series('B', dates, [100, 110, 130, 170])]
  for (const period of [1, 3]) {
    const result = rankFactors(input, period)
    assert.equal(result.ranked.length, 2)
    const rows = rankingRows(result.ranked, result.start, result.end)
    for (const item of result.ranked) {
      assert.equal(rows[0][item.series.bbid], 100)
      assert.ok(Math.abs(rows.at(-1)[item.series.bbid] - 100 * (1 + item.v)) < 1e-10)
    }
  }
  assert.equal(periodStart('2026-05-31', 3), '2026-02-28')
})
test('5D uses six observations and excludes stopped series', () => {
  const dates = ['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-09']
  const input = [series('A', dates, [100, 101, 102, 103, 104, 110]), series('stopped', ['2025-01-01','2025-01-02'],[100,200])]
  const result=rankFactors(input, -5)
  assert.equal(result.start, dates[0])
  assert.equal(result.ranked.length, 1)
  assert.equal(rankingRows(result.ranked,result.start,result.end).length,6)
  assert.ok(Math.abs(result.ranked[0].v - .1) < 1e-10)
})
test('period changes recompute winners and losers and support monthly data', () => {
  const dates=['2025-10','2025-11','2026-09','2026-10']
  const input=[series('A',dates,[100,100,200,150]),series('B',dates,[100,100,100,120])]
  assert.deepEqual(rankFactors(input,1).ranked.map(x=>x.label),['B','A'])
  assert.deepEqual(rankFactors(input,12).ranked.map(x=>x.label),['A','B'])
  assert.equal(rankFactors(input,120).ranked.length,0)
})
