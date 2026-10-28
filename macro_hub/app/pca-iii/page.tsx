import RawDashboard from '@/components/RawDashboard'
import PcaVersionLinks from '@/components/PcaVersionLinks'

export default function BlackRockOnlyPcaPage() {
  return <><PcaVersionLinks model="iii" /><RawDashboard src="/embeds/pca-iii/index.html" title="PCA III · BlackRock 지표 · Level / Momentum" /></>
}
