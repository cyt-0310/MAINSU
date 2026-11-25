import type { Answer, Session } from './VoiceInterview';
import { oralParts } from './reportScores';
import { reportText } from './reportText';

const dimensions = [{key:'trait',name:'個人特質'},{key:'depth',name:'深度邏輯'},{key:'exp',name:'經驗內容'}];
const gapSuggestions:Record<string,string>={trait:'補充你展現的能力或態度，並舉出具體行為。',depth:'說明你為什麼做出這個決定、比較過哪些方案及背後理由。',exp:'補充情境、你的具體行動、成果與反思。'};
const time=(secs:number)=>`${String(Math.floor(secs/60)).padStart(2,'0')}:${String(Math.floor(secs%60)).padStart(2,'0')}`;
const nameOf=(key:string)=>dimensions.find(d=>d.key===key)?.name??key;
const valid=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100;
const value=(a:Answer|undefined,key:string)=>{const v=a?.analysisScores?.[key];return valid(v)?v:null;};
const fmt=(v:number|null)=>v===null?'—':Math.round(v*10)/10;
const delta=(v:number)=>`${v>0?'+':''}${fmt(v)}`;
const average=(arr:number[])=>arr.length?arr.reduce((a,b)=>a+b,0)/arr.length:null;
const lastAssessed=(turns:{a:Answer}[])=>turns.filter(t=>dimensions.some(d=>value(t.a,d.key)!==null)).slice(-1)[0]?.a;

export function followupGroups(session:Session){
  const threshold=session.summary?.pass_threshold??55;
  return (session.summary?.topics??[]).map((topic,index)=>{
    const turns=session.answers.map((a,i)=>({a,number:i+1})).filter(t=>t.a.topicIndex===index);
    const followups=turns.filter(t=>t.a.kind==='followup');
    const first=turns.findIndex(t=>t.a.kind==='followup');
    const before=first<0?undefined:lastAssessed(turns.slice(0,first));
    const after=first<0?undefined:lastAssessed(turns.slice(first));
    const comparison=dimensions.map(d=>({...d,before:value(before,d.key),after:value(after,d.key)}));
    const pairs=comparison.filter(d=>d.before!==null&&d.after!==null);
    const gain=pairs.length===3?average(pairs.map(d=>d.after!-d.before!)):null;
    const closed=pairs.filter(d=>d.before!<threshold&&d.after!>=threshold);
    return {topic,index,turns,followups,comparison,gain,closed};
  });
}

export function FollowupAnalysis({session}:{session:Session}){
  const groups=followupGroups(session);
  const threshold=session.summary?.pass_threshold??55;
  const mainCount=session.answers.filter(a=>a.kind==='main').length;
  const followupCount=session.answers.filter(a=>a.kind==='followup').length;
  const compared=groups.filter(g=>g.gain!==null);
  const gain=average(compared.map(g=>g.gain!));
  const closed=compared.reduce((n,g)=>n+g.closed.length,0);
  const assessed=compared.length>0;
  const grouped=new Set(groups.flatMap(g=>g.turns.map(t=>t.number)));
  const ungrouped=session.answers.map((a,i)=>({a,number:i+1})).filter(t=>!grouped.has(t.number));
  return <section className="card followup-analysis">
    <div className="followup-feature-head"><div><span className="followup-feature-label">MAINSU · 動態追問</span><h2>動態追問與作答分析</h2><p>從主問題辨識資訊缺口，透過針對性追問補足回答。</p></div><span className="followup-feature-icon" aria-hidden="true">↗</span></div>
    <div className="followup-kpis">{[{label:'主問題',v:mainCount+' 題'},{label:'動態追問',v:followupCount+' 題'},{label:'已補足缺口',v:assessed?closed+' 項':'—'},{label:'平均完整度變化',v:gain===null?'—':delta(gain)+' 分'}].map(k=><div key={k.label}><span>{k.label}</span><strong>{k.v}</strong></div>)}</div>
    {assessed&&<p className="followup-explanation">比較有完整前後評估的 {compared.length} 個主題；由低於 {threshold} 分提升至達標的面向計為已補足缺口。</p>}
    <div className="followup-topic-list">{groups.filter(g=>g.turns.length).map(g=><details className="followup-topic" key={g.index}>
      <summary><span className="followup-topic-number">{g.index+1}</span><span className="followup-topic-title"><strong>{g.topic.title}</strong><small>{g.followups.length?`${g.followups.length} 次追問`:'無追問'} · {time(g.topic.answer_seconds??g.turns.reduce((n,t)=>n+t.a.duration,0))} · {g.topic.relevance_status??'未評估'}</small></span><span className="followup-topic-gain">{g.gain!==null?`${delta(g.gain)} 分`:g.followups.length?'—':''}</span><span className="followup-arrow" aria-hidden="true">⌄</span></summary>
      <div className="followup-topic-body">
        {g.followups.length>0&&<div className="followup-compare"><div className="followup-compare-title"><h3>追問前後完整度</h3><div><span className="followup-dot before"/> 追問前 <span className="followup-dot after"/> 追問後</div></div>{g.comparison.map(d=><div className="followup-dimension" key={d.key}><strong>{d.name}</strong><div className="followup-bar-pair">{([{v:d.before,cls:'before'},{v:d.after,cls:'after'}]).map(x=><div className="followup-bar-row" key={x.cls}><div className="followup-track">{x.v!==null&&<i className={x.cls} style={{width:`${x.v}%`}}/>}</div><span>{fmt(x.v)}</span></div>)}</div><span className="followup-change">{d.before!==null&&d.after!==null?delta(d.after-d.before):'—'}</span></div>)}</div>}
        <h3>逐題作答與追問</h3>
        <div className="followup-turns">{g.turns.map(({a,number},i)=><AnswerTurn key={number} a={a} number={number} session={session} previous={lastAssessed(g.turns.slice(0,i))} threshold={threshold}/>)}</div>
        {g.topic.termination_reason&&<p className="followup-end">主題結束原因：{g.topic.termination_reason}</p>}
      </div>
    </details>)}</div>
    {ungrouped.length>0&&<div className="followup-topic-body"><h3>其他作答紀錄</h3><div className="followup-turns">{ungrouped.map(({a,number})=><AnswerTurn key={number} a={a} number={number} session={session} threshold={threshold}/>)}</div></div>}
  </section>;
}

