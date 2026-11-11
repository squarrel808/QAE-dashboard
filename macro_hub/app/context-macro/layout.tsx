'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const views = [
  { href: '/context-macro', label: 'IB 거시 맥락' },
  { href: '/context-macro/indicators', label: '매크로 지표와 IB 해석' },
]

export default function ContextMacroLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname()
  return <>
    <nav aria-label="Context Macro 화면 선택" className="flex flex-wrap gap-2 mb-4 mt-2">
      {views.map(view => <Link key={view.href} href={view.href}
        aria-current={path === view.href ? 'page' : undefined}
        className={'rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ' +
          (path === view.href ? 'bg-[var(--badge)] text-white border-[var(--badge)]' : 'bg-white text-[var(--ink)] border-[var(--line)] hover:bg-[var(--head)]')}>
        {view.label}
      </Link>)}
    </nav>
    {children}
  </>
}
