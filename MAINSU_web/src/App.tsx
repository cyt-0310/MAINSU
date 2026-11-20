import { useEffect, useMemo, useState, type ReactNode } from "react";

type Page =
  | "landing"
  | "login"
  | "register"
  | "dashboard"
  | "profile"
  | "upload"
  | "analysis"
  | "prepare"
  | "interview"
  | "freeInterview"
  | "report"
  | "freeReport"
  | "history"
  | "settings";

type IconName =
  | "spark"
  | "arrow"
  | "check"
  | "file"
  | "mic"
  | "chart"
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
  { page: "profile", label: "申請資料", icon: "user" },
  { page: "upload", label: "備審資料", icon: "upload" },
  { page: "history", label: "面試紀錄", icon: "clock" },
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
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button onClick={() => go("landing")} className="logo-button">
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
        <div className="plan-card">
          <span className="plan-icon">
            <Icon name="spark" size={18} />
          </span>
          <Badge tone="purple">完整版</Badge>
          <strong>讓每次練習更有方向</strong>
          <p>本月尚有 4 場完整面試</p>
          <button onClick={() => go("prepare")}>
            開始練習 <Icon name="arrow" size={15} />
          </button>
        </div>
        <div className="side-user">
          <span className="avatar">陳</span>
          <div>
            <strong>陳語晴</strong>
            <small>yuching@example.com</small>
          </div>
          <button onClick={() => go("landing")} aria-label="登出">
            <Icon name="logout" size={18} />
          </button>
        </div>
      </aside>
      <main className="app-main">
        <header className="topbar">
          <div>
            <span className="status-dot" /> 服務運作正常
          </div>
          <div className="top-actions">
            <button className="icon-button" aria-label="通知">
              <span className="notification-dot" />
              <Icon name="alert" size={19} />
            </button>
            <Badge tone="purple">完整版方案</Badge>
          </div>
        </header>
        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}

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
              從備審資料出發，AI 模擬教授真實提問與動態追問。
              <br />
              不只陪你練習，更讓你知道如何進步。
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
                <Icon name="check" size={16} /> 免費開始
              </span>
              <span>
                <Icon name="check" size={16} /> 不需信用卡
              </span>
              <span>
                <Icon name="shield" size={16} /> 資料安全保護
              </span>
            </div>
          </div>
          <div className="hero-visual">
            <div className="mock-window">
              <div className="window-top">
                <span />
                <span />
                <span />
                <small>AI 模擬面試進行中</small>
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
                <small>備審分析完成</small>
                <strong>辨識 12 個學習事件</strong>
              </div>
              <Icon name="check" />
            </div>
            <div className="floating-card fc-two">
              <span>86</span>
              <div>
                <small>本次面試表現</small>
                <strong>表現優良</strong>
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="features">
          <div className="section-heading">
            <Badge tone="blue">核心特色</Badge>
            <h2>把練習，變成真正有效的準備</h2>
            <p>不提供制式答案，而是從你的經歷出發，打造專屬面試情境。</p>
          </div>
          <div className="feature-grid">
            <Card>
              <span className="feature-icon blue">
                <Icon name="file" size={26} />
              </span>
              <h3>備審資料智慧分析</h3>
              <p>整理學習歷程中的重要事件、能力與成果，找出你與申請科系的真實連結。</p>
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
              <p>依回答的完整度、相關度與一致性判斷後續問題，還原真實面試節奏。</p>
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
              <p>從四大指標看見表現，以清楚、具體的練習建議持續改善。</p>
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
              ["01", "建立申請資料", "選擇你的目標學校與科系", "school"],
              ["02", "上傳備審資料", "PDF 安全上傳並選擇對應校系", "upload"],
              ["03", "進行模擬面試", "在引導下完成語音回答", "mic"],
              ["04", "取得分析報告", "掌握優勢與下一步練習方向", "chart"],
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
            <h2>先免費試試，再決定要不要更深入</h2>
          </div>
          <div className="pricing-grid">
            <Card className="price-card">
              <Badge tone="gray">免費版</Badge>
              <h3>基礎模擬面試</h3>
              <p>適合第一次熟悉面試流程</p>
              <strong className="price">NT$ 0</strong>
              <Button variant="secondary" onClick={() => go("register")}>
                免費開始
              </Button>
              <ul>
                {["每日最多 3 場", "每場 3 題主問題", "最長 8 分鐘", "基礎相關度與口語回饋"].map(
                  (x) => (
                    <li key={x}>
                      <Icon name="check" size={16} />
                      {x}
                    </li>
                  ),
                )}
                <li className="muted">不含備審分析與動態追問</li>
              </ul>
            </Card>
            <Card className="price-card featured">
              <span className="recommended">最推薦</span>
              <Badge tone="purple">完整版</Badge>
              <h3>個人化深度練習</h3>
              <p>適合進入面試衝刺階段</p>
              <strong className="price">依方案選擇</strong>
              <Button onClick={() => go("register")}>體驗完整功能</Button>
              <ul>
                {[
                  "備審 PDF 智慧分析",
                  "2～3 個個人化主題",
                  "每題最多 2 次動態追問",
                  "10～20 分鐘完整面試",
                  "四大指標與深度分析報告",
                  "支援攝影機行為偵測",
                ].map((x) => (
                  <li key={x}>
                    <Icon name="check" size={16} />
                    {x}
                  </li>
                ))}
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

function Auth({ mode, go }: { mode: "login" | "register"; go: (p: Page) => void }) {
  const [error, setError] = useState("");
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const data = new FormData(e.target as HTMLFormElement);
    if (!(data.get("email") as string)?.includes("@")) setError("請輸入有效的電子郵件格式");
    else go("dashboard");
  };
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
            {mode === "login" && (
              <button type="button" className="forgot">
                忘記密碼？
              </button>
            )}
            <Button type="submit" className="full">
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

