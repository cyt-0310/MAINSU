import type { Session, Answer } from './VoiceInterview';

export function mean(values: (number|null|undefined)[]): number|null {
  const valid=values.filter((v):v is number=>typeof v==='number'&&Number.isFinite(v));
  return valid.length?valid.reduce((a,b)=>a+b,0)/valid.length:null;
}
const clamp=(n:number)=>Math.max(0,Math.min(100,n));
export function oralParts(a:Answer) {
  const m=a.metrics;
  if(a.mode!=="voice"||!m?.sufficient||m.rate===null||a.duration<=0)return null;
  // Broad provisional ranges, not a single ideal speech rate. Short natural pauses are not penalized.
  const rate=clamp(100-Math.max(0,100-m.rate,m.rate-260)*0.7);
  const count=Array.from(a.text.replace(/[^\p{L}\p{N}]/gu,'')).length;
  const fillers=Object.values(m.fillers).reduce((n,x)=>n+x,0);
  const filler=clamp(100-Math.max(0,fillers/Math.max(1,count)*100-3)*5);
  const longPauses=m.pauses.reduce((n,p)=>n+Math.max(0,p.duration-2),0);
  const pause=clamp(100-Math.max(0,longPauses/a.duration*100-10)*2);
  const time=a.timedOut?60:100;
  return {rate,filler,pause,time,total:rate*.3+filler*.3+pause*.2+time*.2};
}
export const grade=(n:number|null)=>n===null?'未評定':n>=90?'A':n>=80?'B':n>=70?'C':n>=60?'D':'E';
export function scores(session:Session) {
  if(session.id.startsWith('free-'))return {total:null,completeness:null,relevance:null,consistency:null,oral:null};
  const topics=session.summary?.topics??[];
  const rows=session.reportReview?.questions??[];
  const groups=topics.map((t,i)=>{
    const answers=session.answers.map((a,j)=>({a,j})).filter(({a})=>a.topicIndex===i);
    const c=mean(['trait','depth','exp'].map(k=>t.scores?.[k]));
    const r=mean(answers.map(({j})=>rows.find(x=>x.number===j+1)?.relevance));
    const consistency=mean(answers.map(({j})=>rows.find(x=>x.number===j+1)?.consistency));
    const oral=mean(answers.map(({a})=>oralParts(a)?.total));
    const valid=[[c,.45],[r,.25],[consistency,.20],[oral,.10]].filter(([v])=>v!==null) as number[][];
    const total=valid.length?valid.reduce((sum,[v,w])=>sum+v*w,0)/valid.reduce((sum,[,w])=>sum+w,0):null;
    return {completeness:c,relevance:r,consistency,oral,total};
  });
  const completeness=mean(groups.map(g=>g.completeness));
  const relevance=mean(groups.map(g=>g.relevance));
  const consistency=mean(groups.map(g=>g.consistency));
  const oral=mean(groups.map(g=>g.oral));
  // Do not silently treat a failed or unfinished AI assessment as not applicable.
  const total=session.reportReview?.complete&&relevance!==null?mean(groups.map(g=>g.total)):null;
  return {total:isTextSession(session)?null:total,completeness,relevance,consistency,oral:isTextSession(session)?null:oral};
}
export function isTextSession(session:Session) {
  return session.mode==="text" || (session.answers.length>0&&session.answers.every(a=>a.mode==="text"));
}
