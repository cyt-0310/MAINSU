import { useEffect, useRef, useState } from "react";
import { startVoiceInput, type VoiceInput } from "./voiceInput";
import { monitorAudio, readQuestion, type SpeechMetrics } from "./speechMetrics";
import type { ApplicationTarget } from "./PortfolioManager";
import { scores } from "./reportScores";
import { saveFreeReport, workspaceStorage } from "./workspace";

export type Answer = {question:string;text:string;duration:number;timedOut:boolean;metrics?:SpeechMetrics;mode:string;requestId?:string;kind?:string;topicIndex?:number;gaps?:string[];analysisScores?:Record<string,number>|null;targetGap?:string|null;followupReason?:string|null};
export type TopicSummary = {title:string;reasoning?:string;gaps?:string[];relevance_score?:number|null;relevance_status?:string;termination_reason?:string;status?:string;scores?:Record<string,number>|null;followup_count?:number;restate_count?:number;answer_seconds?:number;timed_out_answers?:number;consistency_issues?:{issue_type?:string;note?:string;portfolio_evidence?:string;answer_evidence?:string;portfolio_sources?:{page?:number}[]}[]};
export type Session = {id:string;mode?:"voice"|"text";noPortfolio?:boolean;reportReview?:{version:number;complete?:boolean;questions:{number:number;relevance:number|null;consistency:number|null;consistencyStatus?:string;advice:string}[]}|null;topicIndex?:number;topicCount?:number;topicType?:string;topicTitle?:string;questionNumber?:number;completedAt?:string;dateEstimated?:boolean;target?:ApplicationTarget;pending?:{text:string;question_kind:string}|null;remaining:number;finished:boolean;awaitingRetry?:boolean;answers:Answer[];summary?:{topics?:TopicSummary[];elapsed_seconds?:number;total_questions?:number;termination_reason?:string;pass_threshold?:number};error?:string};
const key = "mainsu.voice.active.v1";
const pendingKey = "mainsu.voice.pending.v1";
const freeKey = "mainsu.voice.free.active.v1";
const checkpointKey = (id:string)=>`mainsu.voice.draft.${id}`;
const submissionKey = (id:string)=>`mainsu.voice.pending.${id}`;
type DraftCheckpoint={question:string;count:number;text:string;elapsed:number;mode:"voice"|"text"};
type ActiveSession={id:string;target:ApplicationTarget;topicIndex:number;topicCount:number;topicType?:string;questionNumber:number;awaitingRetry:boolean};
function sameQuestion(checkpoint:DraftCheckpoint|null,next:Session){return checkpoint?.question===next.pending?.text&&checkpoint?.count===next.answers.length;}
export const pendingFreeReports = "pending-free-reports";
async function api(url:string, body?:unknown):Promise<Session> {
  const response = await fetch(url, body === undefined ? undefined : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data = await response.json().catch(()=>null);
  if (response.status===404 && !data) throw new Error("暫時無法開始面試，請重新連線。");
  if (!response.ok || !data) throw new Error(data?.error || "連線失敗，請重新連線。");
  return data;
}
export function VoiceInterview({accountId,target,free=false,mode,noPortfolio=false,resumeId,onExit,renderReport}:{accountId:string;target?:ApplicationTarget;free?:boolean;mode:"voice"|"text";noPortfolio?:boolean;resumeId?:string;onExit:()=>void;renderReport?:(session:Session)=>React.ReactNode}) {
  const storage = workspaceStorage(accountId);
  const readStored = storage.read;
  function queued(id: string) {
    const old = readStored<{ id: string; answer: Answer }>(pendingKey);
    return readStored<{ id: string; answer: Answer }>(submissionKey(id)) ?? (old?.id === id ? old : null);
  }
  function clearQueue(id: string) {
    storage.remove(submissionKey(id));
    if (readStored<{ id: string }>(pendingKey)?.id === id) storage.remove(pendingKey);
  }
  const [session,setSession] = useState<Session|null>(null);
  const [phase,setPhase] = useState("loading");
  const [error,setError] = useState("");
  const [draft,setDraft] = useState("");
  const [level,setLevel] = useState(0);
  const [timeWarning,setTimeWarning] = useState(false);
  const [round,setRound] = useState(0);
  const [modeNow,setModeNow] = useState(mode);
  const [micState,setMicState] = useState<"idle"|"testing"|"passed">(!free&&!resumeId&&mode==="voice"?"passed":"idle");
  const [micMessage,setMicMessage] = useState(!free&&!resumeId&&mode==="voice"?"已於面試準備頁完成麥克風檢測。":"");
  const [resumed,setResumed] = useState(false);
  const elapsedBase = useRef(0);
  const preflightDone = useRef(false);
  const micTest = useRef<VoiceInput|null>(null);
  const micMonitor = useRef<Awaited<ReturnType<typeof monitorAudio>>|null>(null);
  const [cameraOn,setCameraOn] = useState(false);
  const [cameraError,setCameraError] = useState("");
  const [cameraBusy,setCameraBusy] = useState(false);
  const cameraStream = useRef<MediaStream|null>(null);
  const videoRef = useRef<HTMLVideoElement|null>(null);
  function stopCamera(){cameraStream.current?.getTracks().forEach(track=>track.stop());cameraStream.current=null;setCameraOn(false);}
  async function startCamera(){
    setCameraBusy(true);setCameraError("");
    try {
      const stream=await navigator.mediaDevices.getUserMedia({video:true,audio:false});
      if(closing.current||!videoRef.current){stream.getTracks().forEach(track=>track.stop());return;}
      cameraStream.current=stream;setCameraOn(true);
      if(videoRef.current)videoRef.current.srcObject=stream;
    }catch{setCameraError("無法開啟攝影機，請確認瀏覽器權限或裝置是否可用。");}
    finally{setCameraBusy(false);}
  }
  const voice = useRef<VoiceInput|null>(null);
  const audio = useRef<Awaited<ReturnType<typeof monitorAudio>>|null>(null);
  const stopSpeech = useRef<(()=>void)|null>(null);
  const deadline = useRef(0);
  const begin = useRef(0);
  const latest = useRef("");
  const submitting = useRef(false);
  const initialized = useRef(false);
  const closing = useRef(false);
  const freeQuestions = ["請用一分鐘自我介紹。","你為什麼想申請這個科系？","請分享一次解決問題的經驗。"];
  const finishReport = (next:Session) => {
    if (free) {
      const record = { ...next, completedAt: next.completedAt ?? new Date().toISOString() };
      const pending = readStored<Session[]>(pendingFreeReports) ?? [];
      storage.write(pendingFreeReports, [record, ...pending.filter(item => item.id !== record.id)]);
      void saveFreeReport(record, accountId).then(() => {
        const remaining = readStored<Session[]>(pendingFreeReports) ?? [];
        storage.write(pendingFreeReports, remaining.filter(item => item.id !== record.id));
      }).catch(() => {});
      storage.remove(freeKey);
    }
    if (readStored<{ id: string }>(key)?.id === next.id) storage.remove(key);
    clearQueue(next.id);
    storage.remove(checkpointKey(next.id));
  };
  function accept(next:Session, initial=false) {
    if(next.finished&&!next.completedAt)next={...next,completedAt:new Date().toISOString()};
    setSession(next);setError(next.error||"");setTimeWarning(false);deadline.current=0;elapsedBase.current=0;
    if(free&&!next.finished)storage.write(freeKey,next);
    const pending=queued(next.id);
    if(pending&&next.answers.some(a=>a.requestId===pending.answer.requestId))clearQueue(next.id);
    const unsent=queued(next.id);
    const checkpoint=readStored<DraftCheckpoint>(checkpointKey(next.id));
    const draftText=next.awaitingRetry?next.answers[next.answers.length-1]?.text||"":unsent?.answer.text||(sameQuestion(checkpoint,next)?checkpoint?.text||"":"");
    if(!next.awaitingRetry&&!unsent&&sameQuestion(checkpoint,next))elapsedBase.current=Math.min(next.remaining,checkpoint!.elapsed);
    else if(!next.awaitingRetry&&!unsent)storage.remove(checkpointKey(next.id));
    setDraft(draftText);latest.current=draftText;
    if(next.finished){stopCamera();finishReport(next);setPhase("report");}
    else if(next.awaitingRetry||unsent){setPhase("retry");}
    else if((initial||!preflightDone.current)&&(free||resumeId&&next.mode!=="text")){setPhase("confirmMic");}
    else {setPhase("ready");setRound(n=>n+1);}
  }
  async function initialize() {
    setPhase("loading");setError("");
    try {
      if(free){const saved=readStored<Session>(freeKey);setResumed(!!saved);if(saved){const checkpoint=readStored<DraftCheckpoint>(checkpointKey(saved.id));if(sameQuestion(checkpoint,saved))setModeNow(checkpoint!.mode);else if(saved.answers[saved.answers.length-1]?.mode==="text")setModeNow("text");}accept(saved||{id:"free-"+crypto.randomUUID(),remaining:90,finished:false,answers:[],pending:{text:freeQuestions[0],question_kind:"main"}},true);return;}
      if(!target)throw new Error("請先選擇校系");
      const list=await fetch("/api/voice-interviews/active").then(r=>{if(!r.ok)throw Error("暫時無法取得面試進度，請重試。");return r.json() as Promise<ActiveSession[]>;});
      const saved=list.find(x=>x.id===resumeId);
      const next=saved?await api("/api/voice-interviews/"+saved.id):await api("/api/voice-interviews",{...target,mode,noPortfolio});
      setResumed(!!saved);storage.write(key,{id:next.id,target});
      const checkpoint=readStored<DraftCheckpoint>(checkpointKey(next.id));
      if(next.mode)setModeNow(next.mode);
      else if(sameQuestion(checkpoint,next))setModeNow(checkpoint!.mode);
      else if(saved&&next.answers[next.answers.length-1]?.mode==="text")setModeNow("text");
      accept(next,true);
    }catch(e){setError(String(e));setPhase("failed");}
  }
  async function testMic(){
    setMicState("testing");setMicMessage("請說一句話，確認麥克風與語音辨識。");
    try{
      micMonitor.current=await monitorAudio(setLevel);
      if(closing.current){micMonitor.current.stop();return;}
      micTest.current=startVoiceInput({continuous:false,onStart:()=>{},onText:()=>{},onEnd:(text,warning)=>{micTest.current=null;micMonitor.current?.stop();micMonitor.current=null;setMicState(text.trim()?"passed":"idle");setMicMessage(text.trim()?"麥克風測試成功："+text:warning||"沒有辨識到聲音，請重試。");}});
    }catch(e){micMonitor.current?.stop();micMonitor.current=null;setMicState("idle");setMicMessage(String(e));}
  }
  useEffect(()=>{if(micState!=="testing")return;const t=window.setTimeout(()=>micTest.current?.stop(),12000);return ()=>clearTimeout(t);},[micState]);
  function saveDraft(){if(!session?.pending||submitting.current)return;const elapsed=Math.min(session.remaining,elapsedBase.current+(deadline.current?Math.max(0,(performance.now()-begin.current)/1000):0));storage.write(checkpointKey(session.id),{question:session.pending.text,count:session.answers.length,text:latest.current,elapsed,mode:modeNow});}
  useEffect(()=>{if(!initialized.current){initialized.current=true;void initialize();}},[]);
  useEffect(()=>{closing.current=false;return ()=>{closing.current=true;micTest.current?.cancel();micMonitor.current?.stop();cameraStream.current?.getTracks().forEach(track=>track.stop());voice.current?.cancel();audio.current?.stop();stopSpeech.current?.();};},[]);
  function startClock(){if(deadline.current<=performance.now()){begin.current=performance.now();deadline.current=begin.current+Math.max(0,(session?.remaining||0)-elapsedBase.current)*1000;}const left=deadline.current-performance.now();setTimeWarning(left>0&&left<=30000);setPhase("answering");}
  async function send(answer?:Answer) {
    if(!session||submitting.current)return;
    submitting.current=true;setPhase("analyzing");setError("");
    try{
      if(free){
        const answers=[...session.answers,answer!];
        const done=answers.length>=freeQuestions.length;
        accept({...session,answers,finished:done,remaining:120,pending:done?null:{text:freeQuestions[answers.length],question_kind:"main"}});return;
      }
      if(answer)storage.write(submissionKey(session.id),{id:session.id,answer:{...answer,requestId:crypto.randomUUID()}});
      const saved=queued(session.id);
      const next=await api("/api/voice-interviews/"+session.id,session.awaitingRetry?{retryOnly:true}:saved?.answer||{retryOnly:true});
      clearQueue(session.id);storage.remove(checkpointKey(session.id));
      accept(next);
    }catch(e){setError(String(e));setPhase("retry");}finally{submitting.current=false;}
  }
  function complete(text=latest.current, timedOut=false, warning?:string) {
    if(!session||submitting.current)return;
    const duration=Math.min(session.remaining,elapsedBase.current+Math.max(0,(performance.now()-begin.current)/1000));
    const metrics=audio.current?.stop(text,duration,warning);
    if(metrics&&elapsedBase.current>0){metrics.sufficient=false;metrics.rate=null;metrics.recognitionWarning="此題曾中斷續接，僅有本次錄音的聲音指標，不作完整口語評估。";}
    audio.current=null;voice.current=null;
    void send({question:session.pending?.text||"",text,duration,timedOut,metrics,mode:modeNow});
  }
  async function listen() {
    setPhase("starting");
    const prefix=latest.current;const merge=(text:string)=>[prefix,text].filter(Boolean).join(" ");
    try{
      audio.current=await monitorAudio(setLevel);
      if(closing.current){audio.current.stop();return;}
      voice.current=startVoiceInput({continuous:true,onStart:startClock,onText:text=>{latest.current=merge(text);setDraft(latest.current);},onEnd:(text,warning)=>{
        voice.current=null;
        if(warning){latest.current=text?merge(text):latest.current;setDraft(latest.current); if(latest.current.trim()){complete(latest.current,false,warning);return;} audio.current?.stop();audio.current=null;setError(warning);setPhase("captureError");return;}
        complete(text?merge(text):latest.current,performance.now()>=deadline.current);
      }});
    }catch(e){audio.current?.stop();audio.current=null;setError(String(e));setPhase("captureError");}
  }
  useEffect(()=>{
    if(phase!=="ready"||!session?.pending)return;
    preflightDone.current=true;
    if(modeNow==="text"){startClock();return;}
    setPhase("reading");
    stopSpeech.current=readQuestion(session.pending.text,()=>{stopSpeech.current=null;void listen();});
  },[round,phase==="ready"]);
  useEffect(()=>{
    if(phase!=="answering")return;
    const timer=window.setInterval(()=>{
      const left=Math.max(0,Math.ceil((deadline.current-performance.now())/1000));saveDraft();
      setTimeWarning(left>0&&left<=30);
      if(!left){clearInterval(timer);if(voice.current){setPhase("stopping");voice.current.stop();}else complete(latest.current,true);}
    },100);
    return ()=>clearInterval(timer);
  },[phase]);
  useEffect(()=>{const save=()=>{if(phase==="answering")saveDraft();};window.addEventListener("pagehide",save);return()=>window.removeEventListener("pagehide",save);},[phase,session,modeNow]);
  if(phase==="report"&&session)return renderReport?renderReport(session):<VoiceReport session={session} free={free} onExit={onExit}/>;
  const status:Record<string,string> = {loading:"建立面試中",ready:"準備開始",reading:"教授正在朗讀",starting:"啟動麥克風",answering:"作答中",stopping:"整理回答",analyzing:"AI 分析中",retry:"面試已暫停",failed:"連線失敗",captureError:"收音異常",confirmMic:"確認麥克風"};
  const kind = session?.pending?.question_kind;
  const questionNumber = session?.questionNumber??((session?.answers.length||0)+(session?.awaitingRetry?0:1));
  const topicIndex=session?.topicIndex??(free?Math.min(2,session?.answers.length||0):0);
  const topicLabel=session?.topicType||(topicIndex===0?"自我介紹":free?"其他主題":"學習歷程");
  return <div className="interview-page voice-room">
    <header className="interview-header voice-room-header"><div><strong>MAINSU</strong><small>{target?`${target.school} · ${target.department}`:"模擬面試"}</small></div><button className="voice-action-btn" onClick={()=>{if(phase==="answering")saveDraft();stopCamera();micTest.current?.cancel();micMonitor.current?.stop();voice.current?.cancel();audio.current?.stop();stopSpeech.current?.();onExit();}}>保存並離開</button></header>
    <main className="voice-room-grid">
      <aside className="voice-room-videos">
        <section className="voice-room-card"><div className="voice-room-label">AI 面試教授 <span>虛擬面試官</span></div><div className="voice-professor-screen"><div className="voice-professor-avatar" aria-hidden="true">AI</div><strong>{phase==="reading"?"正在提問":phase==="analyzing"?"正在分析回答":"AI 教授"}</strong></div></section>
        <section className="voice-room-card"><div className="voice-room-label">我的攝影機 <span>{cameraOn?"預覽中":"已關閉"}</span></div><div className="voice-camera-screen"><video ref={videoRef} autoPlay muted playsInline style={{visibility:cameraOn?"visible":"hidden"}}/>{!cameraOn&&<div className="voice-camera-placeholder"><strong>攝影機尚未開啟</strong></div>}</div><div className="voice-camera-controls"><button className="voice-action-btn" disabled={cameraBusy} onClick={()=>cameraOn?stopCamera():void startCamera()}>{cameraBusy?"開啟中…":cameraOn?"關閉攝影機":"開啟攝影機"}</button></div>{cameraError&&<p role="alert" className="voice-room-error">{cameraError}</p>}</section>
      </aside>
      <section className="voice-room-content">
        <div className="voice-room-card voice-stage"><div className="voice-room-label">面試階段 <span>{resumed?"已接續上次面試":"新面試"}</span></div><div className="voice-stage-steps">{Array.from({length:session?.topicCount??3},(_,i)=><div key={i} className={i===topicIndex?"current":i<topicIndex?"done":""}>{i+1}. {i===0?"自我介紹":free?"其他主題":"學習歷程"}</div>)}</div><p>目前：{topicLabel}{session?.topicTitle?` · ${session.topicTitle}`:""}</p></div>
        <div className="voice-room-card voice-question"><div className="voice-room-label">第 {Math.max(1,questionNumber)} 題 · {kind==="restate"?"重述":kind==="followup"?"追問":"主問題"}<span className="voice-status">{status[phase]||phase}</span></div><h1>{session?.pending?.text||"準備面試中"}</h1>{phase==="answering"&&timeWarning&&<div className="voice-time-warning" role="status"><strong>作答時間剩餘 30 秒內</strong><span>請掌握重點，準備結束回答。</span></div>}<div className="voice-room-timer" style={{gridTemplateColumns:"1fr"}}><div><small>麥克風音量</small><meter min={0} max={100} value={level}/><small>{phase==="analyzing"?"回答已保存，AI 分析與備援期間暫停計時":phase==="retry"?"回答已保留，請重試分析":phase==="answering"?"正在作答":"等待作答"}</small></div></div></div>
        <div className={modeNow==="text"?"voice-room-card voice-live-transcript":"voice-room-card"}>
          {modeNow==="text"&&<><div className="voice-room-label">文字回答 <span>手動輸入</span></div><textarea aria-label="文字回答" placeholder="請在這裡輸入回答…" value={draft} readOnly={phase!=="answering"} onChange={e=>{latest.current=e.target.value;setDraft(e.target.value);}}/></>}
          {modeNow==="voice"&&<div className="voice-room-label">面試操作 <span>{status[phase]||phase}</span></div>}
        {error&&<p role="alert" className="voice-room-error">{error}</p>}
        <div className="voice-room-actions">{phase==="answering"&&<button className="voice-action-btn" onClick={()=>{if(voice.current){setPhase("stopping");voice.current.stop();}else complete();}}>結束作答</button>}{phase==="retry"&&<button className="voice-action-btn" onClick={()=>void send()}>重試原回答分析</button>}{phase==="failed"&&<button className="voice-action-btn" onClick={()=>void initialize()}>重新連線</button>}{phase==="captureError"&&<><button className="voice-action-btn" onClick={()=>void listen()}>重試收音</button></>}{phase==="confirmMic"&&<div className="voice-preflight"><strong>面試前設備檢測</strong><p>攝影機非必要，可不開啟。語音作答請先確認麥克風。</p><p>{micMessage}</p>{modeNow==="voice"&&<><button className="voice-action-btn" disabled={micState==="testing"} onClick={()=>void testMic()}>{micState==="testing"?"測試中…":micState==="passed"?"重新測試":"測試麥克風"}</button><button className="voice-action-btn" disabled={micState!=="passed"} onClick={()=>setPhase("ready")}>{resumed?"接續面試":"開始面試"}</button></>}{free&&<><button className="voice-action-btn" disabled={micState==="testing"} onClick={()=>setModeNow("text")}>選擇文字作答</button>{modeNow==="text"&&<><p role="alert">文字面試不提供總分、口語評分及面部行為分析。</p><button className="voice-action-btn" onClick={()=>setPhase("ready")}>開始文字面試</button><button className="voice-action-btn" onClick={()=>setModeNow("voice")}>改選語音面試</button></>}</>}</div>}{phase==="reading"&&<button className="voice-action-btn" onClick={()=>{stopSpeech.current?.();stopSpeech.current=null;void listen();}}>跳過朗讀</button>}</div></div>
      </section>
    </main>
  </div>;
}




export function VoiceReport({session,free=false,onExit}:{session:Session;free?:boolean;onExit:()=>void}) { return <div className="answer-panel" style={{width:"min(100%, 1000px)",maxWidth:1000,margin:"32px auto"}}><h1>本場面試報告</h1><p>作答 {session.answers.length} 次 · {free?"免費練習":"個人化面試"}</p>{session.answers.map((a,i)=><section className="card" key={i}><h2>{i+1}. {a.question}</h2><p>{a.text||"未作答"}</p><p>作答 {a.duration.toFixed(1)} 秒 {a.timedOut?"· 超時":""}</p>{a.metrics?<><p>語速：{a.metrics.rate??"資料不足"} 字／分鐘；聲音活動：{a.metrics.audibleSeconds} 秒</p><p>填充詞：{Object.entries(a.metrics.fillers).filter(([,n])=>n).map(([w,n])=>w+" "+n+" 次").join("、")||"未辨識到"}</p><p>停頓估計：{a.metrics.pauses.length} 次，合計 {a.metrics.pauses.reduce((total,p)=>total+p.duration,0).toFixed(1)} 秒（音量門檻估計）</p><p>改善建議：{a.metrics.pauses.length?"練習分段說明，但保留自然思考停頓。":"練習清楚表達重點，避免刻意加快語速。"}</p>{a.metrics.recognitionWarning&&<p>辨識待核對：{a.metrics.recognitionWarning}</p>}{!a.metrics.sufficient&&<p>語音資料不足，不計口語分數。</p>}</>:<p>文字作答，無語音分析資料。</p>}</section>)}{session.summary?.topics?.map((t,i)=><section className="card" key={i}><h3>{t.title}</h3><p>{t.relevance_status||"未評估"} · {t.termination_reason}</p><p>{t.reasoning}</p></section>)}<button className="voice-action-btn" onClick={onExit}>返回總覽</button></div>; }

export function ResumeInterviews({accountId,onResume,onFree}:{accountId:string;onResume:(target:ApplicationTarget,id:string)=>void;onFree:()=>void}){
  const [items,setItems]=useState<ActiveSession[]>([]);const [failed,setFailed]=useState(false);const freeSaved=workspaceStorage(accountId).read<Session>(freeKey);
  useEffect(()=>{let live=true;fetch("/api/voice-interviews/active").then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{if(live)setItems(data);}).catch(()=>{if(live)setFailed(true);});return()=>{live=false;};},[]);
  if(!items.length&&!freeSaved&&!failed)return null;
  return <section className="voice-room-card resume-card"><h2>未完成的面試</h2>{failed&&<p>暫時無法取得面試進度，請重新載入。</p>}{items.map(item=><div className="resume-row" key={item.id}><div><strong>{item.target.school} · {item.target.department}</strong><p>{item.topicType||"面試中"} · 第 {item.questionNumber} 題 · {item.awaitingRetry?"等待分析":"尚未完成"}</p></div><button className="voice-action-btn" onClick={()=>onResume(item.target,item.id)}>繼續上次面試</button></div>)}{freeSaved&&!freeSaved.finished&&<div className="resume-row"><div><strong>免費練習</strong><p>第 {freeSaved.answers.length+1} 題</p></div><button className="voice-action-btn" onClick={onFree}>繼續上次面試</button></div>}</section>;
}

export function VoiceHistory({onSelect,records}:{onSelect?:(session:Session)=>void;records:Session[]}) {
  const [selected,setSelected] = useState<Session>();
  if(selected)return <VoiceReport session={selected} free={selected.id.startsWith("free-")} onExit={()=>setSelected(undefined)}/>;
  if(!records.length)return null;
  return <section className="card interview-history-card"><div className="card-title"><div><h2>面試紀錄</h2><p>選擇一場面試查看完整報告</p></div></div>{records.map(record=>{const marks=scores(record);return <div key={record.id} className="interview-history-row"><div className="history-record-info"><strong>{record.target?record.target.school+" · "+record.target.department:"免費基礎練習"}</strong><small title={record.dateEstimated?"舊紀錄的最後保存日期":"面試完成日期"}>{record.completedAt?new Date(record.completedAt).toLocaleDateString("zh-TW"):"日期未記錄"} · {record.answers.length} 題作答</small></div><div className="history-record-score"><small>總分</small><strong>{marks.total===null?"—":Math.round(marks.total)}</strong></div><button className="voice-action-btn history-report-button" onClick={()=>onSelect?onSelect(record):setSelected(record)}>查看報告 <span aria-hidden="true">→</span></button></div>})}</section>;
}
