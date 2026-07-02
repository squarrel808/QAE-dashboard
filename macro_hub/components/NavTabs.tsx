'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

// 탭 순서 — 여기 배열 순서대로 표시됩니다.
const TABS = [
  { href: '/econ', label: '경제지표' },
  { href: '/reports', label: 'Report' },
  { href: '/pca', label: 'PCA' },
  { href: '/caimap', label: 'CAI' },
  { href: '/policy', label: 'Policy Tone' },
  { href: '/equity', label: 'Equity' },
]

export default function NavTabs() {
  const path = usePathname()
  return (
    <nav className="flex gap-2 flex-wrap mt-3">
      {TABS.map((t) => {
        const active = path.startsWith(t.href)
        return (
          <Link
            key={t.href}
            href={t.href}
            className={
              'rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ' +
              (active
                ? 'bg-[var(--badge)] text-white border-[var(--badge)]'
                : 'bg-white text-[var(--ink)] border-[var(--line)] hover:bg-[var(--head)]')
            }
          >
            {t.label}
          </Link>
        )
      })}
    </nav>
  )
}
