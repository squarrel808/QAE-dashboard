'use strict';
const PERSONAL_KEY='qae.personalViews.v1';
const PERSONAL_REGIONS=[{code:'GLOBAL',label:'글로벌'},{code:'US',label:'미국'},{code:'EA',label:'유로존'},{code:'JP',label:'일본'},{code:'CN',label:'중국'},{code:'KR',label:'한국'},{code:'GB',label:'영국'},{code:'CA',label:'캐나다'},{code:'AU',label:'호주'},{code:'EM',label:'신흥국'}];
for(const item of PERSONAL_REGIONS)if(!DATA.countries.some(c=>c.code===item.code))DATA.countries.push(item);
const personalAllowed=new Set(DATA.countries.map(c=>c.code));
function validatePersonal(value){
  if(!value||![1,2].includes(value.schema_version)||!value.regions||typeof value.regions!=='object'||Array.isArray(value.regions))throw new Error('내 뷰 백업 형식을 확인하세요.');
  const result={schema_version:2,regions:{}};
  for(const [code,stored] of Object.entries(value.regions)){
    if(!personalAllowed.has(code))throw new Error('리전을 확인하세요.');
    const entries=value.schema_version===1?[stored]:stored;
    if(!Array.isArray(entries))throw new Error('내 뷰 목록 형식을 확인하세요.');
    result.regions[code]=entries.map(entry=>{
      if(!entry||typeof entry.text!=='string'||entry.text.length>30000||typeof entry.updatedAt!=='string'||!Number.isFinite(Date.parse(entry.updatedAt)))throw new Error('입력 내용의 형식이 올바르지 않습니다.');
      return {text:entry.text,updatedAt:entry.updatedAt};
    });
  }
  return result;
}
function readPersonal(){const raw=localStorage.getItem(PERSONAL_KEY);return raw?validatePersonal(JSON.parse(raw)):{schema_version:2,regions:{}};}
async function updatePersonal(update){
  const write=()=>{
    const next=readPersonal();
    update(next);
    localStorage.setItem(PERSONAL_KEY,JSON.stringify(next));
    personalState=next;
    personalError='';
  };
  if(navigator.locks)await navigator.locks.request(PERSONAL_KEY,write);
  else write();
}
const personalDrafts=new Map();
let personalState={schema_version:2,regions:{}},personalError='';
try{personalState=readPersonal();}catch(error){personalError='저장된 내 뷰를 읽지 못했습니다. '+error.message;}
function personalTime(value){return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(value))+' KST';}
function showPersonalPreview(){
  const entries=personalState.regions[country]||[];
  $('personalTime').textContent=entries.length?'저장된 내 뷰 · '+entries.length+'건':'아직 적용한 뷰가 없습니다.';
  $('personalPreview').innerHTML=entries.length?entries.map(entry=>`<article class="personal-saved"><strong>${esc(personalTime(entry.updatedAt))}</strong><div style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(entry.text)}</div></article>`).join(''):'아직 작성한 내 뷰가 없습니다.';
  $('personalSaveStatus').textContent=personalError||(personalDrafts.has(country)?'작성 중입니다. 입력·적용 버튼을 누르면 저장됩니다.':'입력·적용 버튼을 눌러 내 뷰를 저장하세요.');
  $('personalSaveStatus').classList.toggle('save-error',!!personalError);
}
function renderPersonal(){
  $('personalRegion').textContent=(DATA.countries.find(c=>c.code===country)?.label||country)+' · 내 뷰';
  $('personalText').value=personalDrafts.has(country)?personalDrafts.get(country):'';
  showPersonalPreview();
}
async function savePersonal(code,text){
  if(!personalAllowed.has(code)||typeof text!=='string'||!text.trim()||text.length>30000)throw new Error('추가할 내용을 입력하세요.');
  await updatePersonal(next=>{
    const entries=next.regions[code]||[];
    entries.push({text,updatedAt:new Date().toISOString()});
    next.regions[code]=entries;
  });
}
$('personalText').addEventListener('input',()=>{
  personalDrafts.set(country,$('personalText').value);
  showPersonalPreview();
});
$('personalApply').addEventListener('click',async()=>{
  const code=country,text=$('personalText').value;
  $('personalApply').disabled=true;
  try{
    await savePersonal(code,text);
    if(personalDrafts.get(code)===text)personalDrafts.delete(code);
    renderPersonal();
    $('personalSaveStatus').textContent='새 뷰를 목록 아래에 추가했습니다.';
  }catch(error){personalError='적용 실패: '+error.message;showPersonalPreview();}
  finally{$('personalApply').disabled=false;}
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
    await updatePersonal(next=>{
      for(const [code,entries] of Object.entries(incoming.regions)){
        const existing=next.regions[code]||[];
        const keys=new Set(existing.map(entry=>JSON.stringify([entry.updatedAt,entry.text])));
        for(const entry of entries){
          const key=JSON.stringify([entry.updatedAt,entry.text]);
          if(!keys.has(key)){existing.push(entry);keys.add(key);}
        }
        next.regions[code]=existing.sort((a,b)=>Date.parse(a.updatedAt)-Date.parse(b.updatedAt));
      }
    });
    renderPersonal();
    $('personalSaveStatus').textContent='백업의 뷰를 기존 목록에 합쳤습니다.';
  }catch(error){personalError='불러오기 실패: '+error.message;showPersonalPreview();}
  event.target.value='';
});
window.addEventListener('storage',event=>{if(event.key===PERSONAL_KEY){try{personalState=readPersonal();personalError='';renderPersonal();}catch(error){personalError=error.message;showPersonalPreview();}}});
