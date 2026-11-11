import assert from 'node:assert/strict'
import test from 'node:test'
import { factorReturns } from '../lib/factorHeatmap.ts'
const series = (id, dates, close) => ({ bbid: id, label: id, dates, close })
test('daily compares exact adjacent sessions and leaves missing endpoints blank', () => {
  const a = series('A', ['2026-01-30','2026-02-02','2026-02-03'], [100,110,99])
  const b = series('B', ['2026-01-30','2026-02-03'], [100,120])
  const r = factorReturns([a,b], 'daily','2026-02-03')
  assert.ok(Math.abs(r.values[0][1]-.1)<1e-12)
  assert.ok(Math.abs(r.values[0][2]+.1)<1e-12)
  assert.equal(r.values[1][2],null)
})
test('monthly compounds month-end levels and includes partial current month only to cutoff', () => {
  const a = series('A',['2025-12-31','2026-01-15','2026-01-30','2026-02-02','2026-02-03'],[100,120,110,121,133.1])
  const r = factorReturns([a], 'monthly','2026-02-02')
  assert.deepEqual(r.columns,['2025-12','2026-01','2026-02'])
  assert.ok(Math.abs(r.values[0][1]-.1)<1e-12)
  assert.ok(Math.abs(r.values[0][2]-.1)<1e-12)
  assert.equal(r.latest,'2026-02-02')
})
test('missing calendar month cannot become a one-month return', () => {
  const a=series('A',['2026-01-30','2026-03-31'],[100,150])
  assert.equal(factorReturns([a],'monthly','2026-03-31').values[0][1],null)
  assert.equal(factorReturns([a],'daily','2026-03-31').values[0][1],null)
})
