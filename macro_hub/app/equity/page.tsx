import fs from 'node:fs'
import path from 'node:path'
import EquityFactors from '@/components/EquityFactors'
import type { PairBasketsData } from '@/lib/types'

// 서버 컴포넌트: 빌드/요청 시 서버에서 JSON 파일을 읽어 클라이언트 컴포넌트로 넘김.
// (ibreport 의 app/keyword_trend/page.tsx 와 동일한 패턴)
export default function EquityPage() {
  const jsonPath = path.join(process.cwd(), 'public', 'data', 'pairbaskets.json')
  const data = JSON.parse(fs.readFileSync(jsonPath, 'utf-8')) as PairBasketsData
  return <EquityFactors data={data} />
}
