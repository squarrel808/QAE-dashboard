/* 원본 "Consensus Builder/CPI consensus.py" 의 캔버스 드로잉 로직을 그대로 포팅.
   KDE ridge plot + median/IQR 밴드 차트. React 컴포넌트가 canvas ref로 호출한다. */
/* eslint-disable @typescript-eslint/no-explicit-any */

const CL = [[46,139,87],[60,160,100],[80,180,115],[110,195,130],[145,210,150],[185,220,160],[215,225,140],[240,210,100],[245,180,60],[240,145,40],[230,110,30],[220,90,20],[210,75,15],[200,60,10]]
const MO: Record<string, string> = { '01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'May','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Oct','11':'Nov','12':'Dec' }

export type RidgeItem = { date: string; values: number[] }
export type MedianPoint = { d: string; med: number; q1: number; q3: number }

function kde(data: number[], lo: number, hi: number, n: number, bw: number) {
  const r: { x: number; y: number }[] = []
  const safeBw = Math.max(bw || 0, 0.01)
  const s = (hi - lo) / (n - 1 || 1)
  for (let i = 0; i < n; i++) {
    const x = lo + i * s
    let v = 0
    for (const d of data) { const z = (x - d) / safeBw; v += Math.exp(-0.5 * z * z) }
    r.push({ x, y: v / (data.length * safeBw * Math.sqrt(2 * Math.PI)) })
  }
  return r
}

function fky(c: { x: number; y: number }[], x: number) {
  let b = c[0]
  for (const p of c) if (Math.abs(p.x - x) < Math.abs(b.x - x)) b = p
  return b.y
}

function gc(i: number, N: number) {
  const t = N > 1 ? i / (N - 1) : 0
  const idx = t * (CL.length - 1)
  const lo = Math.floor(idx), hi = Math.min(lo + 1, CL.length - 1), f = idx - lo
  return [
    Math.round(CL[lo][0] + (CL[hi][0] - CL[lo][0]) * f),
    Math.round(CL[lo][1] + (CL[hi][1] - CL[lo][1]) * f),
    Math.round(CL[lo][2] + (CL[hi][2] - CL[lo][2]) * f),
  ]
}

export function buildRidgeState(items: RidgeItem[], bw: number) {
  const N = items.length
  if (!N) return null
  const trimmedItems = items.map((it) => {
    const sv = [...it.values].sort((a, b) => a - b)
    const tv = sv.length > 2 ? sv.slice(1, -1) : sv
    return { date: it.date, values: it.values, trimmed: tv }
  })
  const allTrimmed = trimmedItems.flatMap((it) => it.trimmed).filter((v) => Number.isFinite(v))
  if (!allTrimmed.length) return null
  const tMin = Math.min(...allTrimmed), tMax = Math.max(...allTrimmed)
  const spread = Math.max(tMax - tMin, 0.2)
  const pad = spread * 0.25
  const xL = tMin - pad, xH = tMax + pad
  let maxY = 0
  const curves = trimmedItems.map((it) => {
    const c = kde(it.trimmed, xL, xH, 250, bw)
    for (const p of c) if (p.y > maxY) maxY = p.y
    return c
  })
  return { items: trimmedItems, bw, xL, xH, maxY, curves }
}

export function drawRidge(cv: HTMLCanvasElement, state: any, lp: number, sharedMaxY: number) {
  if (!state || !state.items || !state.items.length) return
  const items = state.items, cs = state.curves, xL = state.xL, xH = state.xH
  const mY = Math.max(sharedMaxY || state.maxY || 0, 1e-6)
  const N = items.length
  const range = xH - xL
  const dpr = window.devicePixelRatio || 1
  const W = 640, pH = 120, rS = N <= 8 ? 36 : N <= 12 ? 30 : 24
  const tP = 14, bP = 30, rP = 14
  const H = tP + pH + (N - 1) * rS + bP
  cv.width = W * dpr; cv.height = H * dpr
  cv.style.width = '100%'; cv.style.height = 'auto'; cv.style.maxWidth = W + 'px'
  const x = cv.getContext('2d')!; x.scale(dpr, dpr)
  const pL = lp, pR = W - rP
  const xP = (v: number) => pL + ((v - xL) / (xH - xL || 1)) * (pR - pL)
  x.strokeStyle = 'rgba(0,0,0,.07)'; x.lineWidth = 0.5; x.setLineDash([2, 4])
  const st = range > 2 ? 1 : range > 0.8 ? 0.5 : 0.2
  for (let v = Math.ceil(xL / st) * st; v <= xH + 1e-9; v += st) {
    const px = xP(v); x.beginPath(); x.moveTo(px, tP - 3); x.lineTo(px, H - bP + 6); x.stroke()
  }
  x.setLineDash([])
  x.font = '10px DM Sans,sans-serif'; x.fillStyle = 'rgba(90,95,102,0.8)'; x.textAlign = 'center'
  for (let v = Math.ceil(xL / st) * st; v <= xH + 1e-9; v += st) x.fillText(v.toFixed(st < 1 ? 1 : 0) + '%', xP(v), H - bP + 18)
  for (let i = N - 1; i >= 0; i--) {
    const c = cs[i]; const bl = tP + pH + i * rS; const [r, g, b] = gc(i, N)
    x.beginPath(); x.moveTo(xP(c[0].x), bl)
    for (const pt of c) x.lineTo(xP(pt.x), bl - (pt.y / mY) * pH)
    x.lineTo(xP(c[c.length - 1].x), bl); x.closePath()
    const gd = x.createLinearGradient(0, bl - pH, 0, bl)
    gd.addColorStop(0, `rgba(${r},${g},${b},0.8)`); gd.addColorStop(0.5, `rgba(${r},${g},${b},0.6)`); gd.addColorStop(1, 'rgba(255,255,255,0.4)')
    x.fillStyle = gd; x.fill()
  }
  for (let i = N - 1; i >= 0; i--) {
    const c = cs[i]; const bl = tP + pH + i * rS; const [r, g, b] = gc(i, N)
    x.beginPath(); let s = false
    for (const pt of c) {
      if (pt.y > 0.01) { const px = xP(pt.x), py = bl - (pt.y / mY) * pH; if (!s) { x.moveTo(px, py); s = true } else x.lineTo(px, py) }
    }
    x.strokeStyle = `rgb(${Math.min(r + 40, 255)},${Math.min(g + 40, 255)},${Math.min(b + 30, 255)})`; x.lineWidth = 1.8; x.stroke()
  }
  for (let i = N - 1; i >= 0; i--) {
    const c = cs[i]; const bl = tP + pH + i * rS; const [r, g, b] = gc(i, N)
    const tm = items[i].trimmed
    const mn = Math.min(...tm), mx = Math.max(...tm)
    const av = tm.reduce((a: number, b: number) => a + b, 0) / tm.length
    const dc = `rgb(${Math.min(r + 50, 255)},${Math.min(g + 50, 255)},${Math.min(b + 40, 255)})`
    const lc = `rgba(${Math.min(r + 70, 255)},${Math.min(g + 70, 255)},${Math.min(b + 50, 255)},0.8)`
    const dot = (xV: number, sz: number, lb: string, side: string) => {
      const ky = fky(c, xV); const px = xP(xV), py = bl - (ky / mY) * pH
      x.beginPath(); x.arc(px, py, sz, 0, Math.PI * 2); x.fillStyle = dc; x.fill(); x.strokeStyle = 'rgba(0,0,0,0.35)'; x.lineWidth = 1.2; x.stroke()
      if (lb) { x.fillStyle = lc; x.font = '600 11px DM Sans,sans-serif'; x.textAlign = (side === 'center' ? 'center' : side) as CanvasTextAlign; const o = side === 'left' ? 6 : side === 'right' ? -6 : 0; x.fillText(lb, px + o, py - 6) }
    }
    dot(av, 3.5, av.toFixed(2) + '%', 'center'); dot(mn, 2, mn.toFixed(2) + '%', 'right'); dot(mx, 2, mx.toFixed(2) + '%', 'left')
    const d = items[i].date; const ds = MO[d.slice(5, 7)] + ' ' + parseInt(d.slice(8))
    x.textAlign = 'right'; x.fillStyle = 'rgba(26,28,31,0.85)'; x.font = '600 12px DM Sans,sans-serif'
    x.fillText(ds, lp - 70, bl + 4); x.fillText('avg ' + av.toFixed(2) + '%', lp - 6, bl + 4)
  }
}

export function drawMedian(cv: HTMLCanvasElement, ml: MedianPoint[]) {
  if (!ml || !ml.length) return
  const dpr = window.devicePixelRatio || 1
  const W = 640, H = 300
  cv.width = W * dpr; cv.height = H * dpr
  cv.style.width = '100%'; cv.style.height = 'auto'; cv.style.maxWidth = W + 'px'
  const x = cv.getContext('2d')!; x.scale(dpr, dpr)
  const tP = 20, bP = 40, lP = 45, rP = 60
  const pW = W - lP - rP, pH_ = H - tP - bP
  const allQ1 = ml.map((d) => d.q1), allQ3 = ml.map((d) => d.q3)
  const yMin = Math.min(...allQ1) - 0.1, yMax = Math.max(...allQ3) + 0.1
  const N = ml.length
  const xP = (i: number) => lP + (N === 1 ? 0 : (i / (N - 1)) * pW)
  const yP = (v: number) => tP + pH_ - (v - yMin) / (yMax - yMin || 1) * pH_
  x.strokeStyle = 'rgba(0,0,0,.07)'; x.lineWidth = 0.5; x.setLineDash([2, 4])
  const st = (yMax - yMin) > 1 ? 0.5 : 0.2
  for (let v = Math.ceil(yMin / st) * st; v <= yMax + 1e-9; v += st) { const py = yP(v); x.beginPath(); x.moveTo(lP, py); x.lineTo(W - rP, py); x.stroke() }
  x.setLineDash([])
  x.font = '11px DM Sans,sans-serif'; x.fillStyle = 'rgba(90,95,102,0.9)'; x.textAlign = 'right'
  for (let v = Math.ceil(yMin / st) * st; v <= yMax + 1e-9; v += st) x.fillText(v.toFixed(1) + '%', lP - 6, yP(v) + 3)
  const months = [0]
  for (let i = 1; i < N; i++) if (ml[i].d.slice(5, 7) !== ml[i - 1].d.slice(5, 7)) months.push(i)
  const skip = months.length > 5 ? 2 : 1
  x.textAlign = 'center'; x.fillStyle = 'rgba(26,28,31,0.7)'; x.font = '600 11px DM Sans,sans-serif'
  months.forEach((idx, j) => { if (j % skip === 0 || j === months.length - 1) { const yr = ml[idx].d.slice(2, 4); const mo = parseInt(ml[idx].d.slice(5, 7)); x.fillText("'" + yr + '.' + mo, xP(idx), H - bP + 20) } })
  x.beginPath()
  for (let i = 0; i < N; i++) { const px = xP(i); if (i === 0) x.moveTo(px, yP(ml[i].q3)); else x.lineTo(px, yP(ml[i].q3)) }
  for (let i = N - 1; i >= 0; i--) x.lineTo(xP(i), yP(ml[i].q1))
  x.closePath(); x.fillStyle = 'rgba(26,122,76,0.12)'; x.fill()
  x.beginPath()
  for (let i = 0; i < N; i++) { const px = xP(i); if (i === 0) x.moveTo(px, yP(ml[i].q3)); else x.lineTo(px, yP(ml[i].q3)) }
  x.strokeStyle = 'rgba(26,122,76,0.3)'; x.lineWidth = 0.8; x.stroke()
  x.beginPath()
  for (let i = 0; i < N; i++) { const px = xP(i); if (i === 0) x.moveTo(px, yP(ml[i].q1)); else x.lineTo(px, yP(ml[i].q1)) }
  x.strokeStyle = 'rgba(26,122,76,0.3)'; x.lineWidth = 0.8; x.stroke()
  x.beginPath()
  for (let i = 0; i < N; i++) { const px = xP(i); if (i === 0) x.moveTo(px, yP(ml[i].med)); else x.lineTo(px, yP(ml[i].med)) }
  x.strokeStyle = '#1a7a4c'; x.lineWidth = 2; x.stroke()
  const last = ml[N - 1]
  x.beginPath(); x.arc(xP(N - 1), yP(last.med), 4, 0, Math.PI * 2); x.fillStyle = '#1a7a4c'; x.fill(); x.strokeStyle = 'rgba(255,255,255,0.6)'; x.lineWidth = 1.5; x.stroke()
  x.fillStyle = '#1a7a4c'; x.font = 'bold 10px DM Sans,sans-serif'; x.textAlign = 'left'; x.fillText(last.med.toFixed(2) + '%', xP(N - 1) + 8, yP(last.med) + 3)
  x.fillStyle = 'rgba(90,95,102,0.9)'; x.font = '9px DM Sans,sans-serif'; x.textAlign = 'left'; x.fillText('Q1-Q3 band', lP + 4, tP + 10)
  x.fillStyle = '#1a7a4c'; x.fillText('Median', lP + 70, tP + 10)
}
