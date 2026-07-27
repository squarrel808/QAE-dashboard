import RawDashboard from '@/components/RawDashboard'

// CPI 품목별 YoY 분포 (haver-api_CPI 엑셀 → "Consensus Builder/CPI distribution.py" 자체완결 HTML 임베드)
export default function CpiDistPage() {
  return <RawDashboard src="/embeds/cpi_dist.html" title="CPI 분포 · CPI YoY Distribution" />
}
