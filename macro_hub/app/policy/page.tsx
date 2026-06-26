import fs from 'node:fs'
import path from 'node:path'
import PolicyTone from '@/components/PolicyTone'
import type { PolicyData } from '@/lib/types'

export default function PolicyPage() {
  const jsonPath = path.join(process.cwd(), 'public', 'data', 'policy.json')
  const data = JSON.parse(fs.readFileSync(jsonPath, 'utf-8')) as PolicyData
  return <PolicyTone data={data} />
}
