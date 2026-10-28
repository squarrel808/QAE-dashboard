import RawDashboard from '@/components/RawDashboard'
import PcaVersionLinks from '@/components/PcaVersionLinks'

export default function LegacyPcaIII() {
  return <><PcaVersionLinks model="iii" legacy /><RawDashboard src="/embeds/pca-legacy/iii/index.html" title="기존 PCA III · BlackRock 지표 · 반감기 24개월 · 비음수 제약" /></>
}
