import RawDashboard from '@/components/RawDashboard'
import PcaVersionLinks from '@/components/PcaVersionLinks'

export default function GdpWeightedPcaPage() {
  return <><PcaVersionLinks model="ii" /><RawDashboard src="/embeds/gdp-weighted/index.html" title="PCA II · Consumer / Capex / Housing / Export" /></>
}
