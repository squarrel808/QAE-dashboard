import RawDashboard from '@/components/RawDashboard'
import PcaVersionLinks from '@/components/PcaVersionLinks'

export default function LegacyPcaII() {
  return <><PcaVersionLinks model="ii" legacy /><RawDashboard src="/embeds/pca-legacy/ii/index.html" title="기존 PCA II · 반감기 24개월 · 비음수 제약" /></>
}
