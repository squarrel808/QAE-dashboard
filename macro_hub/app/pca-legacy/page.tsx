import Link from 'next/link'

export default function LegacyPcaIndex() {
  const items = [
    ['i', 'PCA I', 'Level 반감기 24개월 · 월별 일반 PCA · Momentum 별도 PCA(12개월 반감기)'],
    ['ii', 'PCA II', '반감기 24개월 · 월별 비음수 제약 PCA · 기존 전체 지표 · 연초 GDP 비중'],
    ['iii', 'PCA III', 'PCA II와 같은 방법 · BlackRock 참조 지표만 사용'],
  ]
  return <section className="rounded-xl border border-[var(--line)] bg-white p-6">
    <h2 className="serif text-xl mb-3">기존 PCA I·II·III 보관본</h2>
    <p className="text-sm text-[var(--muted)] mb-5">CFNAI 방식으로 변경하기 직전의 게시 화면과 수치를 복원했습니다. 2026-10-29 보관한 고정본이며 자동 갱신하지 않습니다. II·III의 음수 로딩 제약도 기존대로 유지합니다.</p>
    <div className="grid md:grid-cols-3 gap-4">{items.map(([id, name, detail]) =>
      <Link key={id} href={`/pca-legacy/${id}`} className="rounded-xl border border-[var(--line)] p-5 hover:bg-[var(--head)]">
        <h3 className="font-semibold text-lg mb-2">{name} · 기존 방식</h3><p className="text-sm text-[var(--muted)]">{detail}</p><p className="mt-4 underline">열기 →</p>
      </Link>
    )}</div>
    <p className="text-sm mt-5">현재 방식: <Link className="underline" href="/pca">PCA I</Link> · <Link className="underline" href="/gdp-pca">PCA II</Link> · <Link className="underline" href="/pca-iii">PCA III</Link> · <Link className="underline" href="/pca-comparison">미국·영국 전후 비교</Link></p>
    <p className="text-xs text-[var(--muted)] mt-4">비교 보고서는 같은 원자료로 예전 방식을 재계산한 결과입니다. 이 보관 화면은 변경 직전 실제 게시본이므로 일부 수치가 다를 수 있습니다.</p>
  </section>
}
