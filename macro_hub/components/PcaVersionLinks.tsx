import Link from 'next/link'

export default function PcaVersionLinks({ model, legacy = false }: { model: 'i' | 'ii' | 'iii'; legacy?: boolean }) {
  const current = { i: '/pca', ii: '/gdp-pca', iii: '/pca-iii' }
  return <div className="rounded-lg border border-[var(--line)] bg-[var(--head)] px-4 py-3 mb-4 text-sm flex gap-3 flex-wrap items-center">
    <span className="font-semibold">{legacy ? '기존 방식 · 변경 직전 게시본' : '현재 방식 · CFNAI형 PCA'}</span>
    <Link className="underline" href={legacy ? current[model] : `/pca-legacy/${model}`}>{legacy ? '현재 방식 보기' : '기존 방식 보기'}</Link>
    <Link className="underline" href="/pca-legacy">기존 I·II·III 모아보기</Link>
    <Link className="underline" href="/pca-comparison">변경 전후 비교</Link>
    {legacy && <span className="text-xs text-[var(--muted)] w-full">2026-10-29 보관 · 자동 갱신하지 않는 고정본. 기존 반감기·부호 제약·Momentum 산식을 유지합니다.</span>}
  </div>
}
