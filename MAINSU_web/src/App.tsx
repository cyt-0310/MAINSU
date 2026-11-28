import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { PortfolioManager, type ApplicationTarget } from "./PortfolioManager";
import { startVoiceInput, type VoiceInput } from "./voiceInput";
import { VoiceInterview, VoiceHistory, ResumeInterviews, pendingFreeReports, type Session } from "./VoiceInterview";
import { monitorAudio } from "./speechMetrics";
import { scores, grade, oralParts, mean, isTextSession } from "./reportScores";
import { FollowupAnalysis } from "./FollowupAnalysis";
import { reportText } from "./reportText";
import { SearchSelect, schoolCatalog, schoolNames } from "./SchoolSearch";
import { saveFreeReport, workspaceRequest, workspaceStorage, type Account } from "./workspace";

type Page =
  | "landing"
  | "login"
  | "register"
  | "dashboard"
  | "plans"
  | "profile"
  | "upload"
  | "analysis"
  | "prepare"
  | "interview"
  | "freeInterview"
  | "report"
  | "freeReport"
  | "history"
  | "settings"
  | "logout";

type IconName =
  | "spark"
  | "arrow"
  | "check"
  | "file"
  | "mic"
  | "chart"
  | "wallet"
  | "home"
  | "user"
  | "upload"
  | "clock"
  | "settings"
  | "logout"
  | "chevron"
  | "school"
  | "plus"
  | "camera"
  | "shield"
  | "play"
  | "pause"
  | "trash"
  | "refresh"
  | "eye"
  | "list"
  | "grid"
  | "edit"
  | "alert";

