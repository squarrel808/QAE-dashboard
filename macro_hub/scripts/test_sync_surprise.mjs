import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { webReport, syncSurprise } from './sync_surprise.mjs'

const html='<a href="../index.html" id="home-link">데일리 시황</a><script id="payload" type="application/json">{"source":"snowflake","economic":[1],"inflation":[1]}</script>'
test('web navigation replaces local link; transformation is idempotent',()=>{
  const web=webReport(html)
  assert.ok(web.includes('href="/consensus" target="_top"'))
  assert.equal(webReport(web),web)
})
test('missing or partial index data fails validation',()=>{
  assert.throws(()=>webReport('<html>empty</html>'))
  assert.throws(()=>webReport(html.replace('"source":"snowflake",','')))
  assert.throws(()=>webReport(html.replace('"inflation":[1]','"inflation":[]')))
})
test('source sync and cloud-only fallback retain the same public snapshot',()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'qae-surprise-test-'))
  const source=path.join(folder,'source.html'), target=path.join(folder,'public.html')
  try {
    fs.writeFileSync(source,html)
    syncSurprise(source,target)
    const expected=fs.readFileSync(target,'utf8')
    syncSurprise(path.join(folder,'absent.html'),target)
    assert.equal(fs.readFileSync(target,'utf8'),expected)
    fs.writeFileSync(source,'broken')
    assert.throws(()=>syncSurprise(source,target))
    assert.equal(fs.readFileSync(target,'utf8'),expected)
  } finally {
    for(const file of [source,target])if(fs.existsSync(file))fs.unlinkSync(file)
    fs.rmdirSync(folder)
  }
})
