import { useEffect, useState, type FormEvent } from "react";

const categories = [
  { id: "statement", label: "學習歷程自述", limit: 1 },
  { id: "activities", label: "多元表現", limit: 10 },
  { id: "coursework", label: "課程學習成果", limit: 3 },
] as const;
type Category = (typeof categories)[number]["id"];
type Draft = Record<Category, File[]>;
type Reuse = {portfolio:string;file:string;category:Category;name:string;size:number};
export type ApplicationTarget = { school: string; department: string };
type Portfolio = {
  id: string;
  school: string;
  department: string;
  status: "queued" | "parsing" | "analyzing" | "ready" | "failed";
  message: string;
  files: { id: string; name: string; category: Category; size: number }[];
};

const emptyDraft: Draft = { statement: [], activities: [], coursework: [] };
const pending = (portfolio: Portfolio) => ["queued", "parsing", "analyzing"].includes(portfolio.status);
const normalize = (value: string) => value.normalize("NFKC").toLowerCase().replace(/\s/g, "").replace(/臺/g, "台");
const sameTarget = (a: ApplicationTarget, b: ApplicationTarget) =>
  normalize(a.school) === normalize(b.school) && normalize(a.department) === normalize(b.department);

const statusLabels:Record<Portfolio['status'],string> = {queued:'等待分析',parsing:'讀取文件中',analyzing:'分析中',ready:'分析完成',failed:'待重試'};
function PortfolioIcon({kind='file'}:{kind?:'file'|'upload'|'school'|'plus'|'chevron'|'close'|'check'}) {
  const paths={file:'M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10l-7-7z M13 3v7h7 M8 15h8 M8 18h6',upload:'M12 16V3 M7 8l5-5 5 5 M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4',school:'M3 10l9-6 9 6 M5 10v9 M19 10v9 M3 20h18 M9 11v8 M15 11v8',plus:'M12 5v14 M5 12h14',chevron:'M9 18l6-6-6-6',close:'M6 6l12 12 M18 6L6 18',check:'M5 12l4 4L19 6'};
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[kind]}/></svg>;
}
function StatusPill({status}:{status:Portfolio['status']}){return <span className={`portfolio-status-pill ${status}`}><i/>{statusLabels[status]}</span>;}
const fileSize=(bytes:number)=>bytes>=1024*1024?`${(bytes/1024/1024).toFixed(1)} MB`:`${Math.max(1,Math.round(bytes/1024))} KB`;

async function readApi<T>(url: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (options?.signal?.aborted) throw error;
    throw new Error("暫時無法連線，請稍後重試。");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload === null) {
    throw new Error(payload?.error || "暫時無法取得資料，請重新載入。");
  }
  return payload as T;
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "操作未完成，請再試一次。";
}