function Icon({
  name,
  size = 20,
  className = "",
}: {
  name: IconName;
  size?: number;
  className?: string;
}) {
  const paths: Record<IconName, ReactNode> = {
    spark: (
      <>
        <path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3Z" />
        <path d="m5 15 .8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8L5 15Z" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14" />
        <path d="m13 6 6 6-6 6" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    file: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
        <path d="M14 2v6h6M8 13h8M8 17h5" />
      </>
    ),
    mic: (
      <>
        <rect x="9" y="2" width="6" height="12" rx="3" />
        <path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8" />
      </>
    ),
    chart: (
      <>
        <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
      </>
    ),
    wallet: (
      <>
        <path d="M20 8V6a2 2 0 0 0-2-2H6a3 3 0 0 0 0 6h14a1 1 0 0 1 1 1v7a2 2 0 0 1-2 2H6a3 3 0 0 1-3-3V7" />
        <path d="M21 13h-4a2 2 0 0 0 0 4h4" />
      </>
    ),
    home: (
      <>
        <path d="m3 11 9-8 9 8" />
        <path d="M5 10v10h14V10M9 20v-6h6v6" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="7" r="4" />
        <path d="M4 22a8 8 0 0 1 16 0" />
      </>
    ),
    upload: (
      <>
        <path d="M12 16V3M7 8l5-5 5 5" />
        <path d="M4 14v6h16v-6" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v6l4 2" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
      </>
    ),
    logout: (
      <>
        <path d="M10 17l5-5-5-5M15 12H3" />
        <path d="M14 3h6v18h-6" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    school: (
      <>
        <path d="m3 10 9-5 9 5-9 5-9-5Z" />
        <path d="M7 13v4c3 2 7 2 10 0v-4M21 10v6" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    camera: (
      <>
        <path d="M14 8h5a2 2 0 0 1 2 2v9H3v-9a2 2 0 0 1 2-2h5l1-2h2l1 2Z" />
        <circle cx="12" cy="13" r="3" />
      </>
    ),
    shield: (
      <>
        <path d="M12 2 4 5v6c0 5 3.4 9 8 11 4.6-2 8-6 8-11V5l-8-3Z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
    play: <path d="m8 5 11 7-11 7V5Z" />,
    pause: (
      <>
        <path d="M8 5v14M16 5v14" />
      </>
    ),
    trash: (
      <>
        <path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 7v5h-5" />
        <path d="M18 17a8 8 0 1 1 1.5-8" />
      </>
    ),
    eye: (
      <>
        <path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6-10-6-10-6Z" />
        <circle cx="12" cy="12" r="2.5" />
      </>
    ),
    list: (
      <>
        <path d="M8 6h13M8 12h13M8 18h13" />
        <circle cx="3" cy="6" r="1" />
        <circle cx="3" cy="12" r="1" />
        <circle cx="3" cy="18" r="1" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    edit: (
      <>
        <path d="m15 5 4 4L8 20H4v-4L15 5Z" />
        <path d="m13 7 4 4" />
      </>
    ),
    alert: (
      <>
        <path d="M12 3 2 21h20L12 3Z" />
        <path d="M12 9v5M12 18h.01" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

const Button = ({
  children,
  variant = "primary",
  icon,
  onClick,
  disabled = false,
  type = "button",
  className = "",
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  icon?: IconName;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) => (
  <button
    type={type}
    disabled={disabled}
    onClick={onClick}
    className={`btn btn-${variant} ${className}`}
  >
    {icon && <Icon name={icon} size={18} />}
    {children}
  </button>
);

const Badge = ({
  children,
  tone = "blue",
}: {
  children: ReactNode;
  tone?: "blue" | "green" | "amber" | "gray" | "purple" | "red";
}) => <span className={`badge badge-${tone}`}>{children}</span>;
const Card = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`card ${className}`}>{children}</div>
);
const Progress = ({
  value,
  color = "blue",
}: {
  value: number;
  color?: "blue" | "purple" | "green" | "amber";
}) => (
  <div className="progress">
    <span className={`progress-${color}`} style={{ width: `${value}%` }} />
  </div>
);

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <span className="brand-mark">
        <Icon name="spark" size={22} />
      </span>
      {!compact && <span>MAINSU</span>}
    </div>
  );
}

const appNav: { page: Page; label: string; icon: IconName }[] = [
  { page: "dashboard", label: "總覽", icon: "home" },
  { page: "profile", label: "申請校系", icon: "user" },
  { page: "upload", label: "備審資料", icon: "upload" },
  { page: "history", label: "面試紀錄", icon: "clock" },
  { page: "plans", label: "購買方案", icon: "wallet" },
  { page: "settings", label: "帳號設定", icon: "settings" },
];

function AppShell({
  page,
  go,
  children,
}: {
  page: Page;
  go: (page: Page) => void;
  children: ReactNode;
}) {
  const profile = useContext(AccountContext);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button onClick={() => go("dashboard")} className="logo-button">
          <Brand />
        </button>
        <nav className="side-nav">
          <p className="nav-label">學習空間</p>
          {appNav.map((item) => (
            <button
              key={item.page}
              className={page === item.page ? "active" : ""}
              onClick={() => go(item.page)}
            >
              <Icon name={item.icon} size={19} />
              <span>{item.label}</span>
              {page === item.page && <i />}
            </button>
          ))}
        </nav>
        <div className="side-user">
          <div>
            <strong>{profile?.name || "尚未設定姓名"}</strong>
            <small title={profile?.email}>{profile?.email || "尚未設定信箱"}</small>
          </div>
          <button onClick={() => go("logout")} aria-label="登出">
            <Icon name="logout" size={18} />
          </button>
        </div>
      </aside>
      <main className="app-main">
        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}

const pointPackages = [
  { points: 5, bonus: 1 },
  { points: 10, bonus: 3 },
];
const pricePerPoint = 30;
const currentPlan = { label: "付費版", tone: "purple" } as const;

function Landing({ go }: { go: (page: Page) => void }) {
  return (
    <div className="landing">
      <header className="landing-nav">
        <Brand />
        <nav>
          <a href="#features">產品特色</a>
          <a href="#flow">使用流程</a>
          <a href="#plans">方案比較</a>
        </nav>
        <div>
          <Button variant="ghost" onClick={() => go("login")}>
            登入
          </Button>
          <Button onClick={() => go("register")}>免費註冊</Button>
        </div>
      </header>
      <main>
        <section className="hero">
          <div className="hero-orb orb-one" />
          <div className="hero-orb orb-two" />
          <div className="hero-copy">
            <Badge tone="purple">
              <Icon name="spark" size={14} /> 專為大學個人申請打造
            </Badge>
            <h1>
              讓每一次回答，
              <br />
              都更接近<span>理想校系</span>
            </h1>
            <p>
              選擇申請校系，先用基本題庫熟悉大學個人申請二階面試。
              <br />
              個人化面試會依備審出題、根據作答追問，並在結束後提供改善建議。
            </p>
            <div className="hero-actions">
              <Button icon="arrow" onClick={() => go("register")}>
                開始模擬面試
              </Button>
              <Button
                variant="secondary"
                icon="play"
                onClick={() =>
                  document.querySelector("#flow")?.scrollIntoView({ behavior: "smooth" })
                }
              >
                了解如何運作
              </Button>
            </div>
            <div className="trust-row">
              <span>
                <Icon name="check" size={16} /> 免費版每日 3 次
              </span>
              <span>
                <Icon name="check" size={16} /> 免費版每場最多 15 分鐘
              </span>
              <span>
                <Icon name="chart" size={16} /> 面試後查看逐題回饋
              </span>
            </div>
          </div>
          <div className="hero-visual">
            <div className="mock-window">
              <div className="window-top">
                <span />
                <span />
                <span />
                <small>AI 模擬面試範例</small>
              </div>
              <div className="mock-body">
                <div className="mock-professor">
                  <div className="professor-avatar">
                    <span>AI</span>
                    <i />
                  </div>
                  <strong>AI 面試官</strong>
                  <small>
                    <span className="live-dot" /> 正在聆聽
                  </small>
                </div>
                <div className="mock-question">
                  <Badge tone="purple">主題 1 · 個人特質</Badge>
                  <h3>請分享一段最能展現你解決問題能力的經驗。</h3>
                  <div className="wave">
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((n) => (
                      <i key={n} style={{ height: `${8 + (n % 5) * 6}px` }} />
                    ))}
                  </div>
                  <div className="mock-timer">
                    <span>回答時間</span>
                    <strong>01:24</strong>
                    <Progress value={62} />
                  </div>
                </div>
              </div>
            </div>
            <div className="floating-card fc-one">
              <Icon name="file" />
              <div>
                <small>備審資料分析</small>
                <strong>依學習經歷出題</strong>
              </div>
            </div>
            <div className="floating-card fc-two">
              <span>86</span>
              <div>
                <small>評分範例</small>
                <strong>表現優良</strong>
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="features">
          <div className="section-heading">
            <Badge tone="blue">核心特色</Badge>
            <h2>把練習，變成真正有效的準備</h2>
            <p>個人化面試會結合申請校系與備審資料，從你的學習經歷出題。</p>
          </div>
          <div className="feature-grid">
            <Card>
              <span className="feature-icon blue">
                <Icon name="file" size={26} />
              </span>
              <h3>備審資料智慧分析</h3>
              <p>從備審 PDF 整理學習事件，保留原文與頁碼，供出題與一致性檢核使用。</p>
              <div className="mini-tags">
                <span>學習經歷</span>
                <span>個人特質</span>
                <span>專業能力</span>
              </div>
            </Card>
            <Card>
              <span className="feature-icon purple">
                <Icon name="mic" size={26} />
              </span>
              <h3>AI 動態追問</h3>
              <p>先判斷是否切題，再依個人特質、深度邏輯與經驗內容的缺口，一次生成一題追問。</p>
              <div className="branch-demo">
                <i>主問題</i>
                <span />
                <i>依回答追問</i>
              </div>
            </Card>
            <Card>
              <span className="feature-icon green">
                <Icon name="chart" size={26} />
              </span>
              <h3>個人化分析報告</h3>
              <p>提供作答優點、一致性檢核與改善建議。總分依完整度 45%、相關度 25%、一致性 20%、口語表達 10% 計算，面部行為另列分析。</p>
              <div className="score-bars">
                <span>
                  <i style={{ width: "86%" }} />
                </span>
                <span>
                  <i style={{ width: "74%" }} />
                </span>
                <span>
                  <i style={{ width: "91%" }} />
                </span>
              </div>
            </Card>
          </div>
        </section>

        <section className="section flow-section" id="flow">
          <div className="section-heading">
            <Badge tone="purple">四個步驟</Badge>
            <h2>從備審到面試，準備一次到位</h2>
          </div>
          <div className="steps">
            {[
              ["01", "登入並選擇校系", "登入後選擇要練習的學校與科系。", "school"],
              ["02", "選擇練習方式", "免費版使用基本題庫。個人化面試需提供學習歷程自述，可選附多元表現與課程學習成果。每檔限 PDF、5 MB 以內。", "upload"],
              ["03", "進行模擬面試", "從自我介紹開始，依序回答主問題和追問。", "mic"],
              ["04", "取得分析報告", "查看逐題切題提醒、作答優點及改善建議。", "chart"],
            ].map((s, i) => (
              <div className="step" key={s[0]}>
                <span className="step-number">{s[0]}</span>
                <div className="step-icon">
                  <Icon name={s[3] as IconName} />
                </div>
                <h3>{s[1]}</h3>
                <p>{s[2]}</p>
                {i < 3 && <Icon name="chevron" className="step-arrow" />}
              </div>
            ))}
          </div>
        </section>

        <section className="section plans-section" id="plans">
          <div className="section-heading">
            <Badge tone="blue">選擇方案</Badge>
            <h2>個人化面試與免費練習</h2>
          </div>
          <div className="pricing-grid">
            <Card className="price-card featured">
              <Badge tone="purple">付費版</Badge>
              <h3>個人化備審模擬面試</h3>
              <p>每場使用 1 點</p>
              <strong className="price">{pointPackages[0].points} 點 NT${pointPackages[0].points * pricePerPoint}</strong>
              <ul>
                {[
                  pointPackages.map(({ points, bonus }) => `買 ${points} 點送 ${bonus} 點，共 ${points + bonus} 點`).join("，"),
                  "每人最多上傳 6 組備審資料，可沿用既有資料",
                  "每場 10～20 分鐘，2～3 個大主題，最多 15 題（含追問）",
                  "每單元 1 題主問題、最多 2 次動態追問，自我介紹最多追問 1 次",
                  "檢核回答與備審的一致性，提供加權總分、A～E 等第與逐題改善建議",
                  "報告另列面部行為分析，總分只採計四項評分指標",
                ].map((x) => (
                  <li key={x}>
                    <Icon name="check" size={16} />
                    {x}
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="price-card">
              <Badge tone="gray">免費版</Badge>
              <h3>基礎模擬面試</h3>
              <p>適合第一次熟悉面試流程</p>
              <strong className="price">NT$ 0</strong>
              <Button variant="secondary" onClick={() => go("register")}>
                免費開始
              </Button>
              <ul>
                {[
                  "每帳號每日 3 次，每場最多 15 分鐘",
                  "固定自我介紹 1 題、校系常見題 2～3 題",
                  "依回答關鍵字追問，自我介紹最多 1 次，其他單元最多 2 次",
                  "使用麥克風作答，鏡頭關閉",
                  "逐題提供切題提醒、1 項優點與 1 項改善建議",
                  "使用系統題庫，報告省略加權總分與 A～E 等第",
                ].map(
                  (x) => (
                    <li key={x}>
                      <Icon name="check" size={16} />
                      {x}
                    </li>
                  ),
                )}
              </ul>
            </Card>
          </div>
        </section>
        <section className="cta">
          <span className="cta-glow" />
          <Badge tone="purple">準備好了嗎？</Badge>
          <h2>下一次面試，讓你更有把握</h2>
          <p>從一場免費模擬開始，練出屬於你的回答方式。</p>
          <Button icon="arrow" onClick={() => go("register")}>
            立即免費開始
          </Button>
        </section>
      </main>
      <footer>
        <Brand />
        <p>陪每一位學生，更有自信地說出自己的故事。</p>
        <div>
          <a>隱私權政策</a>
          <a>使用條款</a>
          <a>聯絡我們</a>
        </div>
        <small>© 2026 MAINSU. All rights reserved.</small>
      </footer>
    </div>
  );
}

function Auth({ mode, go, onAuthenticated }: {
  mode: "login" | "register";
  go: (p: Page) => void;
  onAuthenticated: (account: Account) => void;
}) {
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError("");
    try {
      const account = await workspaceRequest<Account>("/api/account/" + mode, "POST", Object.fromEntries(form));
      onAuthenticated(account);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <div className="auth-page">
      <button className="auth-logo" onClick={() => go("landing")}>
        <Brand />
      </button>
      <div className="auth-panel">
        <Card className="auth-card">
          <div className="auth-heading">
            <span className="auth-icon">
              <Icon name={mode === "login" ? "user" : "spark"} />
            </span>
            <h1>{mode === "login" ? "歡迎回來" : "開始你的面試準備"}</h1>
            <p>{mode === "login" ? "登入後繼續你的練習進度" : "建立免費帳號，只需要一分鐘"}</p>
          </div>
          <form onSubmit={submit}>
            {mode === "register" && (
              <label>
                姓名或暱稱
                <input name="name" placeholder="例如：陳語晴" required />
              </label>
            )}
            <label>
              電子郵件
              <input
                name="email"
                type="email"
                placeholder="name@example.com"
                className={error ? "error" : ""}
                onChange={() => setError("")}
                required
              />
              {error && (
                <span className="field-error">
                  <Icon name="alert" size={14} />
                  {error}
                </span>
              )}
            </label>
            <label>
              密碼
              <div className="password-field">
                <input
                  name="password"
                  type="password"
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  minLength={mode === "register" ? 8 : undefined}
                  maxLength={128}
                  placeholder={mode === "register" ? "至少 8 個字元" : "輸入密碼"}
                  required
                />
                <Icon name="eye" size={18} />
              </div>
            </label>
            {mode === "register" && (
              <label className="check-label">
                <input type="checkbox" required />
                我同意<a>使用條款</a>與<a>隱私權政策</a>
              </label>
            )}
            <Button type="submit" className="full" disabled={submitting}>
              {mode === "login" ? "登入" : "建立免費帳號"}
            </Button>
          </form>
          <div className="auth-switch">
            {mode === "login" ? "還沒有帳號？" : "已經有帳號？"}
            <button onClick={() => go(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "免費註冊" : "登入"}
            </button>
          </div>
        </Card>
        <div className="auth-note">
          <Icon name="shield" size={18} />
          <span>
            <strong>你的資料受到妥善保護</strong>
            <small>備審文件僅用於產生個人化練習內容</small>
          </span>
        </div>
      </div>
    </div>
  );
}

const PageTitle = ({
  eyebrow,
  title,
  desc,
  action,
}: {
  eyebrow?: string;
  title: string;
  desc?: string;
  action?: ReactNode;
}) => (
  <div className="page-title">
    <div>
      {eyebrow && <span>{eyebrow}</span>}
      <h1>{title}</h1>
      {desc && <p>{desc}</p>}
    </div>
    {action}
  </div>
);

function PointBalance() {
  const account = useContext(AccountContext);
  const [balance, setBalance] = useState(account?.pointBalance ?? null);
  useEffect(() => {
    if (!account) return;
    let active = true;
    void workspaceRequest<Account>("/api/account/me", "GET", undefined, account.id).then(profile => {
      if (active) setBalance(profile.pointBalance);
    }).catch(() => {});
    return () => { active = false; };
  }, [account?.id]);
  return (
    <span className="point-balance">
      剩餘點數 <strong aria-label={balance === null ? "目前無法取得點數餘額" : undefined}>{balance ?? "—"}</strong>
    </span>
  );
}

function PurchasePlans({ go }: { go: (page: Page) => void }) {
  return (
    <AppShell page="plans" go={go}>
      <PageTitle
        title="購買方案"
        desc="個人化備審模擬面試每場使用 1 點。"
        action={<Button variant="secondary" onClick={() => go("dashboard")}>返回總覽</Button>}
      />
      <div className="purchase-status">
        <span>目前方案</span>
        <Badge tone={currentPlan.tone}>{currentPlan.label}</Badge>
        <PointBalance />
      </div>
      <div className="pricing-grid purchase-plans">
        {pointPackages.map(({ points, bonus }) => (
          <Card className="price-card" key={points}>
            <Badge tone="purple">加贈 {bonus} 點</Badge>
            <h2>{points} 點方案</h2>
            <strong className="price">NT${points * pricePerPoint}</strong>
            <p>含贈點共 {points + bonus} 點，可練習 {points + bonus} 場個人化面試。</p>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}

type DashboardPortfolio = ApplicationTarget & { id:string; status:string; files:{id:string}[]; message?:string };
const AccountContext = createContext<Account | null>(null);

function useInterviewHistory() {
  const account = useContext(AccountContext);
  const [records, setRecords] = useState<Session[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    if (!account) return;
    const storage = workspaceStorage(account.id);
    const accountId = account.id;
    const pending = storage.read<Session[]>(pendingFreeReports) ?? [];
    let active = true;

    async function load() {
      const results = await Promise.allSettled(pending.map(report => saveFreeReport(report, accountId)));
      if (!active) return;
      const uploaded = new Set(pending.filter((_, index) => results[index].status === "fulfilled").map(item => item.id));
      if (uploaded.size) {
        const current = storage.read<Session[]>(pendingFreeReports) ?? [];
        storage.write(pendingFreeReports, current.filter(item => !uploaded.has(item.id)));
      }
      try {
        const reports = await workspaceRequest<Session[]>("/api/voice-interviews/history", "GET", undefined, accountId);
        const combined = new Map([...pending, ...reports].map(item => [item.id, item]));
        if (active) {
          setRecords([...combined.values()].sort((a, b) => (b.completedAt ?? "").localeCompare(a.completedAt ?? "")));
          setStatus("ready");
        }
      } catch {
        if (active) {
          setRecords(pending);
          setStatus("error");
        }
      }
    }

    void load();
    return () => { active = false; };
  }, [account?.id]);
  return { records, status };
}

function usePortfolioData() {
  const [portfolios,setPortfolios]=useState<DashboardPortfolio[]|null>(null);
  const [status,setStatus]=useState<"loading"|"ready"|"error">("loading");
  useEffect(()=>{
    const controller=new AbortController();
    async function refresh(){
      try {
        const response=await fetch("/api/portfolios",{signal:controller.signal});
        if(!response.ok)throw Error();
        const records=await response.json();
        if(!Array.isArray(records))throw Error();
        if(!controller.signal.aborted){setPortfolios(records);setStatus("ready");}
      }catch{if(!controller.signal.aborted){setPortfolios(null);setStatus("error");}}
    }
    void refresh(); const timer=window.setInterval(refresh,5000);
    return ()=>{controller.abort();clearInterval(timer);};
  },[]);
  return {portfolios,status};
}
const targetMatches=(a:ApplicationTarget,b:ApplicationTarget)=>[a.school,a.department].map(x=>x.normalize("NFKC").replace(/\s/g,"").replace(/臺/g,"台")).join("|") === [b.school,b.department].map(x=>x.normalize("NFKC").replace(/\s/g,"").replace(/臺/g,"台")).join("|");
function Dashboard({ go, schools, onResume }: { go: (p: Page) => void; schools: ApplicationTarget[]; onResume:(target:ApplicationTarget,id:string)=>void }) {
  const profile=useContext(AccountContext)!;
  const { records: reports } = useInterviewHistory();
  const freePracticeCount = reports.filter(report => report.id.startsWith("free-")).length;
  const {portfolios,status}=usePortfolioData();
  const now=new Date();
  const hour=now.getHours();
  const greeting=hour<12?"早安":hour<18?"午安":"晚安";
  const [selected,setSelected]=useState(0);
  const target=schools[selected]??schools[0];
  const targetReports=target?reports.filter(r=>r.target&&targetMatches(r.target,target)):[];
  const targetScores=targetReports.map(r=>scores(r as Session).total).filter((n):n is number=>n!==null);
  const best=targetScores.length?Math.max(...targetScores):null;
  const recent=[...reports].sort((a,b)=>(b.completedAt||"").localeCompare(a.completedAt||""))[0];
  const matching=target?portfolios?.filter(p=>targetMatches(p,target)):portfolios;
  const latestPortfolio=matching?.[0];
  const statusText:Record<string,string>={ready:"分析完成",queued:"等待分析",parsing:"解析中",analyzing:"分析中",failed:"分析失敗"};
  return (
    <AppShell page="dashboard" go={go}>
      <PageTitle eyebrow={now.toLocaleDateString("zh-TW",{year:"numeric",month:"long",day:"numeric",weekday:"long"})} title={profile.name?greeting+"，"+profile.name:greeting+"，歡迎使用 MAINSU"} desc="選擇你的申請校系，開始面試準備。" action={<Button icon="plus" onClick={()=>go("prepare")}>開始新的模擬面試</Button>}/>
      <ResumeInterviews accountId={profile.id} onResume={onResume} onFree={()=>go("freeInterview")}/>
      <Card className="dashboard-overview">
        <div className="dashboard-overview-header">
          <div className="dashboard-target">
            {target && (
              <span className="school-logo" aria-hidden="true">
                {schoolShortNames[target.school] ?? target.school.slice(0, 2)}
              </span>
            )}
            <div>
              <Badge tone="blue">申請目標</Badge>
              <h2>{target?.school ?? "尚未設定申請校系"}</h2>
              <p>{target?.department ?? "請先新增你的申請目標"}</p>
            </div>
          </div>
          <div className="dashboard-target-actions">
            {schools.length > 1 && (
              <label className="prep-target dashboard-target-switch">
                切換校系
                <select value={selected} onChange={event => setSelected(Number(event.target.value))}>
                  {schools.map((school, index) => (
                    <option value={index} key={index}>{school.school} · {school.department}</option>
                  ))}
                </select>
              </label>
            )}
            <button className="dashboard-manage-target" onClick={() => go("profile")}>
              管理申請校系 <Icon name="chevron" size={16} />
            </button>
          </div>
          <div className="dashboard-plan">
            <span>目前方案</span>
            <Badge tone={currentPlan.tone}>{currentPlan.label}</Badge>
            <PointBalance />
            <Button variant="secondary" className="dashboard-plans-link" onClick={() => go("plans")}>購買方案</Button>
          </div>
        </div>
        <dl className="dashboard-overview-stats">
          <div>
            <dt>本校系已完成</dt>
            <dd>{targetReports.length} 次</dd>
          </div>
          <div>
            <dt>本校系最佳成績</dt>
            <dd>{best === null ? "尚無評分" : Math.round(best * 10) / 10 + " 分"}</dd>
          </div>
          <div className="dashboard-all-practice">
            <dt>全部練習紀錄</dt>
            <dd>
              {reports.length} 場
              <small>個人化面試 {reports.length - freePracticeCount} 場 · 免費練習 {freePracticeCount} 場</small>
            </dd>
          </div>
        </dl>
      </Card>
      <div className="section-row"><h2>快速開始</h2><span>選擇適合今天的練習方式</span></div>
      <div className="quick-grid">
        <button className="quick-card premium" onClick={()=>go("prepare")}><span className="feature-icon purple"><Icon name="spark"/></span><Badge tone="purple">個人化</Badge><h3>完整 AI 模擬面試</h3><p>依備審資料產生個人化問題，包含動態追問與分析報告。</p><span className="quick-meta"><i><Icon name="clock" size={15}/>10～20 分鐘</i><strong>開始準備 <Icon name="arrow" size={16}/></strong></span></button>
        <button className="quick-card" onClick={()=>go("freeInterview")}><span className="feature-icon blue"><Icon name="mic"/></span><Badge tone="gray">免費版</Badge><h3>快速基礎練習</h3><p>使用內建練習題熟悉語音作答。</p><span className="quick-meta"><i><Icon name="clock" size={15}/>基礎練習</i><strong>開始練習 <Icon name="arrow" size={16}/></strong></span></button>
      </div>
      <div className="dashboard-bottom">
  <Card className="recent-interview-card"><div className="card-title"><div><h2>最近一次面試</h2><p>{recent?.completedAt?new Date(recent.completedAt).toLocaleDateString("zh-TW"):"尚無完成日期"}</p></div>{recent&&<button className="recent-link" onClick={()=>go("history")}>查看面試紀錄 <Icon name="chevron" size={15}/></button>}</div>{recent?(()=>{const marks=scores(recent as Session);const duration=recent.answers.reduce((n,a)=>n+a.duration,0);return <><div className="recent-interview-main">{!isTextSession(recent as Session)&&<div className="recent-interview-score"><strong>{marks.total===null?"—":Math.round(marks.total)}</strong><small>總分 / 100</small></div>}<div className="recent-interview-info"><h3>{recent.target?`${recent.target.school} · ${recent.target.department}`:"免費基礎練習"}</h3><p>{recent.answers.length} 題 · {Math.floor(duration/60)} 分 {Math.round(duration%60)} 秒</p><Badge tone={marks.total===null?"gray":"purple"}>{isTextSession(recent as Session)?"文字面試":marks.total===null?"評分尚未完成":`${grade(marks.total)} 等第`}</Badge></div></div><div className="recent-interview-metrics">{[{name:"完整度",value:marks.completeness},{name:"相關度",value:marks.relevance},{name:"一致性",value:marks.consistency},{name:"口語",value:marks.oral}].filter(m=>!isTextSession(recent as Session)||m.name!=="口語").map(m=><div key={m.name}><small>{m.name}</small><strong>{m.value===null?"—":Math.round(m.value)}</strong></div>)}</div></>})():<p>完成第一場模擬面試後，報告將顯示在這裡。</p>}</Card>
        <Card className="docs-card"><div className="card-title"><div><h2>備審資料</h2><p>{target?target.school+" · "+target.department:"全部校系"}</p></div><Badge tone={latestPortfolio?.status==="ready"?"green":"gray"}>{status==="loading"?"載入中":status==="error"?"無法連線":latestPortfolio?statusText[latestPortfolio.status]??latestPortfolio.status:"尚未上傳"}</Badge></div><div className="doc-count"><span><Icon name="file" size={24}/></span><div><strong>{status==="ready"?(matching??[]).reduce((n,p)=>n+p.files.length,0)+" 份文件":"—"}</strong></div></div><button onClick={()=>go("upload")}>管理備審資料 <Icon name="arrow" size={16}/></button></Card>
      </div>
    </AppShell>
  );
}
const schoolShortNames: Record<string, string> = {
  國立臺灣大學: "臺大",
  國立政治大學: "政大",
  國立清華大學: "清大",
  輔仁大學: "輔大",
};

function Profile({go, schools, setSchools}:{go:(p:Page)=>void;schools:ApplicationTarget[];setSchools:(targets:ApplicationTarget[])=>Promise<void>}) {
  const [adding,setAdding]=useState(false);
  const [draft,setDraft]=useState<ApplicationTarget>({school:"",department:""});
  const duplicate=schools.some(s=>targetMatches(s,draft));
  const ready=!!draft.school&&!!draft.department&&schoolCatalog[draft.school]?.includes(draft.department)&&!duplicate;
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  async function persist(targets: ApplicationTarget[]) {
    if (saving) return false;
    setSaving(true);
    setSaveError("");
    try {
      await setSchools(targets);
      return true;
    } catch (error) {
      setSaveError((error as Error).message);
      return false;
    } finally {
      setSaving(false);
    }
  }
  function move(index: number, step: number) {
    const next = index + step;
    if (next < 0 || next >= schools.length) return;
    const ordered = [...schools];
    [ordered[index], ordered[next]] = [ordered[next], ordered[index]];
    void persist(ordered);
  }
  function cancel(){setAdding(false);setDraft({school:"",department:""});}
  async function save() {
    if (!ready || schools.length >= 6) return;
    if (await persist([...schools, draft])) cancel();
  }
  return <AppShell page="profile" go={go}>
    <PageTitle eyebrow="申請校系" title="建立你的申請目標" desc="最多可建立 6 組申請校系，儲存後不可變更。"/>
    <Card className="form-card">
      <div className="form-section">
        <div className="form-section-title"><span>1</span><div><h2>申請學校與科系</h2><p>依你的申請優先順序排列；第一志願會顯示在總覽，使用箭頭調整順序。</p></div></div>
        {saveError && <p role="alert">{saveError}</p>}
        <div className="school-list">{schools.map((s,i)=><div className="school-item saved-school-item" key={`${s.school}|${s.department}|${i}`}>
          <span className="item-index" title={`第 ${i+1} 志願`}>{i+1}</span>
          <div className="saved-school-field"><small>申請學校</small><strong>{s.school}</strong></div>
          <div className="saved-school-field"><small>申請科系</small><strong>{s.department}</strong></div>
          <div className="school-order-actions"><button type="button" aria-label={`將第 ${i+1} 志願上移`} title="上移" disabled={saving || i===0} onClick={()=>move(i,-1)}>↑</button><button type="button" aria-label={`將第 ${i+1} 志願下移`} title="下移" disabled={saving || i===schools.length-1} onClick={()=>move(i,1)}>↓</button></div>
        </div>)}</div>
        {adding?<div className="school-add-panel"><div><h3>新增申請校系</h3><p>請確認學校與科系，儲存後不可修改。</p></div><div className="school-add-fields">
          <SearchSelect label="學校" kind="school" options={schoolNames} value={draft.school} onSelect={school=>setDraft({school,department:""})}/>
          <SearchSelect key={draft.school} label="科系" kind="department" options={schoolCatalog[draft.school]??[]} value={draft.department} disabled={!draft.school} onSelect={department=>setDraft(v=>({...v,department}))}/>
        </div>{duplicate&&draft.department&&<p role="alert" className="field-error">此校系已新增。</p>}
        <div className="form-actions"><Button variant="secondary" onClick={cancel}>取消</Button><Button disabled={saving || !ready} onClick={save}>確認儲存</Button></div></div>:<button className="add-school" disabled={schools.length>=6} onClick={()=>{setDraft({school:"",department:""});setAdding(true);}}><Icon name="plus" size={18}/>新增申請校系 <small>{schools.length} / 6</small></button>}
      </div>
      <div className="form-actions"><Button variant="secondary" onClick={()=>go("dashboard")}>返回總覽</Button><Button disabled={adding||!schools.length} onClick={()=>go("upload")}>管理備審資料 <Icon name="arrow" size={17}/></Button></div>
    </Card>
  </AppShell>;
}

function Upload({ go, schools }: { go: (p: Page) => void; schools: ApplicationTarget[] }) {
  return (
    <AppShell page="upload" go={go}>
      <PageTitle eyebrow="備審資料" title="校系備審資料" />
      <PortfolioManager applicationTargets={schools} />
    </AppShell>
  );
}

const events = [
  {
    title: "校園碳排視覺化系統",
    type: "自主學習",
    summary: "自主研究校園用電資料，與同學協作建立碳排視覺化網站。",
    role: "專案發起人、前端開發",
    action: "訪談總務處、整理三年用電資料，設計互動儀表板。",
    result: "獲校內自主學習成果展優選",
    abilities: ["資料分析", "問題解決", "團隊協作"],
    relation: "與資訊管理的資料應用、系統分析能力高度相關",
    pages: "自主學習成果，第 3～6 頁",
    confirm: "團隊人數與個人負責比例",
  },
  {
    title: "學生會活動部幹部經驗",
    type: "多元表現",
    summary: "規劃跨校社團博覽會，協調 18 個社團與校方行政單位。",
    role: "活動部副部長",
    action: "建立工作分配表與風險清單，處理場地臨時異動。",
    result: "活動共 620 人參與，滿意度 92%",
    abilities: ["溝通協調", "領導力", "應變能力"],
    relation: "展現組織管理與跨部門協作潛力",
    pages: "多元表現，第 8～10 頁",
    confirm: "滿意度問卷的有效樣本數",
  },
];

function Analysis({ go }: { go: (p: Page) => void }) {
  const [selected, setSelected] = useState(0);
  return (
    <AppShell page="upload" go={go}>
      <PageTitle
        eyebrow="備審分析"
        title="從經歷中，看見你的亮點"
        desc="已將 8 份文件整理為 12 個學習事件。請確認資訊是否正確。"
        action={
          <div className="title-actions">
            <Badge tone="green">
              <Icon name="check" size={14} />
              模擬分析完成
            </Badge>
            <Button variant="secondary" icon="refresh">
              重新分析
            </Button>
          </div>
        }
      />
      <div className="analysis-summary">
        <div>
          <span className="analysis-score">
            <strong>12</strong>
            <small>學習事件</small>
          </span>
          <p>
            分析涵蓋 <b>4</b> 類經歷、辨識 <b>9</b> 項能力，其中有 <b>2</b> 項資訊待你確認。
          </p>
        </div>
        <div className="legend">
          <span>
            <i className="purple-dot" />
            自主學習 3
          </span>
          <span>
            <i className="blue-dot" />
            多元表現 5
          </span>
          <span>
            <i className="green-dot" />
            課程成果 4
          </span>
        </div>
      </div>
      <div className="analysis-layout">
        <Card className="event-list">
          <div className="event-filter">
            <button className="active">全部 12</button>
            <button>待確認 2</button>
          </div>
          {events.map((e, i) => (
            <button
              className={selected === i ? "active" : ""}
              onClick={() => setSelected(i)}
              key={e.title}
            >
              <div>
                <Badge tone={i === 0 ? "purple" : "blue"}>{e.type}</Badge>
                <small>{i === 0 ? "事件 01" : "事件 02"}</small>
              </div>
              <strong>{e.title}</strong>
              <p>{e.summary}</p>
              <span>
                {e.abilities.slice(0, 2).map((a) => (
                  <i key={a}>{a}</i>
                ))}
              </span>
            </button>
          ))}
          <button className="faded-event">
            <strong>數學建模競賽</strong>
            <p>課程成果 · 展現邏輯推理能力</p>
          </button>
        </Card>
        <Card className="event-detail">
          <div className="detail-head">
            <div>
              <Badge tone={selected === 0 ? "purple" : "blue"}>{events[selected].type}</Badge>
              <h2>{events[selected].title}</h2>
              <p>來源：{events[selected].pages}</p>
            </div>
            <Button variant="secondary" icon="edit">
              編輯內容
            </Button>
          </div>
          <div className="detail-section">
            <h3>事件摘要</h3>
            <p>{events[selected].summary}</p>
          </div>
          <div className="detail-two">
            <div>
              <h3>角色與任務</h3>
              <p>{events[selected].role}</p>
            </div>
            <div>
              <h3>行動及成果</h3>
              <p>
                {events[selected].action}
                <br />
                <strong>{events[selected].result}</strong>
              </p>
            </div>
          </div>
          <div className="detail-section">
            <h3>展現能力</h3>
            <div className="ability-list">
              {events[selected].abilities.map((a) => (
                <span key={a}>
                  <Icon name="check" size={14} />
                  {a}
                </span>
              ))}
            </div>
          </div>
          <div className="relation-box">
            <span>
              <Icon name="school" size={20} />
            </span>
            <div>
              <h3>申請科系關聯</h3>
              <p>{events[selected].relation}</p>
            </div>
            <Badge tone="green">高度相關</Badge>
          </div>
          <div className="confirm-box">
            <Icon name="alert" size={20} />
            <div>
              <h3>待確認資訊</h3>
              <p>{events[selected].confirm}</p>
            </div>
            <Button variant="secondary">前往確認</Button>
          </div>
          <div className="source-box">
            <Icon name="file" size={18} />
            <span>
              <small>資料來源頁碼</small>
              <strong>{events[selected].pages}</strong>
            </span>
            <button>查看原始文件</button>
          </div>
        </Card>
      </div>
      <div className="bottom-cta">
        <div>
          <Icon name="check" />
          <span>
            <strong>確認完分析內容了嗎？</strong>
            <small>這些事件會作為個人化問題與一致性分析依據。</small>
          </span>
        </div>
        <Button onClick={() => go("prepare")}>
          前往面試準備 <Icon name="arrow" size={17} />
        </Button>
      </div>
    </AppShell>
  );
}

function Prepare({
  go, schools, onStart,
}: {
  go: (p: Page) => void;
  schools: ApplicationTarget[];
  onStart: (target: ApplicationTarget, mode: "voice" | "text", noPortfolio?:boolean) => void;
}) {
  const [selection, setSelection] = useState("");
  const [mic, setMic] = useState<"idle" | "testing" | "passed">("idle");
  const [answerMode,setAnswerMode]=useState<"voice"|"text"|null>(null);
  const [micMessage, setMicMessage] = useState("");
  const test = useRef<VoiceInput | null>(null);
  const meter = useRef<Awaited<ReturnType<typeof monitorAudio>> | null>(null);
  const [micLevel, setMicLevel] = useState(0);
  const target = selection === "" ? undefined : schools[Number(selection)];
  const {portfolios,status}=usePortfolioData();
  const portfolio=target?portfolios?.find(p=>targetMatches(p,target)):undefined;
  const [missingPrompt,setMissingPrompt]=useState(false);
  const [retryState,setRetryState]=useState("");
  const [retryStarted,setRetryStarted]=useState(false);
  useEffect(()=>{setMissingPrompt(false);setRetryState("");setRetryStarted(false);},[selection]);
  useEffect(()=>{if(portfolio?.status!=="failed")setRetryStarted(false);},[portfolio?.status]);
  async function retryPortfolio(){
    if(!portfolio)return;
    setRetryStarted(true);setRetryState("已送出重新分析，請等待完成。");
    try{const res=await fetch(`/api/portfolios/${portfolio.id}/retry`,{method:"POST"});if(!res.ok)throw Error();}catch{setRetryStarted(false);setRetryState("重新分析失敗，請再試一次。");}finally{window.setTimeout(()=>setRetryStarted(false),6000);}
  }
  const ready = answerMode === "text" || (answerMode === "voice" && mic === "passed");
  useEffect(() => () => { test.current?.cancel(); meter.current?.stop(); }, []);
  useEffect(() => {
    if (mic !== "testing") return;
    const timeout = window.setTimeout(() => test.current?.stop(), 12000);
    return () => window.clearTimeout(timeout);
  }, [mic]);

  async function testMicrophone() {
    setMicMessage("請允許麥克風權限，然後說一句話。");
    setMic("testing");
    try {
      meter.current = await monitorAudio(setMicLevel);
      test.current = startVoiceInput({
        continuous: false,
        onStart: () => setMicMessage("請說一句話，例如「我準備好面試了」。"),
        onText: () => {},
        onEnd(text, error) {
          test.current = null; meter.current?.stop(); meter.current = null; setMic(text ? "passed" : "idle");
          setMicMessage(text ? `已辨識到：${text}` : error ?? "沒有辨識到語音，請再試一次。");
        },
      });
    } catch (error) { meter.current?.stop(); meter.current = null; setMic("idle");
      setMicMessage(error instanceof Error ? error.message : "麥克風測試失敗。");
    }
  }
  return (
    <AppShell page="dashboard" go={go}>
      <PageTitle
        eyebrow="面試前準備"
        title="確認設定，準備開始"
        desc="選擇本次面試校系與作答方式，再開始面試。"
      />
      <div className="prep-steps">
        <span className={target ? "done" : "active"}>
          <i>{target ? <Icon name="check" size={15} /> : "1"}</i>
          選擇校系
        </span>
        <b />
        <span className={target ? "active" : undefined}>
          <i>2</i>確認作答方式
        </span>
        <b />
        <span>
          <i>3</i>設備測試
        </span>
        <b />
        <span>
          <i>4</i>開始面試
        </span>
      </div>
      <div className="prep-layout">
        <div className="prep-main">
          <Card>
            <div className="card-title">
              <div>
                <Badge tone="purple">完整版面試</Badge>
                <h2>{target ? `${target.school} · ${target.department}` : "選擇本次面試校系"}</h2>
                <p>個人化動態追問模式</p>
              </div>
              <button className="text-button" onClick={() => go("profile")}>
                管理申請校系
              </button>
            </div>
            {schools.length ? (
              <label className="prep-target">
                本次面試校系
                <select value={selection} onChange={(event) => setSelection(event.target.value)}>
                  <option value="" disabled>請選擇申請校系</option>
                  {schools.map(({ school, department }, index) => (
                    <option key={index} value={index}>{school} · {department}</option>
                  ))}
                </select>
              </label>
            ) : <p className="prep-target">請先到「申請校系」新增校系。</p>}
            {target&&status==="ready"&&portfolio&&portfolio.status!=="ready"&&<div className="rules-note" role="alert">{portfolio.status==="failed"&&!retryStarted?<><p>此校系的備審分析失敗，請重新分析後再開始模擬面試。</p><Button onClick={()=>void retryPortfolio()}>重新分析</Button></>:<p>此校系的備審資料正在分析中，請待分析完成後再開始模擬面試。</p>}{retryState&&<p>{retryState}</p>}<Button variant="secondary" onClick={()=>go("upload")}>返回備審管理</Button></div>}
            {target&&status==="ready"&&!portfolio&&<div className="rules-note">此校系尚未上傳備審資料。<Button variant="secondary" onClick={()=>go("upload")}>前往上傳</Button></div>}
            <div className="rule-grid">
              {[
                ["clock", "預估時間", "約 10～20 分鐘"],
                ["list", "面試主題", "2～3 個主要主題"],
                ["mic", "題目規則", "每個主題 1 題主問題，最多追問 2 次"],
                ["shield", "全場上限", "最多 15 題，含主問題與追問"],
              ].map((r) => (
                <div key={r[1]}>
                  <span>
                    <Icon name={r[0] as IconName} />
                  </span>
                  <small>{r[1]}</small>
                  <strong>{r[2]}</strong>
                </div>
              ))}
            </div>
            <div className="rules-note">
              <h3>作答時間提醒</h3>
              <ul>
                <li>
                  自我介紹提供 <strong>90 秒</strong>作答時間
                </li>
                <li>
                  其他單題回答最多 <strong>2 分鐘</strong>
                </li>
                <li>系統會依回答完整度、相關度、一致性及時間限制決定後續流程</li>
              </ul>
            </div>
          </Card>
          <Card>
            <div className="card-title">
              <div>
                <h2>選擇作答方式</h2>
                <p>請在開始面試前選定本場作答方式。</p>
              </div>
            </div>
            <div className="answer-mode-options" role="group" aria-label="作答方式">
              <button type="button" aria-pressed={answerMode==="voice"} onClick={()=>setAnswerMode("voice")}><Icon name="mic"/><strong>語音面試</strong><small>語音作答，提供整體評估與口語分析。</small></button>
              <button type="button" aria-pressed={answerMode==="text"} onClick={()=>{test.current?.cancel();meter.current?.stop();meter.current=null;test.current=null;setMic("idle");setMicMessage("");setAnswerMode("text");}}><Icon name="file"/><strong>文字面試</strong><small>文字作答，提供內容分析與改善建議。</small></button>
            </div>
            {answerMode==="text"&&<div className="rules-note" role="alert"><strong>文字面試評分說明</strong><p>本場面試不提供總分、等第、口語評分及面部行為分析；仍提供完整度、相關度、一致性（有適用備審證據時）與改善建議。</p></div>}
            {answerMode==="voice"&&<div className="device-row">
              <span className={`device-icon ${mic==="passed"?"success":""}`}><Icon name="mic"/></span>
              <div><strong>麥克風測試</strong><p role="status">{micMessage||"尚未進行測試"}</p><meter min={0} max={100} value={micLevel}/></div>
              <Button variant={mic==="passed"?"secondary":"primary"} onClick={testMicrophone} disabled={mic==="testing"}>{mic==="testing"?"測試中":mic==="passed"?"重新測試":"測試麥克風"}</Button>
            </div>}
          </Card>
        </div>
        <Card className="ready-card">
          <span className="ready-illustration">
            <Icon name="mic" size={32} />
            <i />
          </span>
          <h2>準備好了嗎？</h2>
          <p>開始前，請再次確認：</p>
          <ul>
            <li>
              <Icon name="check" size={15} />
              環境安靜、不受打擾
            </li>
            <li>
              <Icon name="check" size={15} />
              網路連線穩定
            </li>
            <li>
              <Icon name="check" size={15} />
              裝置電量充足
            </li>
          </ul>
          <Button className="full" disabled={!target || !ready || status!=="ready" || (!!portfolio&&portfolio.status!=="ready")} onClick={() => {
            if (target && ready) {if(!portfolio)setMissingPrompt(true);else onStart(target, answerMode!);}
          }} icon="play">
            開始模擬面試
          </Button>
          {missingPrompt&&target&&!portfolio&&<div role="alert" className="rules-note"><p>此校系尚未上傳備審資料，若繼續面試，本次只會依自我介紹及校系常見題庫提問，不包含備審相關問題。</p><Button variant="secondary" onClick={()=>go("upload")}>前往上傳</Button><Button onClick={()=>onStart(target,answerMode!,true)}>繼續面試</Button><Button variant="secondary" onClick={()=>setMissingPrompt(false)}>取消</Button></div>}
          {status==="error"&&<p role="alert">無法確認備審狀態，請等待重新連線。</p>}
          {!target ? <small>請先選擇面試校系</small> : !ready && <small>請先選擇作答方式；語音面試須完成麥克風測試</small>}
          <p className="simulation-note">語音僅用於模擬及分析；原始音訊不永久保存。</p>
        </Card>
      </div>
    </AppShell>
  );
}

type InterviewAnswer = { question: string; text: string; timedOut: boolean };

function Interview({ go, free = false, target, onFinish }: {
  go: (p: Page) => void;
  free?: boolean;
  target?: ApplicationTarget;
  onFinish: (answers: InterviewAnswer[]) => void;
}) {
  const questions = [
    { title: "自我介紹", prompt: "請簡短介紹你自己，並分享一項最能代表你的特質。" },
    { title: "個人經驗", prompt: free
      ? "請分享一次你如何解決問題的經驗。"
      : "面對資料格式不一致的問題，你如何找出原因並完成整合？" },
    { title: "申請動機", prompt: "你為什麼想申請" + (target?.department ?? "這個科系") + "？" },
  ];
  const [answers, setAnswers] = useState<InterviewAnswer[]>([]);
  const [draft, setDraft] = useState("");
  const [preview, setPreview] = useState("");
  const [message, setMessage] = useState("");
  const [captureState, setCaptureState] = useState<"idle" | "starting" | "listening" | "stopping">("idle");
  const [deadline, setDeadline] = useState<number | null>(null);
  const [seconds, setSeconds] = useState(free ? 120 : 90);
  const capture = useRef<VoiceInput | null>(null);
  const question = questions[answers.length];
  const limit = !free && answers.length === 0 ? 90 : 120;
  const timedOut = deadline !== null && seconds === 0;
  const capturing = captureState !== "idle";
  const canSubmit = deadline !== null && !capturing && (draft.trim() !== "" || timedOut);
  useEffect(() => () => capture.current?.cancel(), []);

  useEffect(() => {
    if (deadline === null) return;
    const timer = window.setInterval(() => {
      setSeconds(Math.max(0, Math.ceil((deadline - performance.now()) / 1000)));
    }, 250);
    return () => window.clearInterval(timer);
  }, [deadline]);

  useEffect(() => {
    if (!timedOut || !capture.current) return;
    setCaptureState("stopping");
    capture.current.stop();
  }, [timedOut]);

  function startTimer() {
    if (deadline === null) {
      setSeconds(limit);
      setDeadline(performance.now() + limit * 1000);
    }
  }

  function speak() {
    if (capture.current || timedOut) return;
    setMessage("");
    setCaptureState("starting");
    const existing = draft.trimEnd();
    const join = (text: string) => [existing, text].filter(Boolean).join(" ");
    try {
      capture.current = startVoiceInput({
        continuous: true,
        onStart: () => {
          startTimer();
          setCaptureState("listening");
        },
        onText: (text) => setPreview(join(text)),
        onEnd(text, error) {
          capture.current = null;
          setCaptureState("idle");
          setPreview("");
          setDraft(join(text));
          setMessage(error ?? (text ? "請確認逐字稿，再送出回答。" : "沒有辨識到語音，可以再試一次或用文字作答。"));
        },
      });
    } catch (error) {
      setCaptureState("idle");
      setMessage(error instanceof Error ? error.message : "無法啟動語音辨識。");
    }
  }

  function submit() {
    if (!canSubmit) return;
    const updated = [...answers, { question: question.prompt, text: draft.trim(), timedOut }];
    if (updated.length === questions.length) {
      onFinish(updated);
      return;
    }
    setAnswers(updated);
    setDraft("");
    setMessage("");
    setDeadline(null);
    setSeconds(120);
  }

  return (
    <div className="interview-page">
      <header className="interview-header">
        <Brand />
        <div className="interview-title">
          <Badge tone={free ? "gray" : "purple"}>{free ? "免費版" : "完整版"}</Badge>
          <strong>{target ? target.school + " · " + target.department : "基礎模擬面試"}</strong>
          <span>固定練習題</span>
        </div>
        <button disabled={capturing} onClick={() => onFinish(answers)}>結束面試</button>
      </header>
      <div className="interview-grid">
        <aside className="interviewer-panel">
          <div className="ai-orb">
            <span><Icon name="spark" size={30} /></span><i /><i /><i />
          </div>
          <div className="ai-name"><strong>模擬面試</strong></div>
          <div className="speech-bubble">
            <small>目前提問</small>
            <p>{question.prompt}</p>
          </div>
        </aside>
        <main className="answer-panel">
          <div className="question-card">
            <div>
              <Badge tone="purple">第 {answers.length + 1} 題 · {question.title}</Badge>
              <span className="question-time"><Icon name="clock" size={15} /> 最多 {limit} 秒</span>
            </div>
            <h1>{question.prompt}</h1>
          </div>
          <div className={"record-area" + (captureState === "listening" ? " recording" : "")}>
            <div className="timer-ring"
              style={{ "--progress": (seconds / limit) * 360 + "deg" } as React.CSSProperties}>
              <div>
                <strong>{String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}</strong>
                <small>{deadline === null ? "作答上限" : "剩餘時間"}</small>
              </div>
            </div>
            {capturing ? (
              <Button variant="danger" icon="pause" disabled={captureState === "stopping"} onClick={() => {
                if (captureState === "starting") {
                  capture.current?.cancel();
                  capture.current = null;
                  setCaptureState("idle");
                  return;
                }
                setCaptureState("stopping");
                capture.current?.stop();
              }}>
                {captureState === "starting" ? "取消連線" : captureState === "stopping" ? "整理辨識文字中" : "停止辨識"}
              </Button>
            ) : !timedOut && (
              <div className="voice-actions">
                <Button icon="mic" onClick={speak}>{draft ? "繼續語音作答" : "開始語音作答"}</Button>
                {deadline === null && <Button variant="secondary" onClick={startTimer}>使用文字作答</Button>}
              </div>
            )}
          </div>
          <div className="transcript">
            <div>
              <label htmlFor="interview-answer">回答逐字稿</label>
              {captureState === "listening" && <Badge tone="red">即時辨識中</Badge>}
            </div>
            <textarea id="interview-answer" rows={5} value={capturing ? preview || draft : draft}
              readOnly={capturing} disabled={deadline === null && !capturing}
              placeholder="開始作答後，這裡會顯示辨識文字，也可直接輸入或修正。"
              onChange={(event) => { setDraft(event.target.value); setMessage(""); }} />
            {timedOut && <p role="status">作答時間已到。你可以確認逐字稿後送出。</p>}
            {message && <p role="status">{message}</p>}
            <div className="voice-actions">
              <Button onClick={submit} disabled={!canSubmit}>
                {timedOut && !draft.trim() ? "略過本題" : "送出回答"}
              </Button>
            </div>
          </div>
        </main>
        <aside className="progress-panel">
          <div className="topic-block">
            <div><strong>面試進度</strong><span>{answers.length + 1} / {questions.length}</span></div>
            <Progress value={(answers.length / questions.length) * 100} color="purple" />
          </div>
          <div className="topics">
            <h3>題目</h3>
            {questions.map(({ title }, index) => (
              <div key={title} className={index < answers.length ? "done" : index === answers.length ? "current" : ""}>
                <span>{index < answers.length ? <Icon name="check" size={14} /> : index + 1}</span>
                <p>{title}</p>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

const metricData = [
  ["回答完整度", "45%", "88", "blue"],
  ["回答相關度", "25%", "82", "purple"],
  ["備審一致性", "20%", "91", "green"],
  ["口語表達", "10%", "78", "amber"],
];

function Report({go,free=false,session:initial}:{go:(p:Page)=>void;free?:boolean;session?:Session}) {
  const [session,setSession]=useState(initial);
  const [reviewState,setReviewState]=useState<"idle"|"loading"|"failed">("idle");
  const [reviewError,setReviewError]=useState("");
  async function review(){if(!session||free)return;setReviewState("loading");setReviewError("");const url=`/api/voice-interviews/${session.id}`;const save=(result:Session)=>{const updated={...result,completedAt:session.completedAt??result.completedAt,dateEstimated:session.completedAt?session.dateEstimated:result.dateEstimated};setSession(updated);return updated;};try{const existing=await fetch(url);if(existing.ok){const current=save(await existing.json());if(current.reportReview?.complete){setReviewState("idle");return;}}const res=await fetch(`${url}/review`,{method:"POST"});if(!res.ok){const data=await res.json().catch(()=>({}));throw Error(data.error||"AI 評分暫時失敗");}save(await res.json());setReviewState("idle");}catch(e){setReviewError(e instanceof Error?e.message:"AI 評分暫時失敗");try{const partial=await fetch(url);if(partial.ok)save(await partial.json());}catch{}setReviewState("failed");}}
  useEffect(()=>{if(session?.finished&&!free&&!session.reportReview?.complete)void review();},[session?.id]);
  useEffect(()=>{
    if(!initial?.finished||free||!initial.reportReview?.complete||initial.answers.some(a=>a.analysisScores))return;
    const controller=new AbortController();
    void fetch(`/api/voice-interviews/${initial.id}`,{signal:controller.signal}).then(async res=>{
      if(!res.ok)return;const data:Session=await res.json();
      if(controller.signal.aborted||!data.answers.some(a=>a.analysisScores))return;
      const updated={...data,completedAt:initial.completedAt??data.completedAt,dateEstimated:initial.completedAt?initial.dateEstimated:data.dateEstimated,reportReview:data.reportReview??initial.reportReview};
      setSession(updated);

    }).catch(()=>{});
    return()=>controller.abort();
  },[initial?.id,free]);
  const textMode=!!session&&isTextSession(session);
  const marks=session?scores(session):{total:null,completeness:null,relevance:null,consistency:null,oral:null};
  const display=(v:number|null)=>v===null?"未評估":Math.round(v*10)/10;
  const reviewRows=session?.reportReview?.questions??[];
  const answers=session?.answers??[];const topics=session?.summary?.topics??[];
  const duration=session?.summary?.elapsed_seconds??answers.reduce((n,a)=>n+a.duration,0);
  const fmt=(seconds:number)=>`${String(Math.floor(seconds/60)).padStart(2,"0")}:${String(Math.floor(seconds%60)).padStart(2,"0")}`;
  const avg=(values:(number|null|undefined)[])=>{const v=values.filter((x):x is number=>typeof x==="number"&&Number.isFinite(x));return v.length?Math.round(v.reduce((a,b)=>a+b,0)/v.length):null;};
  const dimensions=[{key:"trait",label:"個人特質完整度"},{key:"depth",label:"深度邏輯完整度"},{key:"exp",label:"經驗內容完整度"}];
  const dimensionScores=dimensions.map(d=>({...d,score:avg(topics.map(t=>t.scores?.[d.key]))}));
  const completeness=avg(dimensionScores.map(d=>d.score));
  const relevance=avg(topics.map(t=>typeof t.relevance_score==="number"?t.relevance_score*100:null));
  const speeches=answers.filter(a=>a.metrics?.sufficient).map(a=>a.metrics!);
  const rates=avg(speeches.map(m=>m.rate));const pauses=speeches.reduce((n,m)=>n+m.pauses.length,0);
  const fillers:Record<string,number>={};speeches.forEach(m=>Object.entries(m.fillers).forEach(([w,n])=>{fillers[w]=(fillers[w]||0)+n;}));
  const issues=topics.flatMap(t=>t.consistency_issues??[]);const timeout=answers.filter(a=>a.timedOut).length;
  const gapNames:Record<string,string>={trait:"個人特質",depth:"深度邏輯",exp:"經驗內容"};
  const gapSuggestions:Record<string,string>={trait:"補充你展現的能力或態度，並舉出具體行為。",depth:"說明你為什麼做出這個決定、比較過哪些方案及背後理由。",exp:"補充情境、你的具體行動、成果與反思。"};
  const gaps=[...new Set(topics.flatMap(t=>t.gaps??[]))];
  const reportContext=session?.target?`${session.target.school} · ${session.target.department}`:free?"免費基礎練習":"面試紀錄";
  if(!session)return <AppShell page="history" go={go}><PageTitle eyebrow="面試分析報告" title="尚未選擇面試紀錄"/><Button onClick={()=>go("history")}>查看面試紀錄</Button></AppShell>;
  return <AppShell page="history" go={go}>
    <PageTitle eyebrow="面試分析報告" title={free?"基礎練習完成":"你的面試分析報告"} desc={reportContext+(session.completedAt?` · ${new Date(session.completedAt).toLocaleDateString("zh-TW")}`:"")} action={<div className="title-actions"><Button variant="secondary" onClick={()=>go("history")}>返回面試紀錄</Button><Button onClick={()=>go(free?"freeInterview":"prepare")} icon="plus">開始新面試</Button></div>}/>
    <div className="report-summary"><Card className="score-card">{!textMode&&<div className="big-score" style={{background:`conic-gradient(#d85b92 ${marks.total??0}%, #f2e9f0 0)`}}><span><strong>{free?"—":marks.total===null?"—":Math.round(marks.total*10)/10}</strong>{!free&&<small>/ 100</small>}</span></div>}<div><Badge tone="green">{session.finished?"已完成":"未完成"}</Badge><h2>本次面試結果</h2><p>{session.summary?.termination_reason||"本次作答紀錄已保存。"} {!free&&"練習評分僅供參考。"}</p></div></Card><div className="stat-cards"><Card><Icon name="clock"/><span><small>作答時間</small><strong>{fmt(duration)}</strong></span></Card><Card><Icon name="mic"/><span><small>作答題數</small><strong>{answers.length} 題</strong></span></Card>{!textMode&&<Card><Icon name="chart"/><span><small>面試等第</small><strong>{free?"不適用":grade(marks.total)}</strong></span></Card>}</div></div>
    {!free&&<><Card className="metrics-card"><div className="card-title"><div><h2>{textMode?"回答內容分析":"四大評分指標"}</h2></div>{!textMode&&<Badge tone="gray">{marks.total===null?"等待評分":`加權總分 ${display(marks.total)}`}</Badge>}</div><div className="metric-detail">{[{label:"回答完整度",weight:"45%",value:marks.completeness},{label:"回答相關度",weight:"25%",value:marks.relevance},{label:"備審一致性",weight:"20%",value:marks.consistency},{label:"口語表達",weight:"10%",value:marks.oral}].filter(m=>!textMode||m.label!=="口語表達").map(m=><div key={m.label}><div><span>{m.label} {!textMode&&<small>權重 {m.weight}</small>}</span><strong>{m.value===null?(session.reportReview?.complete?"不適用／無有效資料":"等待評分"):display(m.value)}</strong></div>{m.value!==null&&<Progress value={m.value}/>}</div>)}</div><p className="privacy-note">{textMode?"文字面試不提供總分、等第或口語評分。":"不適用的指標不計入總分，其餘權重按比例調整。"}</p>{reviewState==="loading"&&<p role="status">正在產生逐題評分與改善建議…</p>}{reviewState==="failed"&&<p role="alert">{reviewError||"AI 評分暫時失敗，原始回答均已保存。"}<Button variant="secondary" onClick={()=>void review()}>重試評分</Button></p>}</Card>
    <FollowupAnalysis session={session}/>
    <div className="report-grid"><Card><div className="card-title"><div><h2>回答完整度</h2><p>各主題最後一輪累積分析的平均</p></div><strong className="section-score">{completeness??"—"}</strong></div>{dimensionScores.map(d=><div className="submetric" key={d.key}><span>{d.label}<strong>{d.score??"未評估"}</strong></span>{d.score!==null&&<Progress value={d.score}/>}</div>)}</Card>{!textMode&&<Card><div className="card-title"><div><h2>口語表達</h2><p>根據語音辨識資料分析</p></div><strong className="section-score">{marks.oral===null?"—":Math.round(marks.oral)}</strong></div><div className="speech-grid"><span><small>平均語速</small><strong>{rates===null?"未評估":`每分鐘 ${rates} 字`}</strong></span><span><small>停頓次數</small><strong>{speeches.length?`${pauses} 次`:"未評估"}</strong></span><span><small>常見贅字</small><strong>{speeches.length?Object.entries(fillers).filter(([,n])=>n).map(([w,n])=>`${w} ${n} 次`).join("、")||"未辨識到":"未評估"}</strong></span><span><small>超時提醒</small><strong>{timeout} 題</strong></span></div></Card>}</div>
    <div className="report-grid report-grid-single">{issues.length>0&&<Card><div className="card-title"><div><h2>備審一致性待核對</h2><p>{issues.length} 處待確認</p></div></div>{issues.map((item,i)=><p key={i} className="privacy-note">{reportText(item.note||item.issue_type||'請核對備審資料')} {item.portfolio_sources?.length?`（來源頁碼：${item.portfolio_sources.map(x=>x.page).filter(Boolean).join("、")}）`:""}</p>)}</Card>}{!textMode&&<Card><div className="card-title"><div><h2>面部行為分析</h2><p>獨立呈現，不計入總分</p></div></div><div className="face-grid">{["眼神方向","眨眼","嘴部微表情","頭部朝向","是否出現在畫面"].map(x=><span key={x}><small>{x}</small><strong>未評估</strong></span>)}</div></Card>}</div></>}
    {free&&<Card className="topic-analysis report-answer-card"><div className="card-title"><div><h2>逐題作答紀錄</h2><p>完整保留每題題目、原始回答與作答時間</p></div><Badge tone="purple">{answers.length} 題</Badge></div>{answers.map((a,i)=>{const result=reviewRows.find(x=>x.number===i+1);const oral=oralParts(a);const advice=result?.advice||(a.gaps?.length?a.gaps.map(g=>gapSuggestions[g]||"補充具體內容。").join(" "):a.timedOut?"先回答核心問題，再簡短補充例子，避免超時。":"建議先說明核心結論，再補充具體作法與結果。");const body=<><h3>{a.question}</h3><h4>學生回答</h4><p className="report-answer-text">{a.text||"未作答"}</p><div className="report-answer-scores">{!free&&<><span>相關度：{result?.relevance==null?"未評估":`${result.relevance} 分`}</span><span>一致性：{result?.consistency==null?(!result?"等待評分":result.consistencyStatus==="pending"?"待核對":result.consistencyStatus==="not_applicable"?"不適用":"未評估"):`${result.consistency} 分`}</span></>}{oral&&<span>口語：{display(oral.total)} 分</span>}</div>{a.metrics&&<p className="privacy-note">語音資料：{a.metrics.sufficient?`語速 ${a.metrics.rate??"未評估"} 字/分鐘 · 停頓 ${a.metrics.pauses.length} 次`:"資料不足，未評估"}</p>}<div className="report-question-advice"><h4>改善建議{!result?"（初步）":""}</h4><p>{advice}</p></div></>;return <section key={i} className="report-answer-item">{a.kind==="followup"?<details><summary className="followup-summary"><div className="followup-index">第 {i+1} 題 <span>追問</span></div><div className="followup-title">{a.question}</div><span className="followup-chevron" aria-hidden="true"><Icon name="chevron" size={18}/></span></summary>{body}</details>:<><div className="report-answer-heading"><Badge tone="purple">第 {i+1} 題{a.kind==="restate"?" · 重述":" · 主問題"}</Badge><span>{fmt(a.duration)} · {a.mode==="voice"?"語音作答":"文字作答"}{a.timedOut?" · 超時":""}</span></div>{body}</>}</section>;})}{!answers.length&&<p>尚無作答紀錄。</p>}</Card>}
  </AppShell>;
}

function GrowthTrend({records}:{records:Session[]}){
  const [filter,setFilter]=useState("all");const labels=[...new Set(records.filter(r=>r.target).map(r=>`${r.target!.school} · ${r.target!.department}`))];
  const rows=records.filter(r=>!r.id.startsWith("free-")&&(filter==="all"||`${r.target?.school} · ${r.target?.department}`===filter)).sort((a,b)=>(a.completedAt||"").localeCompare(b.completedAt||""));
  const series=[{key:"total",name:"總分",color:"#8153b7"},{key:"completeness",name:"完整度",color:"#3b82b6"},{key:"relevance",name:"相關度",color:"#d55b8c"},{key:"consistency",name:"一致性",color:"#2c9a83"},{key:"oral",name:"口語",color:"#d39a35"}] as const;
  const points=rows.map(r=>scores(r));const x=(i:number)=>rows.length===1?350:45+i*610/Math.max(1,rows.length-1);const y=(n:number)=>210-n*1.8;
  return <Card className="growth-card"><div className="card-title"><div><h2>歷史成長趨勢</h2><p>比較個人化面試歷次成績與各項指標</p></div><select aria-label="篩選校系" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">全部校系</option>{labels.map(l=><option key={l}>{l}</option>)}</select></div>{rows.length?<>{rows.length>1?<div className="growth-chart"><svg viewBox="0 0 700 245" role="img" aria-label="歷次面試分數走勢">{[0,25,50,75,100].map(n=><g key={n}><text x="7" y={y(n)+4} fontSize="13" fill="#84768d">{n}</text><line x1="45" x2="655" y1={y(n)} y2={y(n)} stroke="#e7dfea"/></g>)}{series.map(line=><g key={line.key}>{points.map((p,i)=>{const v=p[line.key],prior=i?points[i-1][line.key]:null;return v===null?null:<g key={i}>{prior!==null&&<line x1={x(i-1)} y1={y(prior)} x2={x(i)} y2={y(v)} stroke={line.color} strokeWidth="2.5"/>}<circle cx={x(i)} cy={y(v)} r="4" fill={line.color}><title>{`${line.name}：${Math.round(v)} 分`}</title></circle></g>;})}</g>)}{rows.map((r,i)=><text key={r.id} x={x(i)} y="230" textAnchor="middle" fontSize="13" fill="#84768d">{i+1}</text>)}</svg></div>:<div className="growth-first"><Icon name="chart" size={24}/><div><strong>已建立第一筆成長基準</strong><p>完成下一次面試後，即可比較分數變化。</p></div></div>}<div className="growth-legend">{series.map(l=><span key={l.key}><i style={{background:l.color}}/>{l.name}</span>)}</div><div style={{overflowX:"auto"}}><table className="growth-table"><thead><tr><th>場次／日期</th><th>校系</th>{series.map(l=><th key={l.key}>{l.name}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={r.id}><td title={r.dateEstimated?"舊紀錄的最後保存日期":"面試完成日期"}>{i+1} · {r.completedAt?new Date(r.completedAt).toLocaleDateString("zh-TW"):"未記錄"}</td><td>{r.target?.school} · {r.target?.department}</td>{series.map(l=><td key={l.key}>{points[i][l.key]===null?"—":Math.round(points[i][l.key]!)}</td>)}</tr>)}</tbody></table></div>{points.some(p=>series.some(l=>p[l.key]===null))&&<small>— 表示尚無評分或該面試模式不提供此項。</small>}</>:<p>目前尚無本校系完成的個人化面試。</p>}</Card>;
}
function History({go,onSelect}:{go:(p:Page)=>void;onSelect:(session:Session)=>void}) {
  const { records, status } = useInterviewHistory();
  if (status !== "ready" && !records.length) {
    return <AppShell page="history" go={go}><p role="status">{status === "loading" ? "正在載入面試紀錄…" : "無法讀取面試紀錄，請重新整理後再試。"}</p></AppShell>;
  }
  const duration=records.reduce((sum,r)=>sum+r.answers.reduce((n,a)=>n+(Number.isFinite(a.duration)?a.duration:0),0),0);
  return <AppShell page="history" go={go}>
    <PageTitle eyebrow="面試紀錄" title="回顧你的練習" desc="查看歷次面試報告與成長趨勢。" action={<Button icon="plus" onClick={()=>go("prepare")}>開始新的模擬面試</Button>}/>
    <div className="history-stats">
      <Card><span><Icon name="mic"/></span><div><small>累積面試</small><strong>{records.length} 場</strong></div></Card>
      <Card><span><Icon name="clock"/></span><div><small>累積作答</small><strong>{Math.floor(duration/60)} 分 {Math.round(duration%60)} 秒</strong></div></Card>
      <Card><span><Icon name="chart"/></span><div><small>最佳成績</small><strong>{records.map(r=>scores(r).total).filter((x):x is number=>x!==null).length?Math.round(Math.max(...records.map(r=>scores(r).total??-1))):"尚無評分"}</strong></div></Card>
    </div>
    <GrowthTrend records={records}/>
    {records.length?<VoiceHistory records={records} onSelect={onSelect}/>:<Card><h2>尚無面試紀錄</h2><p>完成面試後即可查看逐題報告。</p><Button onClick={()=>go("prepare")}>開始練習</Button></Card>}
  </AppShell>;
}
function Settings({ go, needsName, onSaved, onAccount }: {
  go: (p: Page) => void;
  needsName?: boolean;
  onSaved: () => void;
  onAccount: (account: Account) => void;
}) {
  const account = useContext(AccountContext)!;
  const [name, setName] = useState(account.name);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  async function saveName() {
    if (!name.trim()) { setMessage("請輸入姓名或暱稱。"); return; }
    setSaving(true);
    try {
      onAccount(await workspaceRequest<Account>("/api/account/me", "PATCH", { name: name.trim() }, account.id));
      setMessage("已儲存變更。");
      onSaved();
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell page="settings" go={go}>
      <PageTitle
        eyebrow="帳號設定"
        title="管理你的帳號"
        desc="更新姓名或暱稱。"
        action={<Button variant="secondary" icon="logout" onClick={() => go("logout")}>登出</Button>}
      />
      <Card className="settings-content">
        <div className="settings-heading">
          <h2>基本資料</h2>
          <p>這些資訊會顯示在你的學習空間中。</p>
        </div>
        {needsName&&<p className="name-required-notice" role="alert">開始或接續面試前，請先輸入姓名或暱稱並儲存。</p>}
        <div className="settings-form">
          <label>
            姓名或暱稱（必填）
            <input value={name} required onChange={e=>{setName(e.target.value);setMessage("");}} />
          </label>
          <label>
            電子郵件
            <input value={account.email} readOnly aria-readonly="true" />
            <small>電子郵件為帳號識別資料，不可變更。</small>
          </label>
        </div>
        <div className="form-actions">
          <span role="status">{message}</span><Button onClick={saveName} disabled={saving}>{needsName?"儲存並繼續面試":"儲存變更"}</Button>
        </div>
      </Card>
    </AppShell>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("landing");
  const [pendingInterview,setPendingInterview]=useState<Page>();
  const [account, setAccount] = useState<Account | null>(null);
  const [accountError, setAccountError] = useState("");
  const schools = account?.targets ?? [];
  async function setSchools(targets: ApplicationTarget[]) {
    if (!account) return;
    setAccount(await workspaceRequest<Account>("/api/account/me", "PATCH", { targets }, account.id));
  }
  function onAuthenticated(profile: Account) {
    setAccountError("");
    setAccount(profile);
    setPage("dashboard");
    window.scrollTo({ top: 0 });
  }
  const [interviewTarget, setInterviewTarget] = useState<ApplicationTarget>();
  const [resumeId,setResumeId] = useState<string>();
  const [selectedReport,setSelectedReport] = useState<Session>();
  const [interviewMode, setInterviewMode] = useState<"voice" | "text">("voice");
  const [noPortfolio,setNoPortfolio]=useState(false);
  useEffect(() => {
    let current = true;
    void workspaceRequest<Account>("/api/account/me").then(profile => {
      if (current) onAuthenticated(profile);
    }).catch(() => {});
    return () => { current = false; };
  }, []);
  const go = (next: Page) => {
    if (next === "logout") {
      void workspaceRequest("/api/account/logout", "POST").then(() => {
        setAccount(null);
        setAccountError("");
        setSelectedReport(undefined);
        setResumeId(undefined);
        setInterviewTarget(undefined);
        setPendingInterview(undefined);
        setPage("landing");
        window.scrollTo({ top: 0 });
      }).catch(error => setAccountError(error.message));
      return;
    }
    if (!account && next !== "landing" && next !== "login" && next !== "register") next = "login";
    if((next==="prepare"||next==="interview"||next==="freeInterview")&&!account?.name.trim()){
      setPendingInterview(next);setPage("settings");window.scrollTo({top:0});return;
    }
    setPendingInterview(undefined);
    if (next !== "interview" && !(next === "report" && page === "interview")) {
      setInterviewTarget(undefined);
    }
    setPage(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  function view() {
    switch (page) {
      case "landing":
        return <Landing go={go} />;
      case "login":
        return <Auth mode="login" go={go} onAuthenticated={onAuthenticated} />;
      case "register":
        return <Auth mode="register" go={go} onAuthenticated={onAuthenticated} />;
      case "dashboard":
        return <Dashboard go={go} schools={schools} onResume={(target,id)=>{setInterviewMode("voice");setInterviewTarget(target);setResumeId(id);go("interview");}} />;
      case "plans":
        return <PurchasePlans go={go} />;
      case "profile":
        return <Profile go={go} schools={schools} setSchools={setSchools} />;
      case "upload":
        return <Upload go={go} schools={schools} />;
      case "analysis":
        return <Analysis go={go} />;
      case "prepare":
        return <Prepare go={go} schools={schools} onStart={(target, mode, withoutPortfolio) => {
          setInterviewMode(mode);
          setNoPortfolio(!!withoutPortfolio);
          setResumeId(undefined);
          setInterviewTarget(target);
          go("interview");
        }} />;
      case "interview":
        return <VoiceInterview accountId={account!.id} target={interviewTarget} mode={interviewMode} noPortfolio={noPortfolio} resumeId={resumeId} onExit={() => go("dashboard")} renderReport={session=><Report go={go} session={session} free={session.id.startsWith("free-")}/>} />;
      case "freeInterview":
        return <VoiceInterview accountId={account!.id} free mode="voice" onExit={() => go("dashboard")} renderReport={session=><Report go={go} session={session} free={session.id.startsWith("free-")}/>} />;
      case "report":
        return <Report go={go} session={selectedReport} free={selectedReport?.id.startsWith("free-")} />;
      case "freeReport":
        return <Report go={go} free session={selectedReport} />;
      case "history":
        return <History go={go} onSelect={session=>{setSelectedReport(session);go("report");}} />;
      case "settings":
        return <Settings go={go} onAccount={setAccount} needsName={!!pendingInterview} onSaved={()=>{if(pendingInterview)go(pendingInterview);}} />;
    }
  }
  return <AccountContext.Provider value={account} key={account?.id}>
    {accountError && <p role="alert">{accountError}</p>}
    {view()}
  </AccountContext.Provider>;
}
