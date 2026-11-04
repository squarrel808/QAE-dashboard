import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

const hub=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source=path.resolve(hub,'../PCA/Indicator_Heatmap')
const target=path.join(hub,'public/embeds/country-indicators/index.html')
if (!process.env.VERCEL && fs.existsSync(path.resolve(source,'../PCA_Four_Axis/dashboard_data.json'))) {
  execFileSync('python',['-X','utf8',path.join(source,'build.py')],{stdio:'inherit'})
}
if (fs.existsSync(path.join(source,'index.html'))) {
  fs.mkdirSync(path.dirname(target),{recursive:true})
  fs.copyFileSync(path.join(source,'index.html'),target)
}
const html=fs.readFileSync(target,'utf8')
const match=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)
if (!match) throw new Error('Indicator payload missing')
const data=JSON.parse(match[1])
if(Object.keys(data.countries).length!==7 || data.indicators.length!==288 || !html.includes('standardize36')) throw new Error('Indicator snapshot invalid')
console.log('[Country indicators] Snapshot verified')
