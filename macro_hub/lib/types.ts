// pairbaskets.json 의 데이터 형태 (Python 빌드 스크립트가 생성)
export type Series = {
  label: string
  bbid: string
  dates: string[]   // 'YYYY-MM' 월별
  close: number[]
}
export type SectorItem = Series & { sector: string; factor: string }

export type PairBasketsData = {
  groups: Record<string, Series[]>          // { Factor: [...], Tech: [...] }
  sector: { sectors: string[]; factors: string[]; items: SectorItem[] }
  universe?: Series[]
  generatedAt?: string
}

// ── Policy Tone ──
export type PolicyEvent = { sp: string; rs: string; st: number }
export type PolicyBank = {
  label: string
  dates: string[]
  bar: number[]
  trend: number[]
  events: Record<string, PolicyEvent[]>
}
export type PolicyData = {
  banks: Record<string, PolicyBank>
  neutralBand?: number
  smoothWindow?: number
  generatedAt?: string
}

// ── Consensus (CPI/GDP 브로커 예측 분포) ──
export type ConsensusCountry = {
  '2w': { date: string; values: number[] }[]
  '6m': { date: string; values: number[] }[]
  ml: { d: string; med: number; q1: number; q3: number }[]
  bw: number
}
export type ConsensusBundle = {
  data: Record<string, ConsensusCountry>
  names: Record<string, string>
  generatedAt?: string
}

// ── PCA (활동지수 요인 분해) ──
export type PcaVersion = {
  dates: string[]
  gdp: { index: (number | null)[]; contrib: Record<string, (number | null)[]> }
  lei: { index: (number | null)[] }
  categories: Record<string, { index: (number | null)[]; indicators: Record<string, (number | null)[]> }>
}
export type PcaData = { country: string; versions: Record<string, PcaVersion> }

// ── CAI · MAP ──
export type CaiSeries = {
  dates: string[]
  headline: (number | null)[]
  sectors: Record<string, (number | null)[]>
  heatmap?: Record<string, (number | null)[]>   // CAI_HEATMAP_SECTOR_* (GS 라이브 지표)
  types?: Record<string, (number | null)[]>
  completion?: (number | null)[] | null
  innovation?: unknown                            // GS가 2020-10-23 이후 발표 중단 → 미사용
}
export type CaiMapData = {
  countries: { id: string; label: string }[]
  cai: Record<string, CaiSeries>
  map: Record<string, CaiSeries>
  sectors: string[]
}

// ── Reports (PDF 요약 검색) ──
export type ReportRec = {
  id: string
  date: string
  source: string
  section: string
  title: string
  summary: string[]
  keywords: string[]
  file: string
}
