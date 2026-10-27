'use client'

import { useEffect, useState } from 'react'
import EquityFactors from './EquityFactors'
import type { PairBasketsData } from '@/lib/types'

// Keep daily history out of prerendered HTML/RSC (Vercel's 20 MB page limit).
export default function EquityLoader() {
  const [data, setData] = useState<PairBasketsData | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError(false)
    fetch('/data/pairbaskets.json', { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<PairBasketsData>
      })
      .then(value => { if (!controller.signal.aborted) setData(value) })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [attempt])
  if (data) return <EquityFactors data={data} />
  if (error) return <div role="alert" className="p-6">데이터를 불러오지 못했습니다. <button className="underline" onClick={() => setAttempt(n => n + 1)}>다시 시도</button></div>
  return <p role="status" className="p-6 text-[var(--muted)]">일별 바스켓 데이터를 불러오는 중입니다…</p>
}
