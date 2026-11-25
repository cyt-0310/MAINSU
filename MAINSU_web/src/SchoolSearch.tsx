import { useId, useState } from 'react';
// Education Ministry, 114 academic year: https://udb.moe.edu.tw/ulist/Resource
import data from './schoolCatalog.json';

export const schoolCatalog:Record<string,string[]> = data;
export const schoolNames=Object.keys(schoolCatalog).sort((a,b)=>a.localeCompare(b,'zh-TW'));
const normalize=(s:string)=>s.normalize('NFKC').toLowerCase().replace(/臺/g,'台').replace(/\s/g,'');
const schoolAliases:Record<string,string[]>={
  '國立臺灣大學':['台大','臺大','NTU'], '國立政治大學':['政大','NCCU'], '國立清華大學':['清大','NTHU'],
  '國立成功大學':['成大','NCKU'], '輔仁大學':['輔大','FJU'], '淡江大學':['淡大','TKU'],
  '國立陽明交通大學':['陽明交大','陽交大','交大','NYCU'], '國立臺灣科技大學':['台科大','臺科大','NTUST'],
  '國立臺北科技大學':['北科大','NTUT'], '國立臺灣師範大學':['台師大','師大','NTNU'],
  '國立臺北大學':['北大','NTPU'], '國立中央大學':['中央','NCU'], '國立中興大學':['中興','NCHU'],
};
const departmentAliases:Record<string,string[]>={'資訊管理學系':['資管','MIS','IM'],'資訊工程學系':['資工','CS'],'企業管理學系':['企管','BA'],'電機工程學系':['電機','EE'],'財務金融學系':['財金'],'國際企業學系':['國企'],'會計學系':['會計'],'經濟學系':['經濟']};

export function SearchSelect({label,options,value,onSelect,disabled=false,kind}:{label:string;options:string[];value:string;onSelect:(v:string)=>void;disabled?:boolean;kind:'school'|'department'}){
  const id=useId();
  const [query,setQuery]=useState('');
  const [expanded,setExpanded]=useState(false);
  const [active,setActive]=useState(0);
  const aliases=kind==='school'?schoolAliases:departmentAliases;
  const q=normalize(query);
  const found=options.filter(v=>!q||[v,...(aliases[v]??[])].some(a=>normalize(a).includes(q)));
  const results=found.slice(0,40);
  const select=(v:string)=>{onSelect(v);setQuery('');setExpanded(false);setActive(0);};
  return <div className="school-search" onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget))setExpanded(false);}}>
    <label htmlFor={id}>{label}</label>
    <input id={id} role="combobox" aria-autocomplete="list" aria-expanded={expanded&&!disabled} aria-controls={`${id}-list`} aria-activedescendant={expanded&&results[active]?`${id}-${active}`:undefined}
      disabled={disabled} autoComplete="off" placeholder={disabled?'請先選擇學校':`搜尋${label}`} value={expanded?query:value}
      onFocus={()=>{if(!disabled){setQuery('');setActive(0);setExpanded(true);}}}
      onChange={e=>{setQuery(e.target.value);setActive(0);setExpanded(true);if(value)onSelect('');}}
      onKeyDown={e=>{if(e.key==='ArrowDown'){e.preventDefault();setExpanded(true);setActive(i=>Math.min(i+1,Math.max(0,results.length-1)));}else if(e.key==='ArrowUp'){e.preventDefault();setActive(i=>Math.max(0,i-1));}else if(e.key==='Enter'&&expanded&&results[active]){e.preventDefault();select(results[active]);}else if(e.key==='Escape'){setExpanded(false);}}}/>
    {expanded&&!disabled&&<div className="school-search-results" id={`${id}-list`} role="listbox" aria-label={label}>
      {results.map((v,i)=><button type="button" id={`${id}-${i}`} key={v} role="option" aria-selected={v===value} className={i===active?'highlighted':''} onMouseDown={e=>e.preventDefault()} onClick={()=>select(v)}>{v}</button>)}
      {!results.length&&<p>找不到符合的選項</p>}{found.length>results.length&&<p>輸入更多關鍵字縮小搜尋範圍</p>}
    </div>}
  </div>;
}
