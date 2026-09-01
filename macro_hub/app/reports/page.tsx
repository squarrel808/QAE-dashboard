import fs from 'node:fs'
import path from 'node:path'
import Reports from '@/components/Reports'
import type { HouseViewData, ReportRec } from '@/lib/types'

const EMPTY_HV: HouseViewData = { houses: [], assets: [], regions: [], views: [] }

export default function ReportsPage() {
  const dir = path.join(process.cwd(), 'public', 'data')

  let rows: ReportRec[] = []
  try {
    rows = JSON.parse(fs.readFileSync(path.join(dir, 'reports.json'), 'utf-8')) as ReportRec[]
  } catch {}

  // houseviews.json 은 별도 파이프라인이 만든다. 아직 없거나 깨져도 페이지는 떠야 한다.
  let houseViews: HouseViewData = EMPTY_HV
  try {
    const raw = JSON.parse(fs.readFileSync(path.join(dir, 'houseviews.json'), 'utf-8')) as Partial<HouseViewData>
    houseViews = {
      generatedAt: typeof raw.generatedAt === 'string' ? raw.generatedAt : undefined,
      houses: Array.isArray(raw.houses) ? raw.houses : [],
      assets: Array.isArray(raw.assets) ? raw.assets : [],
      regions: Array.isArray(raw.regions) ? raw.regions : [],
      views: Array.isArray(raw.views) ? raw.views : [],
    }
  } catch {}

  return <Reports rows={rows} houseViews={houseViews} />
}
