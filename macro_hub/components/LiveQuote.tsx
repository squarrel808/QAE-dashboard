'use client'
import { useEffect, useState } from 'react'

// 실시간 API 데모: 마운트될 때 우리 서버(/api/quote)에 물어봅니다.
// 키는 서버에만 있으므로 브라우저 코드 어디에도 키가 없습니다.
export default function LiveQuote({ symbol = 'AAPL' }: { symbol?: string }) {
  const [state, setState] = useState<{ price?: number | null; error?: string } | null>(null)

  useEffect(() => {
    fetch(`/api/quote?symbol=${symbol}`)
      .then((r) => r.json())
      .then(setState)
      .catch((e) => setState({ error: String(e) }))
  }, [symbol])

  return (
    <div className="rounded-xl border border-[var(--line)] bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="serif text-base m-0">실시간 API 데모</h2>
        <span className="text-[10px] text-[var(--badge)] font-semibold">LIVE · 서버 경유</span>
      </div>
      <p className="text-xs text-[var(--muted)] mt-2 mb-3">
        브라우저 → /api/quote(서버, 키 보관) → 외부 API. 키는 화면에 노출되지 않습니다.
      </p>
      {state == null && <span className="text-sm text-[var(--muted)]">불러오는 중…</span>}
      {state?.error && <span className="text-sm text-[var(--down)]">{state.error}</span>}
      {state && !state.error && (
        <span className="text-2xl font-bold">
          {symbol} <span className="text-[var(--up)]">{state.price ?? '—'}</span>
        </span>
      )}
    </div>
  )
}
