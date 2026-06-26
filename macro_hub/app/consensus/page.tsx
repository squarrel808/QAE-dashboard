import fs from 'node:fs'
import path from 'node:path'
import Consensus from '@/components/Consensus'
import type { ConsensusBundle } from '@/lib/types'

function read(name: string): ConsensusBundle {
  const p = path.join(process.cwd(), 'public', 'data', name)
  try {
    return JSON.parse(fs.readFileSync(p, 'utf-8')) as ConsensusBundle
  } catch {
    return { data: {}, names: {} }
  }
}

export default function ConsensusPage() {
  const cpi = read('consensus_cpi.json')
  const gdp = read('consensus_gdp.json')
  return <Consensus cpi={cpi} gdp={gdp} />
}
