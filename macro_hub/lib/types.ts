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
export type PcaCountry = { label: string; label_kr?: string; versions: Record<string, PcaVersion> }
// 신버전(다국가): { default, countries } / 구버전(단일): { country, versions } — 둘 다 허용
export type PcaData = {
  country?: string
  versions?: Record<string, PcaVersion>
  default?: string
  countries?: Record<string, PcaCountry>
}

// ── CAI · MAP ──
export type CaiSeries = {
  dates: string[]
  headline: (number | null)[]
  // 국가별로 없는 섹터/타입은 배열이 아니라 null 로 들어옴 (예: JP·KR 의 Housing)
  sectors: Record<string, (number | null)[] | null>
  heatmap?: Record<string, (number | null)[] | null>   // CAI_HEATMAP_SECTOR_* (GS 라이브 지표)
  types?: Record<string, (number | null)[] | null>
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
  /** 원문 PDF 경로. 증권사 리서치는 라이선스 대상이라 배포하지 않으므로 보통 비어 있다. */
  file?: string
}

// ── House Views (운용사별 하우스뷰) ──
// public/data/houseviews.json — 리포트 원문에서 뽑아낸 하우스별 자산군·권역 스탠스.
// 한 리포트가 여러 뷰를 낳을 수 있다 (예: 미국 금리 + 일본 금리).
export type HouseStance = 'OW' | 'N' | 'UW'
// 원문에 명시적 등급이 없고 논조로 추론한 경우가 대부분이라 confidence 가 중요하다.
export type HouseConfidence = 'high' | 'mid' | 'low'
export type HouseView = {
  id: string
  date: string          // 'YYYY-MM-DD'
  house: string         // GS / JPM / BofA / Citi / HSBC / UBS
  asset: string         // 매크로 / 채권 / 주식 / 코모디티
  region: string        // US·EU·JP·CN·KR·UK·AU·EM, 권역이 무의미하면 'GLOBAL'
  stance: HouseStance
  rationale: string
  title: string
  confidence: HouseConfidence
}
export type HouseViewData = {
  generatedAt?: string
  houses: string[]
  assets: string[]
  regions: string[]
  views: HouseView[]
}
