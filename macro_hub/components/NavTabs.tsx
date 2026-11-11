'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

// 탭 순서 — 여기 배열 순서대로 표시됩니다.
const TABS = [
  { href: '/econ', label: '경제지표' },
  { href: '/context-macro', label: 'Context Macro' },
  { href: '/earnings', label: '실적 캘린더' },
  { href: '/reports', label: 'Report' },
  { href: '/country-indicators', label: '국가별 경제지표' },
  { href: '/pca', label: 'PCA' },
  { href: '/caimap', label: 'CAI' },
  { href: '/cpidist', label: 'CPI 분포' },
  { href: '/consensus', label: 'Consensus' },
  { href: '/surprise', label: 'Surprise Index' },
  { href: '/pmi', label: 'PMI' },
  { href: '/policy', label: 'Policy Tone' },
  { href: '/equity', label: 'Factor' },
  { href: '/theme', label: 'Theme' },
  { href: '/market-rotation', label: 'Market Rotation' },
  { href: '/weekly/index.html', label: '주간 시황' },
]

const PCA_TABS = [
  { href: '/pca', label: 'PCA I' },
  { href: '/gdp-pca', label: 'PCA II' },
  { href: '/pca-iii', label: 'PCA III' },
]

export default function NavTabs() {
  const path = usePathname()
  const isPca = PCA_TABS.some((t) => path === t.href || path.startsWith(t.href + '/'))
    || path === '/pca-legacy' || path.startsWith('/pca-legacy/') || path === '/pca-comparison'
  return (
    <>
    <nav aria-label="주 메뉴" className="flex gap-2 flex-wrap mt-3">
      {TABS.map((t) => {
        const active = t.href === '/pca' ? isPca : path === t.href || path.startsWith(t.href + '/')
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={active ? 'page' : undefined}
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
    {isPca && (
      <nav aria-label="PCA 모델 선택" className="flex flex-wrap gap-2 mt-3 rounded-lg border border-[var(--line)] bg-[var(--head)] p-2">
        {PCA_TABS.map((t) => {
          const active = path === t.href || path.startsWith(t.href + '/')
          return (
            <Link
              key={t.href}
              href={t.href}
              aria-current={active ? 'page' : undefined}
              className={'rounded-md px-4 py-2 text-sm font-semibold transition-colors ' + (
                active ? 'bg-[var(--badge)] text-white' : 'bg-white text-[var(--ink)] hover:bg-[var(--line)]'
              )}
            >
              {t.label}
            </Link>
          )
        })}
      </nav>
    )}
    </>
  )
}
