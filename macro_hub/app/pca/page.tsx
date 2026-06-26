import fs from 'node:fs'
import path from 'node:path'
import Pca from '@/components/Pca'
import type { PcaData } from '@/lib/types'
import RawDashboard from '@/components/RawDashboard'

export default function PcaPage() {
  const p = path.join(process.cwd(), 'public', 'data', 'pca.json')
  try {
    const data = JSON.parse(fs.readFileSync(p, 'utf-8')) as PcaData
    return <Pca data={data} />
  } catch {
    // pca.json 이 없으면 원본 임베드로 폴백
    return <RawDashboard src="/embeds/pca.html" title="PCA" />
  }
}
