import fs from 'node:fs'
import path from 'node:path'
import Reports from '@/components/Reports'
import type { ReportRec } from '@/lib/types'

export default function ReportsPage() {
  const p = path.join(process.cwd(), 'public', 'data', 'reports.json')
  let rows: ReportRec[] = []
  try {
    rows = JSON.parse(fs.readFileSync(p, 'utf-8')) as ReportRec[]
  } catch {}
  return <Reports rows={rows} />
}
