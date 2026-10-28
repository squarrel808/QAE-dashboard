// Local updates publish a new snapshot; Vercel validates the committed one.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const source=path.resolve(root,'../PCA_BlackRock_Only')
const destination=path.join(root,'public/embeds/pca-iii')
const files=['index.html','indices.csv','inputs.csv','selection_audit.csv','classification_signs.html','classification_signs.csv','component_signs.csv','weights.csv','blackrock_coverage.csv','blackrock_coverage.html']
function validate(html){
  const match=html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)
  if(!match)throw new Error('PCA III payload missing')
  const d=JSON.parse(match[1])
  if(d.universe!=='blackrock_reference_only'||Object.keys(d.countries).sort().join(',')!=='AU,CA,DE,JP,UK,US')throw new Error('PCA III universe mismatch')
  if(d.weight_policy!=='january_1_ttm_lagged_frozen_half_exports_v3')throw new Error('PCA III weight policy mismatch')
  if(new Set(d.indicators.map(r=>r.country+'|'+r.pk)).size!==d.indicators.length)throw new Error('Duplicate inputs')
  for(const c of Object.values(d.countries)){
    if(!c.annual_weights?.length||!c.active_axes?.length)throw new Error('Missing weights or active sectors')
    for(const v of Object.values(c.versions))if(!v.latest||v.negative_loadings!==0)throw new Error('Model validation failed')
  }
  if(!html.includes('id="momentumChart"'))throw new Error('Paired Level/Momentum view missing')
}
if(fs.existsSync(path.join(source,'index.html'))){
  validate(fs.readFileSync(path.join(source,'index.html'),'utf8'))
  fs.mkdirSync(destination,{recursive:true})
  for(const file of files)fs.copyFileSync(path.join(source,file),path.join(destination,file))
  console.log('[PCA III] BlackRock-only dashboard synchronized')
}else{
  validate(fs.readFileSync(path.join(destination,'index.html'),'utf8'))
  for(const file of files)if(!fs.existsSync(path.join(destination,file)))throw new Error('PCA III snapshot missing: '+file)
  console.log('[PCA III] Committed snapshot validated')
}
