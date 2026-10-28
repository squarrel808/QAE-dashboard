'use client'
import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import RawDashboard from './RawDashboard'

type Obs = {date:string;weight:number|null;yoy:number|null;mom:number|null;yoy_contribution:number|null;mom_contribution:number|null;yoy_weight:number|null;mom_weight:number|null}
type Group = {name:string;index:string;weight:string;descriptor:string;observations:Obs[]}
type Core = {name:string;ticker:string;descriptor:string;frequency:string;observations:{date:string;yoy:number|null;momentum:number|null}[]}
type Data = {generated:string;method:string;core:Core[];countries:Record<string,{groups:Group[]}>}
const colors=['#236a8b','#b45845','#ddab58','#719a84','#7d7aa8','#b87d9f','#84adb6','#a29368','#615e75','#b4bf73','#bd8159','#747d86']
const names:Record<string,string>={AustraliaQuarterly:'호주 (분기)',US:'미국','U.S.':'미국',Japan:'일본',UK:'영국',Germany:'독일',Australia:'호주',Canada:'캐나다',France:'프랑스',Spain:'스페인',Sweden:'스웨덴','New Zealand':'뉴질랜드','EA 11-21':'유로존',Austria:'오스트리아',Belgium:'벨기에',Denmark:'덴마크',Italy:'이탈리아',Luxembourg:'룩셈부르크',Netherlands:'네덜란드',Norway:'노르웨이',Switzerland:'스위스',Greece:'그리스',Iceland:'아이슬란드',Ireland:'아일랜드',Malta:'몰타',Portugal:'포르투갈',Cyprus:'키프로스','EU 27':'EU 27'}
const fmt=(v:number|null|undefined)=>v==null?'—':v.toFixed(2)
const btn=(on:boolean)=>`rounded-lg border px-4 py-2 text-sm ${on?'bg-[#173f4f] text-white':'bg-white text-[#173f4f] hover:bg-[#edf3f1]'}`
const select='border rounded-lg p-2 bg-white text-sm'
const coreOrder=['U.S.','UK','EA 11-21','France','Germany','Canada','Japan','Australia']
function heatColor(value:number|null|undefined) {
 if(value==null)return {background:'#eef1f0',color:'#657575'}
 const delta=value-2
 const strength=Math.min(Math.abs(delta)/2,1)
 const target=delta<0?[35,104,165]:[184,40,55]
 const rgb=target.map(channel=>Math.round(250+(channel-250)*strength))
 return {background:`rgb(${rgb.join(',')})`,color:strength>.7?'#ffffff':'#203640'}
}

function Heatmap({core,metric,months}:{core:Core[];metric:'yoy'|'momentum';months:number}) {
 const displayed=coreOrder.flatMap(name=>core.filter(c=>c.name===name))
 const dates=[...new Set(displayed.flatMap(c=>c.observations.map(o=>o.date)))].sort().slice(-months)
 return <div className="overflow-x-auto rounded-xl border border-[var(--line)] bg-white p-4 mb-5"><h3 className="font-semibold mb-2">Core CPI · {metric==='yoy'?'YoY':'3M/3M 연율'} (%)</h3><div className="flex flex-wrap items-center gap-2 text-base mb-4 text-[#52666b]"><span>색상 기준</span>{[0,1,2,3,4].map(v=><span key={v} style={heatColor(v)} className="px-3 py-1 rounded">{v===0?'≤0%':v===4?'≥4%':`${v}%`}</span>)}<span>2% 중립 · 국가별 공식 목표가 아닌 공통 비교 기준 · 회색은 자료 없음</span></div><table className="text-base border-separate border-spacing-[3px] w-full"><thead><tr><th className="sticky left-0 bg-white text-left min-w-28">국가 / 지역</th>{dates.map(d=><th key={d} className="font-medium min-w-[76px] py-3">{d.slice(2)}</th>)}</tr></thead><tbody>{displayed.map(c=><tr key={c.ticker}><th title={`${c.descriptor}\n${c.ticker}`} className="sticky left-0 bg-white text-left font-medium whitespace-nowrap pr-3">{names[c.name]||c.name}{c.frequency==='Q'?' · 분기':''}{c.name==='Australia'?' · 절사평균':''}</th>{dates.map(d=>{
  const v=c.observations.find(o=>o.date===d)?.[metric]
  return <td key={d} title={`${names[c.name]||c.name} · ${d} · ${fmt(v)}%\n${c.descriptor}`} style={heatColor(v)} className="text-center px-3 py-3 font-semibold tabular-nums">{fmt(v)}</td>
 })}</tr>)}</tbody></table></div>
}

