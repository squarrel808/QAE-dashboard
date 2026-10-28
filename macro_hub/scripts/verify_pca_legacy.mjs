// Frozen archive: verify only. Daily refreshes must not overwrite these files.
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/embeds/pca-legacy')
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'))
if (manifest.automatic_refresh !== false || !manifest.source_commit.startsWith('bb4f6ac7')) throw new Error('Legacy PCA archive identity changed')
for (const [file, record] of Object.entries(manifest.files)) {
  const content = fs.readFileSync(path.join(root, file), 'utf8').replaceAll('\r\n', '\n')
  const hash = crypto.createHash('sha256').update(content).digest('hex')
  if (hash !== record.sha256_lf_normalized) throw new Error(`Legacy PCA archive changed: ${file}`)
}
console.log('[PCA archive] Previous release snapshots verified; no files changed')