function Dashboard({ go }: { go: (p: Page) => void }) {
  return (
    <AppShell page="dashboard" go={go}>
      <PageTitle
        eyebrow="2026 年 3 月 10 日，星期二"
        title="早安，語晴"
        desc="距離臺灣大學面試還有 24 天，今天也一起穩定前進。"
        action={
          <Button icon="plus" onClick={() => go("prepare")}>
            開始新的模擬面試
          </Button>
        }
      />
      <div className="dashboard-grid">
        <Card className="target-card">
          <div className="card-head">
            <div>
              <Badge tone="blue">主要目標</Badge>
              <h2>國立臺灣大學</h2>
              <p>資訊管理學系</p>
            </div>
            <span className="school-logo">臺大</span>
          </div>
          <div className="target-meta">
            <span>
              <Icon name="clock" size={17} />
              <i>面試日期</i>
              <strong>4 月 3 日</strong>
            </span>
            <span>
              <Icon name="mic" size={17} />
              <i>練習次數</i>
              <strong>5 次</strong>
            </span>
            <span>
              <Icon name="chart" size={17} />
              <i>最佳成績</i>
              <strong>86 分</strong>
            </span>
          </div>
          <button onClick={() => go("profile")}>
            管理申請校系 <Icon name="chevron" size={16} />
          </button>
        </Card>
        <Card className="plan-status">
          <div className="card-head">
            <div>
              <Badge tone="purple">完整版</Badge>
              <h2>本月練習額度</h2>
            </div>
            <span className="donut">
              4<small>場</small>
            </span>
          </div>
          <Progress value={40} color="purple" />
          <p>已使用 2 場，共 6 場完整面試</p>
          <small>額度將於 4 月 1 日更新</small>
        </Card>
      </div>
      <div className="section-row">
        <h2>快速開始</h2>
        <span>選擇適合今天的練習方式</span>
      </div>
      <div className="quick-grid">
        <button className="quick-card premium" onClick={() => go("prepare")}>
          <span className="feature-icon purple">
            <Icon name="spark" />
          </span>
          <Badge tone="purple">推薦</Badge>
          <h3>完整 AI 模擬面試</h3>
          <p>依備審資料產生個人化問題，包含動態追問與深度報告。</p>
          <span className="quick-meta">
            <i>
              <Icon name="clock" size={15} /> 10～20 分鐘
            </i>
            <strong>
              開始準備 <Icon name="arrow" size={16} />
            </strong>
          </span>
        </button>
        <button className="quick-card" onClick={() => go("freeInterview")}>
          <span className="feature-icon blue">
            <Icon name="mic" />
          </span>
          <Badge tone="gray">免費版</Badge>
          <h3>快速基礎練習</h3>
          <p>3 題常見問題，不使用備審與追問，適合暖身。</p>
          <span className="quick-meta">
            <i>
              <Icon name="clock" size={15} /> 最多 8 分鐘
            </i>
            <strong>
              今日剩餘 2 場 <Icon name="arrow" size={16} />
            </strong>
          </span>
        </button>
      </div>
      <div className="dashboard-bottom">
        <Card>
          <div className="card-title">
            <div>
              <h2>最近一次面試</h2>
              <p>3 月 8 日 · 完整版</p>
            </div>
            <button onClick={() => go("report")}>
              查看完整報告 <Icon name="chevron" size={15} />
            </button>
          </div>
          <div className="recent-score">
            <span>
              <strong>86</strong>
              <small>/ 100</small>
            </span>
            <div>
              <Badge tone="green">表現優良</Badge>
              <h3>整體回答穩定，經驗描述具體</h3>
              <p>若能加強申請動機與科系課程的連結，說服力會更完整。</p>
            </div>
          </div>
          <div className="metric-row">
            {[
              ["完整度", "88", 88],
              ["相關度", "82", 82],
              ["備審一致性", "91", 91],
              ["口語表達", "78", 78],
            ].map((x) => (
              <div key={x[0] as string}>
                <span>
                  {x[0]}
                  <strong>{x[1]}</strong>
                </span>
                <Progress value={x[2] as number} />
              </div>
            ))}
          </div>
        </Card>
        <Card className="docs-card">
          <div className="card-title">
            <div>
              <h2>備審資料</h2>
              <p>臺大資訊管理學系</p>
            </div>
            <Badge tone="green">
              <Icon name="check" size={14} />
              分析完成
            </Badge>
          </div>
          <div className="doc-count">
            <span>
              <Icon name="file" size={24} />
            </span>
            <div>
              <strong>8 份文件</strong>
              <small>辨識 12 個學習事件</small>
            </div>
          </div>
          <button onClick={() => go("analysis")}>
            查看分析結果 <Icon name="arrow" size={16} />
          </button>
        </Card>
      </div>
    </AppShell>
  );
}

function Profile({ go }: { go: (p: Page) => void }) {
  const [saved, setSaved] = useState(true);
  const [schools, setSchools] = useState([
    ["國立臺灣大學", "資訊管理學系"],
    ["國立政治大學", "資訊管理學系"],
  ]);
  return (
    <AppShell page="profile" go={go}>
      <PageTitle
        eyebrow="申請資料"
        title="建立你的申請目標"
        desc="校系會一對一配對，最多可建立 6 組申請目標。"
        action={
          <span className={`save-state ${saved ? "" : "saving"}`}>
            <Icon name={saved ? "check" : "refresh"} size={15} />
            {saved ? "所有變更已儲存" : "正在儲存變更…"}
          </span>
        }
      />
      <Card className="form-card">
        <div className="form-section">
          <div className="form-section-title">
            <span>1</span>
            <div>
              <h2>基本資料</h2>
              <p>面試中會以此稱呼你</p>
            </div>
          </div>
          <label>
            姓名或暱稱 <small>必填</small>
            <input
              defaultValue="陳語晴"
              onChange={() => {
                setSaved(false);
                setTimeout(() => setSaved(true), 800);
              }}
            />
          </label>
        </div>
        <div className="form-divider" />
        <div className="form-section">
          <div className="form-section-title">
            <span>2</span>
            <div>
              <h2>申請學校與科系</h2>
              <p>請確認校系配對正確，之後仍可修改</p>
            </div>
          </div>
          <div className="school-list">
            {schools.map((s, i) => (
              <div className="school-item" key={i}>
                <span className="item-index">{i + 1}</span>
                <label>
                  申請學校
                  <select
                    value={s[0]}
                    onChange={(e) =>
                      setSchools((v) => v.map((x, j) => (j === i ? [e.target.value, x[1]] : x)))
                    }
                  >
                    <option>國立臺灣大學</option>
                    <option>國立政治大學</option>
                    <option>國立清華大學</option>
                  </select>
                </label>
                <label>
                  申請科系
                  <select
                    value={s[1]}
                    onChange={(e) =>
                      setSchools((v) => v.map((x, j) => (j === i ? [x[0], e.target.value] : x)))
                    }
                  >
                    <option>資訊管理學系</option>
                    <option>企業管理學系</option>
                    <option>經濟學系</option>
                  </select>
                </label>
                <button
                  aria-label="移除校系"
                  onClick={() => setSchools((v) => v.filter((_, j) => j !== i))}
                >
                  <Icon name="trash" size={18} />
                </button>
              </div>
            ))}
          </div>
          <button
            className="add-school"
            disabled={schools.length >= 6}
            onClick={() => setSchools((v) => [...v, ["國立清華大學", "企業管理學系"]])}
          >
            <Icon name="plus" size={18} />
            新增申請校系 <small>{schools.length} / 6</small>
          </button>
        </div>
        <div className="form-actions">
          <Button variant="secondary" onClick={() => go("dashboard")}>
            稍後再說
          </Button>
          <Button onClick={() => go("upload")}>
            儲存並繼續 <Icon name="arrow" size={17} />
          </Button>
        </div>
      </Card>
    </AppShell>
  );
}

