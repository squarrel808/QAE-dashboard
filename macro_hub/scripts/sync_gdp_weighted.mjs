// Copy only the independent reviewed PCA screen and user-facing tables.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = path.resolve(root, '../PCA_Four_Axis')
const destination = path.join(root, 'public/embeds/gdp-weighted')
const files = ['index.html', 'indices.csv', 'inputs.csv', 'selection_audit.csv', 'classification_signs.html', 'classification_signs.csv', 'component_signs.csv', 'weights.csv', 'blackrock_coverage.csv', 'blackrock_coverage.html']

function validate(html) {
  const match = html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)
  if (!match) throw new Error('GDP-weighted report payload is missing')
  const data = JSON.parse(match[1])
  if (!data.method?.includes('Four direct block PCAs') || Object.keys(data.countries || {}).length !== 7) throw new Error('GDP-weighted model validation failed')
  if (data.weight_policy !== 'january_1_ttm_lagged_frozen_half_exports_v3') throw new Error('January weight policy is missing')
  for (const country of Object.values(data.countries)) {
    if (!country.annual_weights?.length || !country.weight_year) throw new Error('Annual weight snapshots are missing')
    for (const version of Object.values(country.versions)) {
      if (!version.latest || version.negative_loadings !== 0) throw new Error('Missing model or economic direction failure')
    }
  }
}

if (fs.existsSync(path.join(source, 'index.html'))) {
  validate(fs.readFileSync(path.join(source, 'index.html'), 'utf8'))
  fs.mkdirSync(destination, { recursive: true })
  for (const name of files) fs.copyFileSync(path.join(source, name), path.join(destination, name))
  console.log('[GDP PCA] Independent model snapshot synchronized')
} else {
  validate(fs.readFileSync(path.join(destination, 'index.html'), 'utf8'))
  for (const name of files) if (!fs.existsSync(path.join(destination, name))) throw new Error(`Missing GDP PCA table: ${name}`)
  console.log('[GDP PCA] Validated committed snapshot')
}
