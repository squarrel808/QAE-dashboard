'use client'
import { useEffect, useRef, useState } from 'react'

/**
 * 원본(자체완결) 대시보드 HTML을 같은 도메인 iframe으로 격리 렌더한다.
 * - 전역 변수(const D, sel ...) 충돌·중복선언 문제를 iframe 스코프 격리로 원천 차단
 * - inline 이벤트 핸들러(onchange="filterCountry(...)") 도 그대로 동작
 * - same-origin 이라 onLoad에서 내용 높이를 읽어 iframe 높이를 자동 맞춤
 * 데이터는 public/embeds/<x>.html 로 제공 (scripts/sync_embeds.py 가 원본에서 복사).
 */
export default function RawDashboard({ src, title }: { src: string; title?: string }) {
  const ref = useRef<HTMLIFrameElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'missing'>('loading')

  useEffect(() => {
    let cancelled = false
    fetch(src, { method: 'GET', cache: 'no-store' })
      .then((r) => { if (!cancelled) setStatus(r.ok ? 'ready' : 'missing') })
      .catch(() => { if (!cancelled) setStatus('missing') })
    return () => { cancelled = true }
  }, [src])

  // 내용 높이에 맞춰 iframe 높이 조절 (캔버스가 setTimeout 후 그려지므로 여러 번 재시도)
  function fit() {
    const f = ref.current
    try {
      const doc = f?.contentDocument
      if (doc?.body) {
        const h = Math.max(doc.body.scrollHeight, doc.documentElement?.scrollHeight || 0)
        if (h > 0) f!.style.height = h + 'px'
      }
    } catch { /* cross-origin 아니면 무시 */ }
  }

  function onLoad() {
    fit()
    ;[150, 400, 900, 1600].forEach((t) => setTimeout(fit, t))
  }

  return (
    <section>
      {title && <h2 className="serif text-[18px] mb-3">{title}</h2>}
      {status === 'loading' && <p className="text-sm text-[var(--muted)]">불러오는 중…</p>}
      {status === 'missing' && (
        <div className="rounded-xl border border-[var(--line)] bg-white p-6 text-sm">
          <p className="font-semibold mb-2">이 모듈 데이터가 아직 동기화되지 않았어요.</p>
          <p className="text-[var(--muted)] leading-relaxed">
            터미널에서 아래 한 줄을 실행하면 원본 대시보드가 <code>public/embeds/</code>로 복사됩니다:
          </p>
          <pre className="mt-2 bg-[var(--head)] rounded-md p-3 text-xs overflow-x-auto">python scripts/sync_embeds.py</pre>
          <p className="text-[var(--muted)] mt-2">그 다음 새로고침하세요.</p>
        </div>
      )}
      {status === 'ready' && (
        <iframe
          ref={ref}
          src={src}
          onLoad={onLoad}
          title={title || src}
          className="w-full rounded-xl border border-[var(--line)] bg-white"
          style={{ border: 'none', minHeight: '85vh' }}
        />
      )}
    </section>
  )
}
