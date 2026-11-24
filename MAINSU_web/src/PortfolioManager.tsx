import { useEffect, useState, type FormEvent } from "react";

const categories = [
  { id: "statement", label: "學習歷程自述", limit: 1 },
  { id: "activities", label: "多元表現", limit: 10 },
  { id: "coursework", label: "課程學習成果", limit: 3 },
] as const;
type Category = (typeof categories)[number]["id"];
type Draft = Record<Category, File[]>;
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

async function readApi<T>(url: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (options?.signal?.aborted) throw error;
    throw new Error("無法連線至 MAINSU 後端。");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload === null) {
    throw new Error(payload?.error || "無法取得 MAINSU 資料，請確認後端已啟動。");
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
  const [adding, setAdding] = useState(false);
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
    if (updated.length > category.limit) {
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
    if (!draft.statement.length || duplicate || saving) return;
    if (!confirmed) {
      setConfirmed(true);
      return;
    }
    const form = new FormData();
    form.append("school", target.school);
    form.append("department", target.department);
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

  return (
    <div className="portfolio-workspace">
      <section className="portfolio-panel">
        <div className="portfolio-heading">
          <h2>已提交備審的校系</h2>
          <button className="portfolio-primary" type="button" disabled={!records || adding}
            onClick={() => { setAdding(true); setError(""); }}>新增校系備審</button>
        </div>
        {loadError && <p role="alert">{loadError} <button type="button" onClick={() => setRefresh((n) => n + 1)}>重新載入</button></p>}
        {!loadError && !records && <p role="status">載入校系中…</p>}
        {records?.length === 0 && <p>目前還沒有提交備審的校系。</p>}
        <div className="portfolio-targets">
          {records?.map((portfolio) => (
            <button type="button" key={portfolio.id} aria-expanded={active === portfolio.id}
              onClick={() => { setActive(active === portfolio.id ? undefined : portfolio.id); setError(""); }}>
              <span><strong>{portfolio.school}</strong><br />{portfolio.department}</span>
              <small>{portfolio.files.length} 份 PDF · {portfolio.status === "failed" ? "待重試" : portfolio.status === "ready" ? "分析完成" : "處理中"}</small>
            </button>
          ))}
        </div>
      </section>
      {selected && (
        <section className="portfolio-panel">
          <h2>{selected.school}　{selected.department}</h2>
          <p role="status">{selected.message}</p>
          {categories.map(({ id, label }) => (
            <div className="portfolio-category" key={id}>
              <h3>{label}</h3>
              {selected.files.some((file) => file.category === id) ? (
                <ul>{selected.files.filter((file) => file.category === id).map((file) => (
                  <li key={file.id}><a href={`/api/portfolios/${selected.id}/files/${file.id}`}>{file.name}</a></li>
                ))}</ul>
              ) : <p>未提供</p>}
            </div>
          ))}
          {selected.status === "failed" && (
            <button className="portfolio-primary" type="button" disabled={!!retrying} onClick={() => retry(selected)}>重新分析原檔</button>
          )}
        </section>
      )}
      {adding && (
        <form className="portfolio-panel" onSubmit={submit}>
          <h2>新增校系備審</h2>
          <fieldset disabled={saving}>
            {savedTargets.length > 0 && (
              <div className="portfolio-fields">
                <label>
                  從申請資料選擇校系
                  <select value={selectedTarget < 0 ? "" : String(selectedTarget)} onChange={(event) => {
                    const value = event.target.value;
                    setTarget(value === "" ? { school: "", department: "" } : savedTargets[Number(value)]);
                    setConfirmed(false);
                    setError("");
                  }}>
                    <option value="">請選擇已填寫的校系，或在下方手動輸入</option>
                    {savedTargets.map((entry, index) => (
                      <option key={index} value={index}>{entry.school}　{entry.department}</option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            <div className="portfolio-fields">
              <label>學校 <input required maxLength={100} value={target.school} onChange={(event) => {
                setTarget({ ...target, school: event.target.value }); setConfirmed(false);
              }} /></label>
              <label>科系 <input required maxLength={100} value={target.department} onChange={(event) => {
                setTarget({ ...target, department: event.target.value }); setConfirmed(false);
              }} /></label>
            </div>
            {duplicate ? (
              <p>這個校系已提交備審。<button type="button" onClick={() => { setActive(duplicate.id); setAdding(false); }}>查看檔案</button></p>
            ) : categories.map((category) => (
              <div className="portfolio-category" key={category.id}>
                <label>
                  <strong>{category.label}</strong>
                  <small>{category.limit === 1 ? "必傳 1 份" : `選傳，最多 ${category.limit} 份`} · 每份 PDF 上限 5 MB</small>
                  <input type="file" accept=".pdf,application/pdf" multiple={category.limit > 1} onChange={(event) => {
                    addFiles(category, Array.from(event.currentTarget.files ?? []));
                    event.currentTarget.value = "";
                  }} />
                </label>
                <ul>{draft[category.id].map((file, index) => (
                  <li key={`${index}-${file.name}`}>{file.name}{" "}
                    <button type="button" onClick={() => {
                      setDraft({ ...draft, [category.id]: draft[category.id].filter((_, i) => i !== index) });
                      setConfirmed(false);
                    }}>移除</button>
                  </li>
                ))}</ul>
              </div>
            ))}
            {!duplicate && confirmed && <p role="status">請核對校系與檔案。確認送出後，這組備審就會鎖定，無法更換或補傳。</p>}
            <div className="portfolio-actions">
              <button type="button" onClick={() => {
                setAdding(false); setConfirmed(false); setError("");
              }}>返回校系列表</button>
              {!duplicate && (
                <button className="portfolio-primary" type="submit" disabled={!normalize(target.school) || !normalize(target.department) || !draft.statement.length}>
                  {saving ? "提交中…" : confirmed ? "確認提交" : "檢查並送出"}
                </button>
              )}
            </div>
          </fieldset>
        </form>
      )}
      {error && <p className="portfolio-error" role="alert">{error}</p>}
    </div>
  );
}