function AnswerTurn({a,number,session,previous,threshold}:{a:Answer;number:number;session:Session;previous?:Answer;threshold:number}){
  const result=session.reportReview?.questions.find(q=>q.number===number);
  const oral=oralParts(a);
  const advice=result?.advice||(a.gaps?.length?a.gaps.map(g=>gapSuggestions[g]||'補充具體內容。').join(' '):a.timedOut?'先回答核心問題，再簡短補充例子，避免超時。':'建議先說明核心結論，再補充具體作法與結果。');
  const filled=dimensions.filter(d=>{const b=value(previous,d.key),v=value(a,d.key);return b!==null&&v!==null&&b<threshold&&v>=threshold;});
  const consistency=result?.consistency==null?(!result?'等待評分':result.consistencyStatus==='pending'?'待核對':result.consistencyStatus==='not_applicable'?'不適用':'未評估'):`${result.consistency} 分`;
  return <details className="followup-turn" open={a.kind!=='followup'}>
    <summary><span className="followup-turn-type">{a.kind==='followup'?'追問':a.kind==='restate'?'重述':'主問題'} · 第 {number} 題</span><strong>{a.question}</strong><span className="followup-arrow" aria-hidden="true">⌄</span></summary>
    <div className="followup-turn-body">
      <div className="followup-turn-meta">{time(a.duration)} · {a.mode==='voice'?'語音作答':'文字作答'}{a.timedOut?' · 超時':''}</div>
      {a.kind==='followup'&&<div className="followup-reason"><h4>為什麼追問？</h4>{previous?.targetGap&&<span className="followup-gap-tag">{nameOf(previous.targetGap)}</span>}{previous?.gaps?.length?<p>前一輪缺口：{previous.gaps.map(nameOf).join('、')}</p>:null}<p>{reportText(a.followupReason??'無追問原因紀錄')}</p></div>}
      <h4>學生回答</h4><p className="report-answer-text">{a.text||'未作答'}</p>
      <div className="report-answer-scores"><span>相關度：{result?.relevance==null?'未評估':`${result.relevance} 分`}</span><span>一致性：{consistency}</span>{oral&&<span>口語：{fmt(oral.total)} 分</span>}</div>
      {a.metrics&&<p className="followup-turn-meta">語音資料：{a.metrics.sufficient?`語速 ${a.metrics.rate??'未評估'} 字/分鐘 · 停頓 ${a.metrics.pauses.length} 次`:'資料不足，未評估'}</p>}
      {a.analysisScores&&<><h4>本輪累積分析</h4><div className="followup-round-scores">{dimensions.map(d=><span key={d.key}>{d.name} <b>{fmt(value(a,d.key))}</b></span>)}</div><p>{a.gaps?.length?'尚待補足：'+a.gaps.map(nameOf).join('、'):'三項完整度皆達標'}</p>{a.kind==='followup'&&filled.length>0&&<p className="followup-filled">本輪已補足：{filled.map(d=>d.name).join('、')}</p>}</>}
      <div className="report-question-advice"><h4>改善建議{!result?'（初步）':''}</h4><p>{reportText(advice)}</p></div>
    </div>
  </details>;
}
