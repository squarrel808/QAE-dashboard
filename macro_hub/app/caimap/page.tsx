import fs from 'node:fs'
import path from 'node:path'
import CaiMap from '@/components/CaiMap'
import type { CaiMapData } from '@/lib/types'
import RawDashboard from '@/components/RawDashboard'

export default function CaiMapPage() {
  const p = path.join(process.cwd(), 'public', 'data', 'caimap.json')
  try {
    const data = JSON.parse(fs.readFileSync(p, 'utf-8')) as CaiMapData
    return <CaiMap data={data} />
  } catch {
    return <RawDashboard src="/embeds/caimap.html" title="CAI · MAP" />
  }
}
