// Vercel needs only the validated, self-contained report, never local credentials.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export function webReport(html) {
  const match = html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)
  if (!match) throw new Error('Surprise report has no validated payload')
  const data = JSON.parse(match[1])
  if (data.source !== 'snowflake') throw new Error('Surprise must use Snowflake; legacy PostgreSQL snapshots are rejected')
  if (!data.economic?.length || !data.inflation?.length) throw new Error('Both Surprise indices are required')
  return html
    .replace('<a href="../index.html" id="home-link">데일리 시황</a>', '<a href="/consensus" target="_top" id="home-link">Consensus</a>')
    .replace(' API 갱신 실행: 이 폴더의 update_surprise.cmd.', '')
}

export function syncSurprise(source = path.resolve(root, '../데일리시황/표_업데이트/surprise index/index.html'), destination = path.join(root, 'public/embeds/surprise.html')) {
  if (!fs.existsSync(source)) {
    // Vercel may receive macro_hub alone; retain the committed public snapshot.
    if (!fs.existsSync(destination)) throw new Error('Surprise source and public snapshot are both missing')
    webReport(fs.readFileSync(destination, 'utf8'))
    console.log('[surprise] Validated committed public snapshot')
    return
  }
  const report = webReport(fs.readFileSync(source, 'utf8'))
  fs.mkdirSync(path.dirname(destination), { recursive: true })
  if (!fs.existsSync(destination) || fs.readFileSync(destination, 'utf8') !== report) {
    const temporary = destination + '.tmp'
    fs.writeFileSync(temporary, report, 'utf8')
    fs.renameSync(temporary, destination)
  }
  console.log('[surprise] Ready: public/embeds/surprise.html')
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) syncSurprise()
