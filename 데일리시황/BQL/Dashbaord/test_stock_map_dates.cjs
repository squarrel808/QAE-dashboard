/* Run with node test_stock_map_dates.cjs. Exercises the shipped template functions. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const templatePath = process.argv[2] || path.join(__dirname, '유로존_dashboard', 'market_rotation_dashboard.template.html');
const html = fs.readFileSync(templatePath, 'utf8');
const helpers = html.match(/\/\/ STOCK_MAP_DATE_HELPERS_START[^\n]*\n([\s\S]*?)\/\/ STOCK_MAP_DATE_HELPERS_END/);
assert.ok(helpers, 'The template must contain the actual date helpers');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(helpers[1] + '\nthis.helpers={stockMapISODate,resolveStockMapRange,stockMapRangeReturn,stockMapRangeLimit};', sandbox);
const {stockMapISODate, resolveStockMapRange, stockMapRangeReturn, stockMapRangeLimit} = sandbox.helpers;
const dataset = {asOf:'2026-10-14', dates:['2026-10-02','2026-10-05','2026-10-06','2026-10-08','2026-10-09','2026-10-12','2026-10-13','2026-10-14']};
const prices = [100,102,103,105,104,108,110,112];
let passed = 0;
function test(name, fn) { fn(); passed++; console.log(`PASS ${name}`); }

test('ISO calendar validation rejects impossible dates and accepts leap days', () => {
  assert.equal(stockMapISODate('2024-02-29'), true);
  for(const value of ['2026-02-29','2026-04-31','2026-2-01','2026-13-01','','not-a-date',null]) assert.equal(stockMapISODate(value), false);
});
test('an exact session range calculates its endpoint price return', () => {
  const range = resolveStockMapRange(dataset,'2026-10-05','2026-10-13');
  assert.equal(range.ok,true);
  assert.equal(range.startIndex,1);
  assert.equal(range.endIndex,6);
  assert.ok(Math.abs(stockMapRangeReturn(prices,range)-(110/102-1))<1e-12);
});
test('both weekend endpoints resolve backwards independently', () => {
  const range = resolveStockMapRange(dataset,'2026-10-03','2026-10-11');
  assert.equal(range.requestedStart,'2026-10-03');
  assert.equal(range.requestedEnd,'2026-10-11');
  assert.equal(range.startDate,'2026-10-02');
  assert.equal(range.endDate,'2026-10-09');
  assert.ok(Math.abs(stockMapRangeReturn(prices,range)-.04)<1e-12);
});
test('a missing market session resolves backwards without looking ahead', () => {
  const range = resolveStockMapRange(dataset,'2026-10-07','2026-10-08');
  assert.equal(range.startDate,'2026-10-06');
  assert.equal(range.endDate,'2026-10-08');
});
test('equal dates, including two dates on the same weekend, return zero', () => {
  for(const [start,end] of [['2026-10-06','2026-10-06'],['2026-10-10','2026-10-11']]) {
    const range = resolveStockMapRange(dataset,start,end);
    assert.equal(range.ok,true);
    assert.equal(stockMapRangeReturn(prices,range),0);
  }
});
test('empty and malformed dates are rejected with a user message', () => {
  for(const [start,end] of [['','2026-10-13'],['2026-10-02',''],['2026-10-00','2026-10-13']]) {
    const range = resolveStockMapRange(dataset,start,end);
    assert.equal(range.ok,false);
    assert.ok(range.error.length>0);
  }
});
test('reversed dates are rejected before resolving market sessions', () => {
  const range = resolveStockMapRange(dataset,'2026-10-11','2026-10-10');
  assert.equal(range.ok,false);
  assert.match(range.error,/시작일/);
});
test('out-of-range endpoints are rejected rather than silently clamped', () => {
  for(const [start,end] of [['2026-10-01','2026-10-13'],['2026-10-02','2026-10-15']]) {
    const range = resolveStockMapRange(dataset,start,end);
    assert.equal(range.ok,false);
    assert.match(range.error,/2026-10-02 ~ 2026-10-14/);
  }
});
test('a new index reuses requested dates and explicitly rejects an unavailable history', () => {
  const original = resolveStockMapRange(dataset,'2026-10-03','2026-10-11');
  const shorter = {asOf:dataset.asOf,dates:dataset.dates.slice(2)};
  const result = resolveStockMapRange(shorter,original.requestedStart,original.requestedEnd);
  assert.equal(result.ok,false);
  assert.match(result.error,/2026-10-06/);
});
test('missing endpoint prices stay unavailable; intermediate missing prices do not alter endpoints', () => {
  const range = resolveStockMapRange(dataset,'2026-10-02','2026-10-14');
  for(const missing of [null,undefined,0,-1,NaN,Infinity,'100']) {
    const atStart = prices.slice(); atStart[0]=missing;
    const atEnd = prices.slice(); atEnd[7]=missing;
    assert.equal(stockMapRangeReturn(atStart,range),null);
    assert.equal(stockMapRangeReturn(atEnd,range),null);
  }
  const intermediate = prices.slice(); intermediate[3]=null;
  assert.ok(Math.abs(stockMapRangeReturn(intermediate,range)-.12)<1e-12);
  assert.equal(stockMapRangeReturn([],range),null);
  assert.equal(stockMapRangeReturn(null,range),null);
  assert.equal(stockMapRangeReturn(prices,{ok:false}),null);
});
test('even a same-day return is unavailable when that stock has no price', () => {
  const range = resolveStockMapRange(dataset,'2026-10-08','2026-10-08');
  const missing=prices.slice(); missing[3]=null;
  assert.equal(stockMapRangeReturn(missing,range),null);
});
test('invalid, duplicate, unsorted or future market sessions are rejected', () => {
  for(const dates of [[],['2026-10-02','2026-10-02'],['2026-10-05','2026-10-02'],['2026-02-30'],['2026-10-15']]) {
    assert.equal(resolveStockMapRange({asOf:dataset.asOf,dates},'2026-10-02','2026-10-13').ok,false);
  }
});
test('custom colors scale with the number of market sessions', () => {
  for(const [sessions,limit] of [[0,.03],[1,.03],[2,.06],[5,.06],[6,.10],[23,.10],[24,.20],[66,.20],[67,.30]]) {
    assert.equal(stockMapRangeLimit({startIndex:10,endIndex:10+sessions}),limit);
  }
});
test('preset inputs, custom inputs, and bounds use the actual template synchronization', () => {
  const functionSource=html.match(/    function syncStockMapDates\(dataset,values=false\) \{([\s\S]*?)\n    function syncStockMapPeriodButtons/)[0].replace(/\n    function syncStockMapPeriodButtons$/,'');
  const fields={};
  const root={querySelector:selector=>(fields[selector]||=( {value:''} ))};
  const context={root,mapPeriod:'ytd',mapRequestedRange:null};
  vm.createContext(context);
  vm.runInContext(functionSource+'\nthis.sync=syncStockMapDates;',context);
  const data={...dataset,periods:{'ytd':{startDate:null,endDate:dataset.asOf},'1d':{startDate:'2026-10-13',endDate:dataset.asOf}}};
  context.sync(data,true);
  assert.equal(fields['#mrd-map-start'].value,'');
  assert.equal(fields['#mrd-map-end'].value,dataset.asOf);
  assert.equal(fields['#mrd-map-start'].min,dataset.dates[0]);
  assert.equal(fields['#mrd-map-end'].max,dataset.asOf);
  context.mapPeriod='1d'; context.sync(data,true);
  assert.equal(fields['#mrd-map-start'].value,'2026-10-13');
  context.mapPeriod='custom'; context.mapRequestedRange={start:'2026-10-03',end:'2026-10-11'};
  context.sync(data,true);
  assert.equal(fields['#mrd-map-start'].value,'2026-10-03');
  assert.equal(fields['#mrd-map-end'].value,'2026-10-11');
  fields['#mrd-map-start'].value='2026-10-05'; context.sync(data,false);
  assert.equal(fields['#mrd-map-start'].value,'2026-10-05','Rendering must not erase an unapplied date edit');
});
test('custom dates apply through click and Enter without sandbox-blocked form submission', () => {
  const source=html.match(/    function applyStockMapDates\(\)\{[\s\S]*?(?=    root.querySelectorAll\('\[data-heatmap-period\]')/)[0];
  const fields={
    '#mrd-map-index':{value:'SPX'},
    '#mrd-map-start':{value:'2026-10-03'},
    '#mrd-map-end':{value:'2026-10-13'}
  };
  const listeners={};
  const root={querySelector:selector=>fields[selector]||{addEventListener:(event,fn)=>listeners[`${selector}:${event}`]=fn}};
  let renders=0, error='';
  const context={root,DATA:{stockMap:{SPX:dataset}},resolveStockMapRange,
    mapPeriod:'1d',mapRequestedRange:null,syncStockMapPeriodButtons:()=>{},
    setStockMapDateError:value=>error=value,renderStockMap:()=>renders++};
  vm.createContext(context); vm.runInContext(source,context);
  listeners['#mrd-map-apply:click']();
  assert.equal(renders,1); assert.equal(context.mapPeriod,'custom');
  assert.equal(context.mapRequestedRange.start,'2026-10-03');
  fields['#mrd-map-start'].value='2026-10-14';
  listeners['#mrd-map-apply:click']();
  assert.equal(renders,1); assert.match(error,/시작일/);
  fields['#mrd-map-start'].value='2026-10-08';
  let prevented=false;
  listeners['#mrd-map-dates:keydown']({key:'Enter',target:{matches:()=>true},preventDefault:()=>prevented=true});
  assert.equal(prevented,true); assert.equal(renders,2); assert.equal(error,'');
  assert.match(html,/<button id="mrd-map-apply" type="button"/);
  assert.doesNotMatch(html,/<form[^>]*id="mrd-map-dates"/);
});
test('the full dashboard script parses and date controls have accessible labels', () => {
  const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(match=>match[1]);
  new vm.Script(scripts.find(script=>script.includes('const DATA =')).replace('__DASHBOARD_DATA__','{}'));
  assert.match(html,/<label for="mrd-map-start">시작일/);
  assert.match(html,/<label for="mrd-map-end">종료일/);
  assert.match(html,/id="mrd-map-date-error"[^>]*role="alert"/);
  assert.match(html,/id="mrd-map-dates"[^>]*role="group"/);
  for(const preset of ['1d','1w','1m','mtd','3m','6m','ytd']) assert.match(html,new RegExp(`data-map-period="${preset}"`));
});
console.log(`${passed} Stock Map date checks passed.`);
