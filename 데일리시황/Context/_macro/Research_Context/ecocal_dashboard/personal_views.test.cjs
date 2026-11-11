const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const script = fs.readFileSync(__dirname + '/personal_views.js', 'utf8');
function browser(initial) {
  const store = new Map(initial ? [['qae.personalViews.v1', JSON.stringify(initial)]] : []);
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {value:'', textContent:'', innerHTML:'', classList:{toggle(){}}, handlers:{}, addEventListener(name, fn){this.handlers[name]=fn;}});
    return elements.get(id);
  };
  let pending = Promise.resolve();
  const context = vm.createContext({
    DATA:{countries:[{code:'US',label:'미국'},{code:'JP',label:'일본'}]}, country:'US', $:element,
    esc:value=>String(value).replace(/</g,'&lt;'), navigator:{locks:{request(key, fn){const run=pending.then(fn);pending=run.catch(()=>{});return run;}}},
    localStorage:{getItem:key=>store.get(key),setItem:(key,value)=>store.set(key,value)}, window:{addEventListener(){}}, Intl, Date, Set, Map,
  });
  vm.runInContext(script,context);
  return {context, element, store, state:()=>JSON.parse(store.get('qae.personalViews.v1')), run:code=>vm.runInContext(code,context)};
}
test('existing single view survives two additions, reload, and region switching',async()=>{
  const b=browser({schema_version:1,regions:{US:{text:'기존 견해',updatedAt:'2026-11-10T01:00:00Z'}}});
  for(const text of ['첫 추가','둘째 추가']){
    b.element('personalText').value=text;
    b.element('personalText').handlers.input();
    await b.element('personalApply').handlers.click();
    assert.equal(b.element('personalText').value,'');
  }
  assert.deepEqual(b.state().regions.US.map(e=>e.text),['기존 견해','첫 추가','둘째 추가']);
  b.run("country='JP';renderPersonal()");
  assert.equal(b.element('personalPreview').innerHTML,'아직 작성한 내 뷰가 없습니다.');
  const reload=browser(b.state());reload.run('renderPersonal()');
  assert.match(reload.element('personalPreview').innerHTML,/기존 견해.*첫 추가.*둘째 추가/s);
});
test('old and new backups merge without deleting entries or duplicating repeated imports',async()=>{
  const b=browser();await b.run("savePersonal('US','현재')");
  const old={schema_version:1,regions:{US:{text:'과거',updatedAt:'2026-11-01T00:00:00Z'}}};
  const importData=async data=>b.element('personalImport').handlers.change({target:{files:[{size:100,text:async()=>JSON.stringify(data)}],value:'backup'}});
  await importData(old);await importData(old);await importData(b.state());
  assert.deepEqual(b.state().regions.US.map(e=>e.text),['과거','현재']);
});
test('concurrent additions persist, empty input and storage failure preserve saved data and draft',async()=>{
  const b=browser();
  await Promise.all([b.run("savePersonal('US','A')"),b.run("savePersonal('US','B')")]);
  assert.equal(b.state().regions.US.length,2);
  await assert.rejects(b.run("savePersonal('US','   ')"));
  const before=JSON.stringify(b.state());
  b.context.localStorage.setItem=()=>{throw Error('QuotaExceeded');};
  b.element('personalText').value='실패 초안';b.element('personalText').handlers.input();
  await b.element('personalApply').handlers.click();
  assert.equal(JSON.stringify(b.state()),before);
  assert.equal(b.element('personalText').value,'실패 초안');
  assert.match(b.element('personalSaveStatus').textContent,/적용 실패/);
});
test('saved markup is escaped',async()=>{
  const b=browser();await b.run("savePersonal('US','<img onerror=alert(1)>')");b.run('renderPersonal()');
  assert.ok(!b.element('personalPreview').innerHTML.includes('<img'));
});
