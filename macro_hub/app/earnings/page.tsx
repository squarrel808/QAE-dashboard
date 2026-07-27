import RawDashboard from '@/components/RawDashboard'

// 기업실적 발표 달력 (releasecalendar/기업실적.xlsx → 자체완결 HTML 임베드)
export default function EarningsPage() {
  return <RawDashboard src="/embeds/earnings.html" title="실적 캘린더 · Earnings Calendar" />
}