const files = [
  ["學習歷程自述_臺大資管.pdf", "2.4 MB", "分析完成"],
  ["自主學習成果_校園碳排系統.pdf", "3.1 MB", "分析完成"],
  ["社團幹部經驗.pdf", "1.8 MB", "上傳完成"],
];

function Upload({ go }: { go: (p: Page) => void }) {
  const [active, setActive] = useState("學習歷程自述");
  const [fileList, setFileList] = useState(files);
  const categories = [
    ["學習歷程自述", "必傳", "2 / 6"],
    ["多元表現", "選填", "3 / 60"],
    ["課程學習成果", "選填", "2 / 18"],
    ["其他備審文件", "選填", "1 / 18"],
  ];
  return (
    <AppShell page="upload" go={go}>
      <PageTitle
        eyebrow="備審資料"
        title="上傳與管理備審文件"
        desc="上傳 PDF 後選擇適用校系，系統將以模擬資料展示分析流程。"
        action={
          <Badge tone="purple">
            <Icon name="spark" size={14} />
            完整版功能
          </Badge>
        }
      />
      <div className="info-banner">
        <Icon name="shield" size={20} />
        <div>
          <strong>這是介面流程展示</strong>
          <p>目前不會實際上傳或分析文件；範例結果為模擬資料。正式服務僅接受 PDF，每份上限 5MB。</p>
        </div>
      </div>
      <div className="upload-layout">
        <Card className="category-nav">
          <h3>文件分類</h3>
          {categories.map((c) => (
            <button
              className={active === c[0] ? "active" : ""}
              onClick={() => setActive(c[0])}
              key={c[0]}
            >
              <span>
                <Icon name="file" size={18} />
                <i>
                  <strong>{c[0]}</strong>
                  <small>{c[1]}</small>
                </i>
              </span>
              <em>{c[2]}</em>
            </button>
          ))}
          <div className="capacity">
            <span>
              總檔案數 <strong>8 / 102</strong>
            </span>
            <Progress value={8} />
          </div>
        </Card>
        <div className="upload-main">
          <Card>
            <div className="card-title">
              <div>
                <h2>{active}</h2>
                <p>
                  {active === "學習歷程自述"
                    ? "此類文件為完整版分析的必要資料"
                    : "可依需求補充，協助建立更多面試素材"}
                </p>
              </div>
              <Badge tone={active === "學習歷程自述" ? "amber" : "gray"}>
                {active === "學習歷程自述" ? "必傳" : "選填"}
              </Badge>
            </div>
            <label className="dropzone">
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => {
                  if (e.target.files?.[0])
                    setFileList((v) => [[e.target.files![0].name, "1.2 MB", "上傳完成"], ...v]);
                }}
              />
              <span>
                <Icon name="upload" size={26} />
              </span>
              <h3>
                拖曳 PDF 到這裡，或 <u>選擇檔案</u>
              </h3>
              <p>僅接受 PDF 格式，單一檔案不超過 5MB</p>
            </label>
            <div className="file-list">
              <div className="list-header">
                <strong>已上傳檔案</strong>
                <span>{fileList.length} 份</span>
              </div>
              {fileList.map((f, i) => (
                <div className="file-row" key={`${f[0]}${i}`}>
                  <span className="pdf-icon">PDF</span>
                  <div className="file-info">
                    <strong>{f[0]}</strong>
                    <small>
                      {f[1]} ·{" "}
                      <i>
                        <Icon name="check" size={12} />
                        {f[2]}
                      </i>
                    </small>
                  </div>
                  <div className="school-chips">
                    <span>臺大資管</span>
                    {i === 0 && <span>政大資管</span>}
                    <button>＋ 選擇校系</button>
                  </div>
                  <button
                    aria-label="移除"
                    onClick={() => setFileList((v) => v.filter((_, j) => j !== i))}
                  >
                    <Icon name="trash" size={17} />
                  </button>
                </div>
              ))}
            </div>
          </Card>
          <div className="sticky-actions">
            <span>
              <Icon name="check" size={16} /> 已自動儲存
            </span>
            <div>
              <Button variant="secondary" onClick={() => go("dashboard")}>
                返回總覽
              </Button>
              <Button onClick={() => go("analysis")}>
                查看分析結果 <Icon name="arrow" size={17} />
              </Button>
            </div>
          </div>
        </div>
      </div>
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

function Prepare({ go }: { go: (p: Page) => void }) {
  const [mic, setMic] = useState(false);
  const [camera, setCamera] = useState(false);
  return (
    <AppShell page="dashboard" go={go}>
      <PageTitle
        eyebrow="面試前準備"
        title="確認設定，準備開始"
        desc="完成設備測試後，就可以進入模擬面試。"
      />
      <div className="prep-steps">
        <span className="done">
          <i>
            <Icon name="check" size={15} />
          </i>
          選擇校系
        </span>
        <b />
        <span className="active">
          <i>2</i>確認規則
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
                <h2>國立臺灣大學 · 資訊管理學系</h2>
                <p>個人化動態追問模式</p>
              </div>
              <button className="text-button" onClick={() => go("profile")}>
                更換校系
              </button>
            </div>
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
                <h2>設備測試</h2>
                <p>開始前請允許瀏覽器使用麥克風與攝影機</p>
              </div>
              <Badge tone="gray">模擬測試</Badge>
            </div>
            <div className="device-row">
              <span className={`device-icon ${mic ? "success" : ""}`}>
                <Icon name="mic" />
              </span>
              <div>
                <strong>麥克風</strong>
                <p>{mic ? "已偵測到清楚的聲音" : "尚未進行測試"}</p>
                {mic && (
                  <div className="volume-bars">
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                      <i key={n} style={{ height: `${6 + n * 2}px` }} />
                    ))}
                  </div>
                )}
              </div>
              <Button variant={mic ? "secondary" : "primary"} onClick={() => setMic(true)}>
                {mic ? "重新測試" : "測試麥克風"}
              </Button>
            </div>
            <div className="device-row">
              <span className={`device-icon ${camera ? "success" : ""}`}>
                <Icon name="camera" />
              </span>
              <div>
                <strong>
                  攝影機 <Badge tone="purple">完整版支援</Badge>
                </strong>
                <p>{camera ? "畫面正常；面部行為分析為選用功能" : "尚未進行測試"}</p>
              </div>
              <Button variant="secondary" onClick={() => setCamera(true)}>
                {camera ? "已通過" : "測試攝影機"}
              </Button>
            </div>
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
          <Button className="full" disabled={!mic} onClick={() => go("interview")} icon="play">
            開始模擬面試
          </Button>
          {!mic && <small>請先完成麥克風測試</small>}
          <p className="simulation-note">此原型使用模擬題目，不會啟用真實 AI 或裝置偵測。</p>
        </Card>
      </div>
    </AppShell>
  );
}

