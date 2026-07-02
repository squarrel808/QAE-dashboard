import RawDashboard from '@/components/RawDashboard'

// 대문(첫 페이지) — Selenium으로 긁어온 경제지표 캘린더(자체완결 HTML)를 임베드
export default function EconPage() {
  return <RawDashboard src="/embeds/econ.html" title="경제지표 · Economic Calendar" />
}
