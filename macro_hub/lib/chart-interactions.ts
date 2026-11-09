// Shared behavior for native SVG dashboards, including same-origin embeds.
export function enhanceCharts(doc: Document) {
  const win = doc.defaultView
  if (!win) return () => {}
  const tip = doc.createElement('div')
  tip.setAttribute('role', 'tooltip')
  tip.style.cssText = 'display:none;position:fixed;z-index:10000;pointer-events:none;background:white;border:1px solid #cbd5e1;border-radius:6px;padding:9px 12px;box-shadow:0 3px 14px #0002;color:#334e68;font:12px/1.6 Arial,sans-serif;white-space:pre-line;max-width:340px'
  doc.body.append(tip)
  const hide = () => { tip.style.display = 'none' }
  const move = (e: PointerEvent) => {
    const target = e.target as Element
    const svg = target.closest?.('svg:not(.recharts-surface)')
    let label = target.closest?.('[title]')?.getAttribute('title') || ''
    if (svg) {
      let best = Infinity
      for (const title of svg.querySelectorAll('title')) {
        const mark = title.parentElement
        if (!mark || mark === svg || mark.tagName.toLowerCase() === 'text') continue
        const r = mark.getBoundingClientRect()
        const dx = Math.max(r.left-e.clientX, 0, e.clientX-r.right)
        const dy = Math.max(r.top-e.clientY, 0, e.clientY-r.bottom)
        const distance = Math.hypot(dx, dy)
        if (distance < best && distance < 24) { best = distance; label = title.textContent || '' }
      }
    }
    if (!label) { hide(); return }
    tip.textContent = label
    tip.style.display = 'block'
    tip.style.left = Math.max(4, Math.min(e.clientX+14, win.innerWidth-tip.offsetWidth-8))+'px'
    tip.style.top = Math.max(4, Math.min(e.clientY+14, win.innerHeight-tip.offsetHeight-8))+'px'
  }
  const style = doc.createElement('style')
  style.textContent = `.qae-heatmap{border-collapse:collapse!important;border-spacing:0!important;font:11px/1.5 Arial,sans-serif!important;color:#526b80!important}.qae-heatmap th{background:#f3f6f9!important;color:#688096!important;font-size:11px!important;padding:8px!important}.qae-heatmap td{font-size:11px!important;padding:7px 6px!important;border-radius:0!important;font-weight:400!important;text-align:center}.qae-heatmap td span{border-radius:0!important;font-weight:400!important}`
  doc.head.append(style)
  const refresh = () => {
    for (const table of doc.querySelectorAll('table')) {
      if (table.querySelector('td[style*="background"],td [style*="background"]')) table.classList.add('qae-heatmap')
    }
  }
  refresh()
  const observer = new MutationObserver(refresh)
  observer.observe(doc.body, {childList:true, subtree:true})
  doc.addEventListener('pointermove', move)
  doc.addEventListener('pointerleave', hide)
  win.addEventListener('scroll', hide, true)
  return () => { observer.disconnect(); doc.removeEventListener('pointermove',move); doc.removeEventListener('pointerleave',hide); win.removeEventListener('scroll',hide,true); tip.remove(); style.remove() }
}
