import type { NextConfig } from 'next'

// 주의: ibreport 대시보드는 output: 'export' (순수 정적)였습니다.
// 이 허브는 app/api/* 의 실시간 서버 라우트를 쓰기 때문에 output: 'export' 를
// 의도적으로 빼두었습니다. 이래야 Vercel이 페이지는 정적으로, /api 는
// serverless 함수로 같이 배포해줍니다. (= "정적 + 실시간 둘 다 섞기")
const nextConfig: NextConfig = {}

export default nextConfig
