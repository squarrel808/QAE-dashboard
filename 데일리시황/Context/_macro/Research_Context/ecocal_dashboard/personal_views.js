'use strict';
const PERSONAL_KEY='qae.personalViews.v1';
const PERSONAL_REGIONS=[{code:'GLOBAL',label:'글로벌'},{code:'US',label:'미국'},{code:'EA',label:'유로존'},{code:'JP',label:'일본'},{code:'CN',label:'중국'},{code:'KR',label:'한국'},{code:'GB',label:'영국'},{code:'CA',label:'캐나다'},{code:'AU',label:'호주'},{code:'EM',label:'신흥국'}];
for(const item of PERSONAL_REGIONS)if(!DATA.countries.some(c=>c.code===item.code))DATA.countries.push(item);
const personalAllowed=new Set(DATA.countries.map(c=>c.code));
function validatePersonal(value){
  if(!value||value.schema_version!==1||!value.regions||typeof value.regions!=='object'||Array.isArray(value.regions))throw new Error('내 뷰 백업 형식을 확인하세요.');
  const result={schema_version:1,regions:{}};
  for(const [code,entry]of Object.entries(value.regions)){
    if(!personalAllowed.has(code)||!entry||typeof entry.text!=='string'||entry.text.length>30000||typeof entry.updatedAt!=='string'||!Number.isFinite(Date.parse(entry.updatedAt)))throw new Error('리전 또는 입력 내용의 형식이 올바르지 않습니다.');
    result.regions[code]={text:entry.text,updatedAt:entry.updatedAt};
  }
  return result;
}
function readPersonal(){const raw=localStorage.getItem(PERSONAL_KEY);return raw?validatePersonal(JSON.parse(raw)):{schema_version:1,regions:{}};}
const personalDrafts=new Map();
let personalState={schema_version:1,regions:{}},personalError='';
try{personalState=readPersonal();}catch(error){personalError='저장된 내 뷰를 읽지 못했습니다. '+error.message;}
function personalTime(value){return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(value))+' KST';}
function showPersonalPreview(){
  const entry=personalState.regions[country];
  $('personalPreview').textContent=entry?.text||'아직 작성한 내 뷰가 없습니다.';
  $('personalTime').textContent=entry?'적용일시 · '+personalTime(entry.updatedAt):'아직 적용한 뷰가 없습니다.';
  $('personalSaveStatus').textContent=personalError||(personalDrafts.has(country)?'작성 중입니다. 입력·적용 버튼을 누르면 저장됩니다.':'입력·적용 버튼을 눌러 내 뷰를 저장하세요.');
  $('personalSaveStatus').classList.toggle('save-error',!!personalError);
}
function renderPersonal(){
  $('personalRegion').textContent=(DATA.countries.find(c=>c.code===country)?.label||country)+' · 내 뷰';
  $('personalText').value=personalDrafts.has(country)?personalDrafts.get(country):(personalState.regions[country]?.text||'');
  showPersonalPreview();
}
function savePersonal(code,text){
  if(!personalAllowed.has(code)||typeof text!=='string'||text.length>30000)throw new Error('입력 내용을 확인하세요.');
  const next=readPersonal();
  next.regions[code]={text,updatedAt:new Date().toISOString()};
  localStorage.setItem(PERSONAL_KEY,JSON.stringify(next));
  personalState=next;personalError='';
  return next.regions[code];
}
$('personalText').addEventListener('input',()=>{
  personalDrafts.set(country,$('personalText').value);
  showPersonalPreview();
});
$('personalApply').addEventListener('click',()=>{
  try{
    savePersonal(country,$('personalText').value);
    personalDrafts.delete(country);
    showPersonalPreview();
    $('personalSaveStatus').textContent='적용되었습니다. 아래 뷰와 적용일시가 저장되었습니다.';
  }catch(error){personalError='적용 실패: '+error.message;showPersonalPreview();}
});
$('personalExport').addEventListener('click',()=>{
  try{
    const state=readPersonal();
    const url=URL.createObjectURL(new Blob([JSON.stringify(state,null,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download='QAE_내뷰_'+new Date().toISOString().slice(0,10)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){personalError='백업 실패: '+error.message;showPersonalPreview();}
});
$('personalImport').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;
  try{
    if(file.size>2000000)throw new Error('백업 파일이 너무 큽니다.');
    const incoming=validatePersonal(JSON.parse(await file.text()));
    const next=readPersonal();
    for(const[code,entry]of Object.entries(incoming.regions)){
      const existing=next.regions[code];
      if(!existing||Date.parse(entry.updatedAt)>Date.parse(existing.updatedAt))next.regions[code]=entry;
    }
    localStorage.setItem(PERSONAL_KEY,JSON.stringify(next));personalState=next;personalError='';renderPersonal();
    $('personalSaveStatus').textContent='백업을 불러왔습니다. 리전별 최신 수정 내용을 유지합니다.';
  }catch(error){personalError='불러오기 실패: '+error.message;showPersonalPreview();}
  event.target.value='';
});
window.addEventListener('storage',event=>{if(event.key===PERSONAL_KEY){try{personalState=readPersonal();personalError='';renderPersonal();}catch(error){personalError=error.message;showPersonalPreview();}}});