export function PortfolioManager({ applicationTargets }: { applicationTargets: ApplicationTarget[] }) {
  const [records, setRecords] = useState<Portfolio[]>();
  const [active, setActive] = useState<string>();
  const [target, setTarget] = useState({ school: "", department: "" });
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [reuse,setReuse]=useState<Reuse[]>([]);
  const [adding, setAdding] = useState(false);
  const [dragging,setDragging]=useState<Category|null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [retrying, setRetrying] = useState<string>();
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const selected = records?.find((portfolio) => portfolio.id === active);
  const duplicate = records?.find((portfolio) => sameTarget(portfolio, target));
  const savedTargets = applicationTargets.filter((entry, index) =>
    applicationTargets.findIndex((candidate) => sameTarget(candidate, entry)) === index);
  const selectedTarget = savedTargets.findIndex((entry) => sameTarget(entry, target));
  const polling = records?.some(pending) ?? false;

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const list = await readApi<Portfolio[]>("/api/portfolios", { signal: controller.signal });
        if (!controller.signal.aborted) {
          setRecords(list);
          setLoadError("");
        }
      } catch (failure) {
        if (!controller.signal.aborted) setLoadError(errorText(failure));
      }
    }
    void load();
    const timer = polling ? window.setInterval(load, 2000) : undefined;
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [polling, refresh]);

  function addFiles(category: (typeof categories)[number], files: File[]) {
    if (!files.length) return;
    setConfirmed(false);
    const updated = category.limit === 1 ? files : [...draft[category.id], ...files];
    if (updated.length + reuse.filter(r=>r.category===category.id).length > category.limit) {
      setError(`${category.label}最多可放 ${category.limit} 份。`);
      return;
    }
    if (updated.some((file) => !/\.pdf$/i.test(file.name) || !file.size || file.size > 5 * 1024 * 1024)) {
      setError("請選擇 PDF，每份大小上限為 5 MB。");
      return;
    }
    setError("");
    setDraft({ ...draft, [category.id]: updated });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedTarget<0 || !(draft.statement.length||reuse.some(r=>r.category==="statement")) || duplicate || saving) return;
    if (!confirmed) {
      setConfirmed(true);
      return;
    }
    const form = new FormData();
    form.append("school", target.school);
    form.append("department", target.department);
    form.append("reuse",JSON.stringify(reuse));
    categories.forEach(({ id }) => draft[id].forEach((file) => form.append(id, file)));
    setError("");
    setSaving(true);
    try {
      const portfolio = await readApi<Portfolio>("/api/portfolios", { method: "POST", body: form });
      setRecords((current) => [portfolio, ...(current ?? []).filter(({ id }) => id !== portfolio.id)]);
      setActive(portfolio.id);
      setAdding(false);
      setTarget({ school: "", department: "" });
      setDraft(emptyDraft);
      setReuse([]);
      setConfirmed(false);
      setRefresh((previous) => previous + 1);
    } catch (failure) {
      setError(errorText(failure));
      setRefresh((previous) => previous + 1);
    } finally {
      setSaving(false);
    }
  }

  async function retry(portfolio: Portfolio) {
    setRetrying(portfolio.id);
    setError("");
    try {
      const updated = await readApi<Portfolio>(`/api/portfolios/${portfolio.id}/retry`, { method: "POST" });
      setRecords((current) => current?.map((record) => (record.id === updated.id ? updated : record)));
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setRetrying(undefined);
    }
  }

  const startAdding=()=>{setAdding(true);setTarget({school:"",department:""});setDraft(emptyDraft);setReuse([]);setConfirmed(false);setError("");};
  const cancelAdding=()=>{setAdding(false);setTarget({school:"",department:""});setDraft(emptyDraft);setReuse([]);setConfirmed(false);setError("");setDragging(null);};
  const totalFiles=categories.reduce((n,c)=>n+draft[c.id].length,0)+reuse.length;
  const changeTarget=(next:ApplicationTarget)=>{setTarget(next);setConfirmed(false);setError("");};
  return <div className="portfolio-workspace portfolio-redesign">
    {!adding?<>
      <section className="portfolio-panel portfolio-library-head">
        <div className="portfolio-library-title"><span className="portfolio-hero-icon"><PortfolioIcon kind="school"/></span><div><h2>我的備審資料</h2><p>依申請校系管理備審文件與分析進度。</p></div></div>
        <button className="portfolio-primary" type="button" disabled={!records} onClick={startAdding}><PortfolioIcon kind="plus"/> 新增校系備審</button>
      </section>
      {loadError&&<div className="portfolio-panel portfolio-load-error" role="alert">{loadError}<button type="button" onClick={()=>setRefresh(n=>n+1)}>重新載入</button></div>}
      {!loadError&&!records&&<section className="portfolio-panel" role="status">載入校系中…</section>}
      {records?.length===0&&<section className="portfolio-panel portfolio-empty"><span className="portfolio-hero-icon"><PortfolioIcon kind="upload"/></span><h3>尚未上傳備審資料</h3><p>新增申請校系的備審文件，開始準備個人化面試。</p><button className="portfolio-primary" type="button" onClick={startAdding}><PortfolioIcon kind="plus"/> 上傳備審資料</button></section>}
      {!!records?.length&&<div className={`portfolio-browser ${selected?'has-selection':''}`}>
        <section className="portfolio-panel portfolio-collection"><div className="portfolio-section-heading"><h2>已提交備審的校系</h2><span className="portfolio-count">{records.length} 組</span></div>
          <div className="portfolio-school-list">{records.map((record)=><button type="button" key={record.id} className="portfolio-school-card" aria-expanded={active===record.id} onClick={()=>{setActive(active===record.id?undefined:record.id);setError("");}}>
            <span className="portfolio-school-icon"><PortfolioIcon kind="school"/></span><span className="portfolio-school-content"><strong>{record.school}</strong><span>{record.department}</span><span className="portfolio-school-meta"><StatusPill status={record.status}/><small>{record.files.length} 份文件</small></span></span><PortfolioIcon kind="chevron"/>
          </button>)}</div>
        </section>
        {selected&&<section className="portfolio-panel portfolio-detail"><div className="portfolio-detail-head"><div><small>備審文件</small><h2>{selected.school}</h2><p>{selected.department}</p></div><StatusPill status={selected.status}/></div>
          {pending(selected)&&<div className="portfolio-processing" role="status"><span className="portfolio-spinner"/>{statusLabels[selected.status]}…</div>}
          {selected.status==='failed'&&<div className="portfolio-processing failed" role="status">分析未完成，請重試。<button type="button" className="portfolio-primary" disabled={!!retrying} onClick={()=>retry(selected)}>{retrying?'重新分析中…':'重新分析原檔'}</button></div>}
          {categories.map(({id,label})=>{const files=selected.files.filter(f=>f.category===id);return <div className="portfolio-file-group" key={id}><div className="portfolio-section-heading"><h3>{label}</h3><span className="portfolio-count">{files.length} 份</span></div>{files.length?<ul className="portfolio-file-list">{files.map(file=><li key={file.id}><span className="portfolio-pdf-icon">PDF</span><div className="portfolio-file-name"><strong>{file.name}</strong><small>{fileSize(file.size)}</small></div><a className="portfolio-file-link" href={`/api/portfolios/${selected.id}/files/${file.id}`}>查看 <PortfolioIcon kind="chevron"/></a></li>)}</ul>:<div className="portfolio-empty-category">未提供</div>}</div>;})}
        </section>}
      </div>}
    </>:<form className="portfolio-panel portfolio-upload-form" onSubmit={submit}>
      <div className="portfolio-upload-heading"><div className="portfolio-library-title"><span className="portfolio-hero-icon"><PortfolioIcon kind="upload"/></span><div><h2>新增校系備審</h2><p>選擇申請校系，依資料類型上傳 PDF。</p></div></div><button type="button" className="portfolio-close" aria-label="取消新增" disabled={saving} onClick={cancelAdding}><PortfolioIcon kind="close"/></button></div>
      <div className="portfolio-steps"><span className={!target.school||!target.department?'active':'done'}><b>1</b> 選擇校系</span><i/><span className={target.school&&target.department&&!confirmed?'active':confirmed?'done':''}><b>2</b> 上傳文件</span><i/><span className={confirmed?'active':''}><b>3</b> 確認提交</span></div>
      <fieldset disabled={saving}>
        <section className="portfolio-upload-section"><div className="portfolio-section-heading"><h3>申請校系</h3></div>
          <div className="portfolio-fields"><label>從已儲存的申請校系選擇<select required disabled={!savedTargets.length} value={selectedTarget<0?'':String(selectedTarget)} onChange={e=>changeTarget(e.target.value===''?{school:'',department:''}:savedTargets[Number(e.target.value)])}><option value="">請選擇申請校系</option>{savedTargets.map((t,i)=><option key={i} value={i}>{t.school} · {t.department}</option>)}</select></label></div>
          {!savedTargets.length&&<p className="portfolio-error" role="status">尚未儲存申請校系，請先至「申請校系」頁面新增並儲存校系。</p>}
        </section>
        {duplicate?<div className="portfolio-duplicate"><span>這個校系已提交備審。</span><button type="button" className="portfolio-primary" onClick={()=>{setActive(duplicate.id);cancelAdding();}}>查看檔案</button></div>:<section className="portfolio-upload-section"><div className="portfolio-section-heading"><h3>上傳備審文件</h3><span className="portfolio-count">共 {totalFiles} 份</span></div><div className="portfolio-upload-grid">{categories.map(category=><div className="portfolio-upload-card" key={category.id}><div className="portfolio-upload-card-head"><div><h3>{category.label}</h3><p>最多 {category.limit} 份 · 每份 5 MB</p></div><span className={`portfolio-required ${category.id==='statement'?'required':''}`}>{category.id==='statement'?'必傳':'選傳'}</span></div>
            <label className={`portfolio-dropzone ${dragging===category.id?'dragging':''}`} onDragOver={e=>{e.preventDefault();if(!saving)setDragging(category.id);}} onDragLeave={()=>setDragging(null)} onDrop={e=>{e.preventDefault();setDragging(null);if(!saving)addFiles(category,Array.from(e.dataTransfer.files));}}>
              <input type="file" accept=".pdf,application/pdf" multiple={category.limit>1} onChange={e=>{addFiles(category,Array.from(e.currentTarget.files??[]));e.currentTarget.value='';}} aria-label={`選擇${category.label} PDF`}/><span className="portfolio-upload-icon"><PortfolioIcon kind="upload"/></span><strong>選擇 PDF 或拖曳至此</strong><small>PDF 格式</small>
            </label>
            <label className="portfolio-fields">選擇已上傳的檔案<select value="" onChange={e=>{const [portfolio,file]=e.target.value.split(":");const source=records?.find(r=>r.id===portfolio)?.files.find(f=>f.id===file);if(!source)return;if(draft[category.id].length+reuse.filter(r=>r.category===category.id).length>=category.limit){setError("已達此類別檔案數量上限。");return;}setReuse([...reuse,{portfolio,file,category:category.id,name:source.name,size:source.size}]);setConfirmed(false);setError("");}}><option value="">選擇既有 PDF</option>{records?.flatMap(r=>r.files.filter(f=>f.category===category.id&&!reuse.some(x=>x.portfolio===r.id&&x.file===f.id)).map(f=><option key={r.id+f.id} value={r.id+":"+f.id}>{f.name} — {r.school} · {r.department}</option>))}</select></label>
            {reuse.filter(r=>r.category===category.id).map(r=><div className="portfolio-file-list" key={r.portfolio+r.file}><span>{r.name}（沿用）</span><button type="button" className="portfolio-remove" onClick={()=>{setReuse(reuse.filter(x=>x!==r));setConfirmed(false);}}>移除</button></div>)}
            {!!draft[category.id].length&&<ul className="portfolio-file-list">{draft[category.id].map((file,i)=><li key={`${i}-${file.name}`}><span className="portfolio-pdf-icon">PDF</span><div className="portfolio-file-name"><strong>{file.name}</strong><small>{fileSize(file.size)}</small></div><button type="button" className="portfolio-remove" aria-label={`移除 ${file.name}`} onClick={()=>{setDraft({...draft,[category.id]:draft[category.id].filter((_,j)=>i!==j)});setConfirmed(false);}}><PortfolioIcon kind="close"/></button></li>)}</ul>}
          </div>)}</div></section>}
        {confirmed&&!duplicate&&<div className="portfolio-confirmation" role="status"><span className="portfolio-hero-icon"><PortfolioIcon kind="check"/></span><div><strong>確認提交備審</strong><p>{target.school} · {target.department}，共 {totalFiles} 份文件。確認提交後，這組備審無法更換或補傳。</p></div></div>}
        {error&&<p className="portfolio-error" role="alert">{error}</p>}
        <div className="portfolio-actions"><button type="button" className="portfolio-secondary" onClick={cancelAdding}>取消</button>{!duplicate&&<button className="portfolio-primary" type="submit" disabled={selectedTarget<0||!(draft.statement.length||reuse.some(r=>r.category==="statement"))||saving}>{saving?'提交中…':confirmed?'確認提交':'檢查並送出'}<PortfolioIcon kind="chevron"/></button>}</div>
      </fieldset>
    </form>}
    {!adding&&error&&<p className="portfolio-error" role="alert">{error}</p>}
  </div>;
}