export default function CpiAnalysis(){
 const [data,setData]=useState<Data|null>(null),[error,setError]=useState(false)
 const [tab,setTab]=useState('distribution'),[country,setCountry]=useState('US')
 const [metric,setMetric]=useState<'yoy'|'mom'>('yoy'),[months,setMonths]=useState(24),[heatMonths,setHeatMonths]=useState(12),[selected,setSelected]=useState('')
 useEffect(()=>{fetch('/data/cpi_analysis.json').then(r=>{if(!r.ok)throw Error();return r.json()}).then(setData).catch(()=>setError(true))},[])
 const quarterly=country==='AustraliaQuarterly'
 const shortRate=quarterly?'QoQ':'MoM'
 const groups=data?.countries[country]?.groups||[]
 const dates=[...new Set(groups.flatMap(g=>g.observations.map(o=>o.date)))].sort()
 const end=selected||dates.at(-1)||''
 const chart=dates.filter(d=>d<=end).slice(-months).map(date=>{
  const row:Record<string,string|number|null>={date}
  groups.forEach((g,i)=>{row['g'+i]=g.observations.find(o=>o.date===date)?.[`${metric}_contribution`]??null});return row
 })
 const latest=groups.map(g=>({g,o:g.observations.find(o=>o.date===end)}))
 const coverage=latest.reduce((s,{o})=>s+(o?.[`${metric}_contribution`]!=null?(o[`${metric}_weight`]??0):0),0)
 const sum=latest.reduce((s,{o})=>s+(o?.[`${metric}_contribution`]??0),0)
 return <div>
  <div className="flex flex-wrap justify-between gap-3 mb-4"><div><h1 className="text-2xl serif">CPI Monitor</h1><p className="text-sm text-[var(--muted)] mt-1">국가별 기조물가와 항목별 기여도 · Haver Analytics</p></div><label className="text-sm">히트맵 기간 <select aria-label="히트맵 기간" className={select} value={heatMonths} onChange={e=>setHeatMonths(+e.target.value)}>{[6,12,24,36,60].map(n=><option key={n} value={n}>{n}개월</option>)}</select></label></div>
  <div className="flex gap-2 border-b border-[var(--line)] pb-3 mb-5" role="tablist" aria-label="CPI 분석"><button role="tab" aria-selected={tab==='distribution'} className={btn(tab==='distribution')} onClick={()=>setTab('distribution')}>CPI Distribution</button><button role="tab" aria-selected={tab==='contribution'} className={btn(tab==='contribution')} onClick={()=>setTab('contribution')}>기여도</button></div>
  {error&&<p role="alert">CPI 데이터를 불러오지 못했습니다. 새로고침해 주세요.</p>}{!data&&!error&&<p>Haver CPI 데이터 불러오는 중…</p>}
  {data&&tab==='distribution'&&<><Heatmap core={data.core} metric="momentum" months={heatMonths}/><Heatmap core={data.core} metric="yoy" months={heatMonths}/><p className="text-xs text-[var(--muted)] mb-6">3M/3M은 계절조정 지수의 최근 3개월 평균 / 직전 3개월 평균을 연율화한 값입니다. 국가별 Core 정의는 행에 마우스를 올려 확인할 수 있습니다. 호주는 절사평균을 사용합니다. 빈칸은 미발표·자료 부족이며 보간하지 않습니다. 갱신 {data.generated.slice(0,10)}</p></>}
  {tab==='distribution'?<RawDashboard src="/embeds/cpi_dist.html" title="CPI Distribution"/>:data&&<section>
   <div className="flex flex-wrap gap-3 items-center mb-4"><select aria-label="국가" className={select} value={country} onChange={e=>{setCountry(e.target.value);setSelected('')}}>{Object.keys(data.countries).map(c=><option key={c} value={c}>{names[c]||c}</option>)}</select>{(['yoy','mom'] as const).map(m=><button key={m} className={btn(metric===m)} onClick={()=>setMetric(m)}>{m==='yoy'?'YoY':shortRate}</button>)}<label className="text-sm">표시 기간 <select aria-label="기여도 표시 기간" className={select} value={months} onChange={e=>setMonths(+e.target.value)}>{(quarterly?[12,24,40,80,160]:[12,24,36,60,120]).map(n=><option key={n} value={n}>{n}{quarterly?'분기':'개월'}</option>)}</select></label><label className="text-sm">기준월 <select aria-label="기준월" className={select} value={end} onChange={e=>setSelected(e.target.value)}>{[...dates].reverse().map(d=><option key={d}>{d}</option>)}</select></label></div>
   <div className="rounded-xl border border-[var(--line)] bg-white p-4"><h2 className="text-lg font-semibold">{names[country]} · {metric==='yoy'?'YoY':shortRate} 항목별 추정 기여도</h2><p className="text-xs text-[var(--muted)] my-2">단위 %p · 비계절조정(NSA) · 양(+)과 음(-) 기여를 나누어 누적 · {end} 표시 항목 합계 {fmt(sum)}%p · 가중치 커버리지 {fmt(coverage)}%</p><div className="h-[440px] w-full"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} stackOffset="sign" margin={{top:12,right:20,bottom:20,left:0}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" tick={{fontSize:11}} minTickGap={25}/><YAxis tick={{fontSize:11}} unit="pp"/><Tooltip formatter={value=>typeof value==='number'?`${value.toFixed(3)} %p`:'—'}/><Legend wrapperStyle={{fontSize:11}}/>{groups.map((g,i)=><Bar key={g.index} dataKey={'g'+i} name={g.name} stackId="cpi" fill={colors[i%colors.length]} isAnimationActive={false}/>)}</BarChart></ResponsiveContainer></div><p className="text-xs text-[var(--muted)] leading-relaxed mt-3">{quarterly?'분기 원지수 사용. QoQ는 직전 분기, YoY는 전년 동분기 대비 상승률 × 해당 비교시점 가중치 / 100. 공식 기여도가 아닌 추정치입니다.':data.method} 가중치 또는 비교기간 자료가 없는 항목은 막대에서 제외합니다. 합계는 표시 항목의 합이며 공식 헤드라인 CPI가 아닙니다.</p></div>
   <div className="overflow-x-auto rounded-xl border border-[var(--line)] bg-white p-4 mt-4" data-testid="component-heatmap"><h3 className="text-lg font-semibold mb-3">{names[country]} · 항목별 {metric==='yoy'?'YoY':shortRate} 상승률 히트맵 (%)</h3><div className="flex flex-wrap items-center gap-3 text-base mb-4 text-[#52666b]"><span>{metric==='yoy'?'2%':'0%'} 중심 · 파랑: 기준 이하 / 빨강: 기준 이상 · 회색: 자료 없음</span><span>선택한 기간·기준월 적용</span></div><table className="w-full text-base border-separate border-spacing-[3px]"><thead><tr><th className="sticky left-0 z-10 bg-white text-left min-w-[260px] pr-4">항목</th>{chart.map(row=><th key={String(row.date)} className="font-medium min-w-[86px] py-3">{String(row.date)}</th>)}</tr></thead><tbody>{groups.map(g=><tr key={g.index}><th title={g.descriptor} className="sticky left-0 z-10 bg-white text-left font-medium py-3 pr-4">{g.name}</th>{chart.map(row=>{
    const date=String(row.date),v=g.observations.find(o=>o.date===date)?.[metric]
    return <td key={date} title={`${g.name} · ${date} · ${fmt(v)}%`} style={heatColor(v==null?null:metric==='yoy'?v:v+2)} className="text-center px-3 py-3 font-semibold tabular-nums">{fmt(v)}</td>
   })}</tr>)}</tbody></table></div>
  </section>}
 </div>
}
