import type { Metadata } from 'next'
import './globals.css'
import NavTabs from '@/components/NavTabs'

export const metadata: Metadata = {
  title: 'Macro Dashboard',
  description: 'QAE 통합 매크로 대시보드 (Next.js 허브)',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="px-6 pt-4 pb-2">
          <h1 className="serif text-[22px] m-0">Macro Dashboard</h1>
          <NavTabs />
        </header>
        <main className="px-6 pb-10">{children}</main>
      </body>
    </html>
  )
}