type InterviewState =
  | "asking"
  | "answering"
  | "processing"
  | "analyzing"
  | "followup"
  | "clarify"
  | "timewarning"
  | "micerror"
  | "networkerror"
  | "done";

function Interview({ go, free = false }: { go: (p: Page) => void; free?: boolean }) {
  const [state, setState] = useState<InterviewState>("asking");
  const [seconds, setSeconds] = useState(free ? 120 : 120);
  const [question, setQuestion] = useState(1);
  useEffect(() => {
    if (state !== "answering" && state !== "timewarning") return;
    const timer = setInterval(() => setSeconds((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [state]);
  useEffect(() => {
    if (seconds === 0 && (state === "answering" || state === "timewarning")) setState("processing");
  }, [seconds, state]);
  const statusMap = {
    asking: ["AI 正在提問", "請先聆聽完整問題"],
    answering: ["正在錄製你的回答", "說完後請點選「結束回答」"],
    processing: ["語音轉文字處理中", "已保留錄音，請稍候"],
    analyzing: ["AI 正在分析回答", "正在準備下一個問題，通常需要數秒"],
    followup: ["這是一題追問", "請根據剛才的內容補充說明"],
    clarify: ["讓我們重新聚焦問題", "剛才的回答較偏離題目，請依提示重新說明"],
    timewarning: ["回答時間即將結束", "剩餘時間不多，請先說明最重要的結論"],
    micerror: ["無法使用麥克風", "請檢查瀏覽器權限，或改用文字輸入回答"],
    networkerror: ["網路暫時異常", "回答已保留；連線恢復後可安全重試"],
    done: ["面試已完成", "正在產生你的分析報告"],
  };
  const advance = () => {
    if (state === "asking" || state === "followup" || state === "clarify") {
      setState("answering");
      setSeconds(question === 1 ? (free ? 120 : 90) : 120);
    } else if (state === "answering" || state === "timewarning") {
      setState("processing");
      setTimeout(() => setState(free ? "asking" : "analyzing"), 1000);
      if (free) setQuestion((q) => q + 1);
    } else if (state === "processing") setState("analyzing");
    else if (state === "analyzing") {
      setState("followup");
      setQuestion((q) => q + 1);
    }
  };
  useEffect(() => {
    if (state !== "done") return;
    const t = setTimeout(() => go(free ? "freeReport" : "report"), 1800);
    return () => clearTimeout(t);
  }, [state, free, go]);
  const isBusy = ["processing", "analyzing", "networkerror", "done"].includes(state);
  const isRecording = state === "answering" || state === "timewarning";
  return (
    <div className="interview-page">
      <header className="interview-header">
        <Brand />
        <div className="interview-title">
          <Badge tone={free ? "gray" : "purple"}>{free ? "免費版" : "完整版"}</Badge>
          <strong>{free ? "基礎模擬面試" : "臺大資訊管理學系"}</strong>
          <span>此流程為模擬展示</span>
        </div>
        <button onClick={() => go("dashboard")}>結束面試</button>
      </header>
      <div className="interview-grid">
        <aside className="interviewer-panel">
          <div className={`ai-orb ${isBusy ? "thinking" : ""}`}>
            <span>
              <Icon name="spark" size={30} />
            </span>
            <i />
            <i />
            <i />
          </div>
          <div className="ai-name">
            <strong>AI 面試官</strong>
            <Badge tone={isBusy ? "amber" : "green"}>{isBusy ? "思考中" : "連線正常"}</Badge>
          </div>
          <div className="speech-bubble">
            <small>{state === "followup" ? "追問" : "目前提問"}</small>
            <p>
              {state === "followup"
                ? "你剛才提到在團隊中調整了溝通方式，可以具體說明你觀察到什麼問題，以及如何改變嗎？"
                : free
                  ? question === 1
                    ? "請用兩分鐘介紹你自己，並分享一項最能代表你的特質。"
                    : "為什麼想申請資訊管理學系？"
                  : "請分享你在校園碳排視覺化系統中，遇到最困難的問題，以及你如何解決。"}
            </p>
          </div>
          <div className="audio-status">
            <div className="wave small">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                <i key={n} style={{ height: `${6 + (n % 4) * 5}px` }} />
              ))}
            </div>
            <span>{isBusy ? "正在處理" : "語音播放完成"}</span>
          </div>
        </aside>
        <main className="answer-panel">
          <div className={`state-banner state-${state}`}>
            <span>
              {isBusy ? (
                <span className="spinner" />
              ) : (
                <Icon
                  name={isRecording ? "mic" : state === "micerror" ? "alert" : "spark"}
                  size={20}
                />
              )}
            </span>
            <div>
              <strong>{statusMap[state][0]}</strong>
              <p>{statusMap[state][1]}</p>
            </div>
          </div>
          <div className="question-card">
            <div>
              <Badge tone="purple">
                {free
                  ? `第 ${Math.min(question, 3)} 題，共 3 題`
                  : question === 1
                    ? "主問題 · 個人經驗"
                    : "追問 1 / 2"}
              </Badge>
              <span className="question-time">
                <Icon name="clock" size={15} />
                {question === 1 && !free ? "90 秒" : "最多 2 分鐘"}
              </span>
            </div>
            <h1>
              {state === "followup"
                ? "你如何發現溝通方式需要調整？改變後帶來什麼結果？"
                : free
                  ? question === 1
                    ? "請用兩分鐘介紹你自己。"
                    : "為什麼想申請資訊管理學系？"
                  : "面對資料格式不一致的問題，你如何找出原因並完成整合？"}
            </h1>
          </div>
          <div className={`record-area ${isRecording ? "recording" : ""}`}>
            <div
              className="timer-ring"
              style={{ "--progress": `${(seconds / 120) * 360}deg` } as React.CSSProperties}
            >
              <div>
                <strong>
                  {String(Math.floor(seconds / 60)).padStart(2, "0")}:
                  {String(seconds % 60).padStart(2, "0")}
                </strong>
                <small>{isRecording ? "剩餘時間" : "作答上限"}</small>
              </div>
            </div>
            {isRecording ? (
              <>
                <div className="live-wave">
                  {Array.from({ length: 28 }, (_, n) => (
                    <i key={n} style={{ height: `${12 + ((n * 7) % 36)}px` }} />
                  ))}
                </div>
                <Button variant="danger" icon="pause" onClick={advance}>
                  結束回答
                </Button>
              </>
            ) : state === "micerror" ? (
              <div className="processing-copy">
                <Icon name="mic" size={27} />
                <strong>請允許網站使用麥克風</strong>
                <p>你也可以先檢查系統輸入裝置，或改用文字方式完成這一題。</p>
                <Button variant="secondary" icon="refresh" onClick={() => setState("asking")}>
                  重新偵測
                </Button>
              </div>
            ) : isBusy ? (
              <div className="processing-copy">
                <span className="processing-dots">
                  <i />
                  <i />
                  <i />
                </span>
                <strong>請稍候，系統仍在運作</strong>
                <p>你已完成的回答已安全保留，不會因等待或暫時性異常而清空。</p>
              </div>
            ) : (
              <Button icon="mic" onClick={advance}>
                開始回答
              </Button>
            )}
          </div>
          <div className="transcript">
            <div>
              <span>
                <Icon name="file" size={17} />
                語音辨識文字預覽
              </span>
              {isRecording && <Badge tone="red">即時辨識中</Badge>}
            </div>
            <p>
              {isRecording
                ? "在這個專案中，我們一開始拿到的資料格式很不一致。我先把問題分成欄位名稱、日期格式和缺漏值三類，接著……"
                : "回答開始後，辨識出的文字會顯示在這裡。送出前你可以再次確認。"}
            </p>
          </div>
          <div className="demo-controls">
            <span>原型狀態展示：</span>
            <button onClick={() => setState("asking")}>AI 提問</button>
            <button onClick={() => setState("processing")}>轉文字</button>
            <button onClick={() => setState("analyzing")}>分析中</button>
            {!free && <button onClick={() => setState("followup")}>追問</button>}
            <button onClick={() => setState("clarify")}>偏題提示</button>
            <button
              onClick={() => {
                setSeconds(15);
                setState("timewarning");
              }}
            >
              倒數提醒
            </button>
            <button onClick={() => setState("micerror")}>麥克風錯誤</button>
            <button onClick={() => setState("networkerror")}>網路異常</button>
            <button onClick={() => setState("done")}>完成面試</button>
          </div>
        </main>
        <aside className="progress-panel">
          <div className="total-time">
            <small>面試總計時</small>
            <strong>{free ? "03:26" : "08:42"}</strong>
            <span>{free ? "上限 08:00" : "預估 10～20 分鐘"}</span>
          </div>
          <div className="topic-block">
            <div>
              <strong>面試進度</strong>
              <span>{free ? `${Math.min(question, 3)} / 3` : `${question + 2} / 最多 15 題`}</span>
            </div>
            <Progress value={free ? (Math.min(question, 3) / 3) * 100 : 34} color="purple" />
          </div>
          <div className="topics">
            <h3>{free ? "題目" : "目前主題"}</h3>
            {free ? (
              [
                ["1", "自我介紹"],
                ["2", "申請動機"],
                ["3", "常見面試題"],
              ].map((t, i) => (
                <div
                  className={
                    i + 1 === Math.min(question, 3) ? "current" : i + 1 < question ? "done" : ""
                  }
                  key={t[0]}
                >
                  <span>{i + 1 < question ? <Icon name="check" size={14} /> : t[0]}</span>
                  <p>{t[1]}</p>
                </div>
              ))
            ) : (
              <>
                <div className="done">
                  <span>
                    <Icon name="check" size={14} />
                  </span>
                  <p>
                    自我介紹<small>已完成 · 01:18</small>
                  </p>
                </div>
                <div className="current">
                  <span>2</span>
                  <p>
                    個人經驗與能力<small>進行中 · 03:24</small>
                  </p>
                </div>
                <div>
                  <span>3</span>
                  <p>
                    申請動機與科系連結<small>尚未開始</small>
                  </p>
                </div>
              </>
            )}
          </div>
          <div className="device-status">
            <h3>裝置狀態</h3>
            <p>
              <Icon name="mic" size={17} />
              <span>麥克風</span>
              <Badge tone="green">正常</Badge>
            </p>
            {!free && (
              <p>
                <Icon name="camera" size={17} />
                <span>攝影機</span>
                <Badge tone="green">偵測中</Badge>
              </p>
            )}
          </div>
          {!free && (
            <div className="camera-preview">
              <div>
                <Icon name="user" size={34} />
              </div>
              <span>
                <i />
                畫面正常
              </span>
            </div>
          )}
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

function Report({ go, free = false }: { go: (p: Page) => void; free?: boolean }) {
  return (
    <AppShell page="history" go={go}>
      <PageTitle
        eyebrow="面試分析報告"
        title={free ? "基礎練習完成" : "你的準備，正在穩定進步"}
        desc={`${free ? "免費版基礎面試" : "國立臺灣大學 · 資訊管理學系"}　·　2026 年 3 月 8 日`}
        action={
          <div className="title-actions">
            <Button variant="secondary" onClick={() => go("dashboard")}>
              返回總覽
            </Button>
            <Button onClick={() => go(free ? "freeInterview" : "prepare")} icon="refresh">
              重新練習
            </Button>
          </div>
        }
      />
      <div className="simulation-report">
        <Icon name="alert" size={18} />
        <span>這是使用模擬資料產生的示範報告，並非真實 AI 評分或偵測結果。</span>
      </div>
      <div className="report-summary">
        <Card className="score-card">
          <div className="big-score">
            <span>
              <strong>{free ? "—" : "86"}</strong>
              {!free && <small>/ 100</small>}
            </span>
          </div>
          <div>
            <Badge tone="green">{free ? "已完成" : "表現優良"}</Badge>
            <h2>{free ? "完成 3 題基礎練習" : "整體表現穩定，回答具體有層次"}</h2>
            <p>
              {free
                ? "你能清楚傳達申請動機。以下基礎回饋可作為下一次練習方向。"
                : "善於以具體行動說明經驗，且與備審內容一致。若能更明確連結科系課程，說服力會更完整。"}
            </p>
          </div>
        </Card>
        <div className="stat-cards">
          <Card>
            <Icon name="clock" />
            <span>
              <small>面試時間</small>
              <strong>{free ? "06:42" : "14:36"}</strong>
            </span>
          </Card>
          <Card>
            <Icon name="mic" />
            <span>
              <small>完成題數</small>
              <strong>{free ? "3 / 3" : "11 題"}</strong>
            </span>
          </Card>
          <Card>
            <Icon name="chart" />
            <span>
              <small>{free ? "今日剩餘" : "面試等第"}</small>
              <strong>{free ? "2 場" : "A"}</strong>
            </span>
          </Card>
        </div>
      </div>
      {!free ? (
        <>
          <Card className="metrics-card">
            <div className="card-title">
              <div>
                <h2>四大評分指標</h2>
                <p>總分依文件指定權重計算</p>
              </div>
              <Badge tone="gray">加權總分 86</Badge>
            </div>
            <div className="metric-detail">
              {metricData.map((m) => (
                <div key={m[0]}>
                  <div>
                    <span>
                      {m[0]} <small>權重 {m[1]}</small>
                    </span>
                    <strong>{m[2]}</strong>
                  </div>
                  <Progress value={Number(m[2])} color={m[3] as "blue"} />
                </div>
              ))}
            </div>
          </Card>
          <div className="report-grid">
            <Card>
              <div className="card-title">
                <div>
                  <h2>回答完整度</h2>
                  <p>回答是否涵蓋足夠資訊與深度</p>
                </div>
                <strong className="section-score">88</strong>
              </div>
              {[
                ["個人特質完整度", 92],
                ["深度邏輯完整度", 84],
                ["經驗內容完整度", 87],
              ].map((x) => (
                <div className="submetric" key={x[0]}>
                  <span>
                    {x[0]}
                    <strong>{x[1]}</strong>
                  </span>
                  <Progress value={x[1] as number} />
                </div>
              ))}
            </Card>
            <Card>
              <div className="card-title">
                <div>
                  <h2>口語表達</h2>
                  <p>根據語音辨識資料分析</p>
                </div>
                <strong className="section-score amber">78</strong>
              </div>
              <div className="speech-grid">
                <span>
                  <small>平均語速</small>
                  <strong>每分鐘 186 字</strong>
                  <Badge tone="green">適中</Badge>
                </span>
                <span>
                  <small>明顯停頓</small>
                  <strong>7 次</strong>
                  <Badge tone="amber">可改善</Badge>
                </span>
                <span>
                  <small>常見贅字</small>
                  <strong>「然後」12 次</strong>
                </span>
                <span>
                  <small>時間掌握</small>
                  <strong>3 題接近上限</strong>
                </span>
              </div>
            </Card>
          </div>
          <Card className="topic-analysis">
            <div className="card-title">
              <div>
                <h2>各主題分析</h2>
                <p>檢視每個主題的回答表現與追問流程</p>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>主題名稱</th>
                  <th>回答時間</th>
                  <th>追問次數</th>
                  <th>相關度</th>
                  <th>追問終止原因</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <strong>自我介紹</strong>
                    <small>主問題 1 題</small>
                  </td>
                  <td>01:18</td>
                  <td>0 次</td>
                  <td>
                    <Badge tone="green">高</Badge>
                  </td>
                  <td>資訊完整，進入下一主題</td>
                </tr>
                <tr>
                  <td>
                    <strong>個人經驗與能力</strong>
                    <small>主問題 1 題</small>
                  </td>
                  <td>05:42</td>
                  <td>2 次</td>
                  <td>
                    <Badge tone="green">高</Badge>
                  </td>
                  <td>已達追問次數上限</td>
                </tr>
                <tr>
                  <td>
                    <strong>申請動機與科系連結</strong>
                    <small>主問題 1 題</small>
                  </td>
                  <td>04:26</td>
                  <td>1 次</td>
                  <td>
                    <Badge tone="amber">中</Badge>
                  </td>
                  <td>核心資訊已補充</td>
                </tr>
              </tbody>
            </table>
          </Card>
          <div className="report-grid">
            <Card>
              <div className="card-title">
                <div>
                  <h2>回答問題分析</h2>
                  <p>內容品質與備審資料對照</p>
                </div>
              </div>
              <div className="quality-list">
                <p>
                  <span className="ok">
                    <Icon name="check" size={15} />
                  </span>
                  <i>
                    <strong>是否離題</strong>
                    <small>11 題皆未明顯偏離題目</small>
                  </i>
                  <Badge tone="green">正常</Badge>
                </p>
                <p>
                  <span className="warn">
                    <Icon name="clock" size={15} />
                  </span>
                  <i>
                    <strong>是否超時</strong>
                    <small>1 題在時間結束時自動送出</small>
                  </i>
                  <Badge tone="amber">1 題</Badge>
                </p>
                <p>
                  <span className="ok">
                    <Icon name="check" size={15} />
                  </span>
                  <i>
                    <strong>備審內容是否矛盾</strong>
                    <small>未發現明顯矛盾</small>
                  </i>
                  <Badge tone="green">一致</Badge>
                </p>
              </div>
              <button className="source-link">
                查看對應備審來源 <Icon name="arrow" size={15} />
              </button>
            </Card>
            <Card>
              <div className="card-title">
                <div>
                  <h2>面部行為分析</h2>
                  <p>獨立呈現，不納入總分</p>
                </div>
                <Badge tone="blue">本次已完成偵測</Badge>
              </div>
              <div className="face-grid">
                {[
                  ["眼神方向", "正視畫面 78%"],
                  ["眨眼", "平均每分鐘 14 次"],
                  ["嘴唇相關行為", "未見明顯異常"],
                  ["頭部朝向", "大多保持正向"],
                  ["是否出現在畫面", "可辨識時間 96%"],
                ].map((x) => (
                  <span key={x[0]}>
                    <small>{x[0]}</small>
                    <strong>{x[1]}</strong>
                  </span>
                ))}
              </div>
              <p className="privacy-note">
                <Icon name="shield" size={15} />
                此區僅描述系統偵測到的畫面行為，不代表人格或能力判斷。
              </p>
            </Card>
          </div>
        </>
      ) : (
        <Card className="free-feedback">
          <div className="card-title">
            <div>
              <h2>本次回答紀錄</h2>
              <p>免費版僅提供文字紀錄、回答時間與基礎回饋</p>
            </div>
            <Badge tone="gray">未使用備審與動態追問</Badge>
          </div>
          {[
            ["自我介紹", "01:52", "回答能聚焦個人特質，例子具體。"],
            ["申請動機／校系認識", "02:14", "提到課程特色，建議再連結未來學習目標。"],
            ["常見面試問題", "02:36", "回答切題，但結尾可以更精簡。"],
          ].map((x, i) => (
            <div className="free-answer" key={x[0]}>
              <span>{i + 1}</span>
              <div>
                <strong>{x[0]}</strong>
                <p>
                  「
                  {i === 0
                    ? "教授您好，我是陳語晴。我喜歡從生活中發現問題，並嘗試用資料找到改善的方法……"
                    : "我選擇資訊管理學系，是因為希望結合資訊技術與組織管理……"}
                  」
                </p>
                <small>
                  <Icon name="clock" size={13} />
                  {x[1]}　·　基礎相關度：{i === 1 ? "中" : "高"}
                </small>
              </div>
              <p className="feedback-note">{x[2]}</p>
            </div>
          ))}
        </Card>
      )}
      <Card className="advice-card">
        <div className="card-title">
          <div>
            <h2>下一步改善建議</h2>
            <p>把回饋轉成可以執行的練習</p>
          </div>
          <Badge tone="purple">
            <Icon name="spark" size={13} />
            模擬建議
          </Badge>
        </div>
        <div className="advice-grid">
          <div className="good">
            <span>
              <Icon name="check" />
            </span>
            <h3>回答優點</h3>
            <ul>
              <li>能用具體情境說明個人特質</li>
              <li>語速穩定，重點表達清楚</li>
            </ul>
          </div>
          <div className="improve">
            <span>
              <Icon name="arrow" />
            </span>
            <h3>需要改善</h3>
            <ul>
              <li>申請動機可增加校系專屬連結</li>
              <li>減少「然後」等連接詞重複</li>
            </ul>
          </div>
          <div className="practice">
            <span>
              <Icon name="refresh" />
            </span>
            <h3>具體練習</h3>
            <ul>
              <li>用 60 秒說明「為何是這個科系」</li>
              <li>錄音後刪除不影響語意的贅字</li>
            </ul>
          </div>
          {!free && (
            <div className="content">
              <span>
                <Icon name="file" />
              </span>
              <h3>建議補強的經驗</h3>
              <ul>
                <li>補充個人負責比例與決策依據</li>
                <li>說明專案成果如何驗證</li>
              </ul>
            </div>
          )}
        </div>
      </Card>
      <div className="report-actions">
        <Button variant="secondary" onClick={() => go("history")}>
          查看面試紀錄
        </Button>
        <Button onClick={() => go(free ? "freeInterview" : "prepare")} icon="refresh">
          再練習一次
        </Button>
      </div>
    </AppShell>
  );
}

function History({ go }: { go: (p: Page) => void }) {
  const [grid, setGrid] = useState(false);
  const records = [
    ["2026 / 03 / 08", "國立臺灣大學", "資訊管理學系", "完整版", "14:36", "86"],
    ["2026 / 03 / 05", "國立政治大學", "資訊管理學系", "免費版", "06:42", "—"],
    ["2026 / 02 / 27", "國立臺灣大學", "資訊管理學系", "完整版", "16:08", "81"],
    ["2026 / 02 / 20", "國立清華大學", "科技管理學院", "免費版", "07:15", "—"],
  ];
  return (
    <AppShell page="history" go={go}>
      <PageTitle
        eyebrow="面試紀錄"
        title="每一次練習，都留下進步軌跡"
        desc="回顧過往回答與分析報告，找到下一次的練習重點。"
        action={
          <Button icon="plus" onClick={() => go("prepare")}>
            開始新的面試
          </Button>
        }
      />
      <div className="history-stats">
        <Card>
          <span>
            <Icon name="mic" />
          </span>
          <div>
            <small>累積面試</small>
            <strong>8 場</strong>
          </div>
        </Card>
        <Card>
          <span>
            <Icon name="clock" />
          </span>
          <div>
            <small>累積練習</small>
            <strong>1 小時 42 分</strong>
          </div>
        </Card>
        <Card>
          <span>
            <Icon name="chart" />
          </span>
          <div>
            <small>最佳成績</small>
            <strong>86 分</strong>
          </div>
        </Card>
        <Card>
          <span>
            <Icon name="arrow" />
          </span>
          <div>
            <small>近三次進步</small>
            <strong className="green-text">+ 7 分</strong>
          </div>
        </Card>
      </div>
      <Card className="history-card">
        <div className="history-toolbar">
          <div>
            <button className="active">全部</button>
            <button>完整版</button>
            <button>免費版</button>
          </div>
          <div className="view-switch">
            <button className={!grid ? "active" : ""} onClick={() => setGrid(false)}>
              <Icon name="list" size={17} />
            </button>
            <button className={grid ? "active" : ""} onClick={() => setGrid(true)}>
              <Icon name="grid" size={17} />
            </button>
          </div>
        </div>
        <div className={grid ? "record-grid" : "record-list"}>
          {records.map((r, i) => (
            <div className="record-row" key={r[0] + i}>
              <span className="record-date">
                <strong>{r[0]}</strong>
                <small>{i === 0 ? "最近一次" : ""}</small>
              </span>
              <span className="record-school">
                <i className="school-mini">{r[1].slice(2, 4)}</i>
                <span>
                  <strong>{r[1]}</strong>
                  <small>{r[2]}</small>
                </span>
              </span>
              <Badge tone={r[3] === "完整版" ? "purple" : "gray"}>{r[3]}</Badge>
              <span className="record-time">
                <Icon name="clock" size={15} />
                {r[4]}
              </span>
              <span className="record-score">
                {r[5] !== "—" && (
                  <>
                    <strong>{r[5]}</strong>
                    <small>/100</small>
                  </>
                )}{" "}
                {r[5] === "—" && <small>基礎回饋</small>}
              </span>
              <Button
                variant="secondary"
                onClick={() => go(r[3] === "完整版" ? "report" : "freeReport")}
              >
                查看報告
              </Button>
            </div>
          ))}
        </div>
      </Card>
    </AppShell>
  );
}

function Settings({ go }: { go: (p: Page) => void }) {
  const [tab, setTab] = useState("基本資料");
  return (
    <AppShell page="settings" go={go}>
      <PageTitle
        eyebrow="帳號設定"
        title="管理你的帳號"
        desc="更新個人資料、申請校系與登入設定。"
      />
      <div className="settings-layout">
        <Card className="settings-nav">
          {["基本資料", "申請校系管理", "帳號與安全"].map((x) => (
            <button className={tab === x ? "active" : ""} onClick={() => setTab(x)} key={x}>
              <Icon
                name={x === "基本資料" ? "user" : x === "申請校系管理" ? "school" : "shield"}
                size={18}
              />
              {x}
              <Icon name="chevron" size={15} />
            </button>
          ))}
          <div />
          <button className="logout-button" onClick={() => go("landing")}>
            <Icon name="logout" size={18} />
            登出
          </button>
        </Card>
        <Card className="settings-content">
          {tab === "基本資料" && (
            <>
              <div className="settings-heading">
                <h2>基本資料</h2>
                <p>這些資訊會顯示在你的學習空間中。</p>
              </div>
              <div className="profile-avatar">
                <span>陳</span>
                <div>
                  <Button variant="secondary">更換頭像</Button>
                  <small>支援 JPG、PNG，檔案上限 2MB</small>
                </div>
              </div>
              <div className="settings-form">
                <label>
                  姓名或暱稱
                  <input defaultValue="陳語晴" />
                </label>
                <label>
                  電子郵件
                  <input defaultValue="yuching@example.com" disabled />
                  <small>如需變更電子郵件，請聯絡客服。</small>
                </label>
              </div>
              <div className="form-actions">
                <Button>儲存變更</Button>
              </div>
            </>
          )}
          {tab === "申請校系管理" && (
            <>
              <div className="settings-heading">
                <h2>申請校系管理</h2>
                <p>目前已建立 2 / 6 組申請目標。</p>
              </div>
              <div className="setting-schools">
                <div>
                  <span>臺大</span>
                  <p>
                    <strong>國立臺灣大學</strong>
                    <small>資訊管理學系</small>
                  </p>
                  <Button variant="secondary" icon="edit">
                    編輯
                  </Button>
                </div>
                <div>
                  <span>政大</span>
                  <p>
                    <strong>國立政治大學</strong>
                    <small>資訊管理學系</small>
                  </p>
                  <Button variant="secondary" icon="edit">
                    編輯
                  </Button>
                </div>
              </div>
              <Button variant="secondary" icon="plus" onClick={() => go("profile")}>
                新增申請校系
              </Button>
            </>
          )}
          {tab === "帳號與安全" && (
            <>
              <div className="settings-heading">
                <h2>帳號與安全</h2>
                <p>管理密碼與帳號安全設定。</p>
              </div>
              <div className="security-row">
                <span>
                  <Icon name="shield" />
                </span>
                <div>
                  <strong>登入密碼</strong>
                  <p>上次更新於 2026 年 1 月 12 日</p>
                </div>
                <Button variant="secondary">變更密碼</Button>
              </div>
              <div className="danger-zone">
                <h3>刪除帳號</h3>
                <p>刪除後，所有面試紀錄與備審資料將無法復原。</p>
                <Button variant="danger">刪除我的帳號</Button>
              </div>
            </>
          )}
        </Card>
      </div>
    </AppShell>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("landing");
  const go = (next: Page) => {
    setPage(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const view = useMemo(() => {
    switch (page) {
      case "landing":
        return <Landing go={go} />;
      case "login":
        return <Auth mode="login" go={go} />;
      case "register":
        return <Auth mode="register" go={go} />;
      case "dashboard":
        return <Dashboard go={go} />;
      case "profile":
        return <Profile go={go} />;
      case "upload":
        return <Upload go={go} />;
      case "analysis":
        return <Analysis go={go} />;
      case "prepare":
        return <Prepare go={go} />;
      case "interview":
        return <Interview go={go} />;
      case "freeInterview":
        return <Interview go={go} free />;
      case "report":
        return <Report go={go} />;
      case "freeReport":
        return <Report go={go} free />;
      case "history":
        return <History go={go} />;
      case "settings":
        return <Settings go={go} />;
    }
  }, [page]);
  return view;
}
