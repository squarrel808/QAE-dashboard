import { NextResponse } from 'next/server'

// 이 파일은 Vercel에서 '서버리스 함수'로 배포됩니다(브라우저가 아니라 서버에서 실행).
// 그래서 API 키(FMP_API_KEY)가 브라우저에 절대 노출되지 않습니다.
//   브라우저 → /api/quote?symbol=AAPL → (서버가 키 들고) 외부 API → 결과만 반환
export const revalidate = 60 // 같은 응답을 60초 캐시 (호출 비용 절약)

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const symbol = (searchParams.get('symbol') || 'AAPL').toUpperCase()
  const key = process.env.FMP_API_KEY

  if (!key) {
    // 키 미설정 시에도 화면이 깨지지 않도록 안내 메시지 반환
    return NextResponse.json(
      { symbol, error: 'FMP_API_KEY 미설정 (.env.local 또는 Vercel 환경변수에 추가하세요)' },
      { status: 200 }
    )
  }

  try {
    const url = `https://financialmodelingprep.com/api/v3/quote-short/${symbol}?apikey=${key}`
    const r = await fetch(url, { next: { revalidate: 60 } })
    const arr = await r.json()
    const q = Array.isArray(arr) ? arr[0] : null
    return NextResponse.json({ symbol, price: q?.price ?? null, ts: Date.now() })
  } catch (e) {
    return NextResponse.json({ symbol, error: String(e) }, { status: 200 })
  }
}
