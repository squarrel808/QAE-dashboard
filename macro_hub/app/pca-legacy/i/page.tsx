import fs from 'node:fs'
import path from 'node:path'
import PcaLegacy from '@/components/PcaLegacy'
import PcaVersionLinks from '@/components/PcaVersionLinks'
import type { PcaData } from '@/lib/types'

export default function LegacyPcaI() {
  const data = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'public/embeds/pca-legacy/i/data.json'), 'utf8')) as PcaData
  return <><PcaVersionLinks model="i" legacy /><PcaLegacy data={data} /></>
}
