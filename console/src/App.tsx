import { Component, lazy, Suspense, useEffect, useState } from "react";
import { MotionConfig, motion } from "framer-motion";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  CircleHelp,
  ClipboardList,
  Gauge,
  LayoutDashboard,
  Menu,
  Maximize2,
  Minimize2,
  Network,
  Plug,
  ShieldCheck,
  X,
  Zap,
} from "lucide-react";
import {
  auditResult,
  auditWhat,
  isRecord,
  parseArray,
  parseIncidentId,
  serviceState,
  supportsConfidence,
  textValue,
  type UnknownRecord,
} from "./lib/api";
import {
  adaptIncident,
  adaptService,
  adaptServices,
  adaptStatus,
  adaptIncidents,
} from "./lib/api";
import { isFresh, TelemetryProvider, useTelemetry, useCurrentTelemetry } from "./lib/useTelemetry";
import { recordedResultsExcerpt } from "./lib/results";
import type { Sample } from "./lib/history";
const ThreeMap = lazy(() => import("./components/ThreeMap"));
const ScoreChart = lazy(() => import("./components/ScoreChart"));
const LiveIncident = lazy(() => import("./pages/LiveIncident"));
const Integrations = lazy(() => import("./pages/Integrations"));
const Charts = lazy(() => import("./components/ChartsSection"));
import PolicyRows from "./components/PolicyRows";
import { HowItWorks, LandingKpis } from "./components/LandingKpis";
import ReportProvider, { maskReportVendor } from "./components/ReportProvider";
import NumberTicker from "./components/NumberTicker";
import InvestigationTrace from "./components/InvestigationTrace";
import { newestActive } from "./lib/pipeline";
type Page =
  | "overview"
  | "live"
  | "integrations"
  | "incidents"
  | "topology"
  | "approvals"
  | "safety"
  | "audit"
  | "results";
const nav: {
  key: Page;
  label: string;
  icon: typeof LayoutDashboard;
  path: string;
}[] = [
  {
    key: "overview",
    label: "Overview",
    icon: LayoutDashboard,
    path: "/console",
  },
  { key: "live", label: "Live Incident", icon: Zap, path: "/console/live" },
  {
    key: "incidents",
    label: "Incidents",
    icon: Activity,
    path: "/console/incidents",
  },
  {
    key: "topology",
    label: "Topology",
    icon: Network,
    path: "/console/topology",
  },
  {
    key: "approvals",
    label: "Approvals",
    icon: ClipboardList,
    path: "/console/approvals",
  },
  {
    key: "safety",
    label: "Safety",
    icon: ShieldCheck,
    path: "/console/safety",
  },
  { key: "audit", label: "Audit", icon: CircleHelp, path: "/console/audit" },
  {
    key: "results",
    label: "Verified Results",
    icon: Gauge,
    path: "/console/results",
  },
  {
    key: "integrations",
    label: "Sources & Integrations",
    icon: Plug,
    path: "/console/integrations",
  },
];
function routeFromPath(
  path: string,
): { page: Page; incidentId?: string } | null {
  if (path === "/") return null;
  const clean = decodeURIComponent(path.replace(/\/$/, ""));
  const row = nav.find((x) => x.path === clean);
  if (row) return { page: row.key };
  const detail = clean.match(/^\/console\/incidents\/([^/]+)$/);
  if (detail) return { page: "incidents", incidentId: detail[1] };
  return { page: "overview" };
}
function useLocationPath() {
  const [path, setPath] = useState(location.pathname);
  useEffect(() => {
    const cb = () => setPath(location.pathname);
    addEventListener("popstate", cb);
    return () => removeEventListener("popstate", cb);
  }, []);
  return path;
}
export function App() {
  return (
    <MotionConfig reducedMotion="user">
      <TelemetryProvider>
        <AppShell />
      </TelemetryProvider>
    </MotionConfig>
  );
}
function AppShell() {
  const path = useLocationPath();
  const route = routeFromPath(path);
  const [mobile, setMobile] = useState(false);
  const [focus, setFocus] = useState(false);
  useEffect(() => {
    const exit = (event: KeyboardEvent) => { if (event.key === "Escape") setFocus(false); };
    window.addEventListener("keydown", exit);
    return () => window.removeEventListener("keydown", exit);
  }, []);
  useEffect(() => {
    if (!mobile) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobile(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobile]);
  if (!route) return <Landing />;
  const onNavigate = (e: React.MouseEvent<HTMLAnchorElement>) => {
    const href = e.currentTarget.getAttribute("href");
    if (href?.startsWith("/") && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      history.pushState({}, "", href);
      dispatchEvent(new PopStateEvent("popstate"));
      setMobile(false);
      window.scrollTo(0, 0);
    }
  };
  return (
    <div className={`layout ${focus ? "focus-layout" : ""}`}>
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <div className="sidebar-head">
          <a href="/" className="brand side-brand" onClick={onNavigate}>
            <span className="brand-mark">E</span>
            <span>EternalAI</span>
          </a>
          <button
            className="mobile-sidebar-close"
            aria-label="Close navigation"
            onClick={() => setMobile(false)}
          >
            <X size={16} />
          </button>
        </div>
        <div>
          <div className="nav-group-label">Operations</div>
          <nav className="nav-list" aria-label="Console navigation">
            {nav.map((item) => (
              <a
                key={item.key}
                href={item.path}
                onClick={onNavigate}
                className={`nav-link ${route.page === item.key ? "active" : ""}`}
                aria-current={route.page === item.key ? "page" : undefined}
              >
                <item.icon size={15} />
                {item.label}
              </a>
            ))}
          </nav>
        </div>
        <div className="sidebar-foot">
          Read-only · updates every 2 s
        </div>
      </aside>
      {mobile && <button className="nav-scrim" aria-label="Dismiss navigation" onClick={() => setMobile(false)} />}
      <main className="main">
        <header className="console-top">
          <button
            className="mobile-menu btn"
            aria-label={mobile ? "Close navigation" : "Open navigation"}
            aria-expanded={mobile}
            onClick={() => setMobile(!mobile)}
          >
            {mobile ? <X size={16} /> : <Menu size={16} />}
          </button>
          <a className="brand console-brand" href="/" onClick={onNavigate}>
            <span className="brand-mark">E</span>
            <span>EternalAI</span>
          </a>
          <span className="console-label">OPERATIONS CONSOLE</span>
          <button className="btn focus-toggle" aria-pressed={focus} onClick={() => { setFocus(!focus); setMobile(false); }}>
            {focus ? <Minimize2 size={15} /> : <Maximize2 size={15} />} {focus ? "Exit focus" : "Focus view"}
          </button>
        </header>
        <PageContent route={route} onNavigate={onNavigate} />
      </main>
    </div>
  );
}
function Brand() {
  return (
    <a href="/" className="brand">
      <span className="brand-mark">E</span>
      <span>EternalAI</span>
    </a>
  );
}
function Landing() {
  const { connection } = useTelemetry();
  const handle = (e: React.MouseEvent<HTMLAnchorElement>) => {
    const h = e.currentTarget.getAttribute("href");
    if (h?.startsWith("/")) {
      e.preventDefault();
      history.pushState({}, "", h);
      dispatchEvent(new PopStateEvent("popstate"));
      window.scrollTo(0, 0);
    }
  };
  return (
    <div className="landing">
      <header className="topbar">
        <div className="container topbar-inner">
          <Brand />
          <nav className="top-links" aria-label="Main navigation">
            <a className="desktop-only" href="#workflow">
              Workflow
            </a>
            <a className="desktop-only" href="#evidence">
              Evidence
            </a>
            <a href="/console" className="btn btn-primary" onClick={handle}>
              Open Console <ArrowRight size={14} />
            </a>
          </nav>
        </div>
      </header>
      <main>
        <section className="container hero">
          <div>
            <div className="eyebrow">EVIDENCE-LED OPERATIONS</div>
            <h1>
              Understand the <span className="mark">failure.</span> Inspect the response.
            </h1>
            <p>
              From the first anomaly to verified recovery. Follow the evidence,
              understand each decision, and see what changed.
            </p>
            <div className="hero-actions">
              <a href="/console/live" className="btn btn-primary" onClick={handle}>
                Open live console <ArrowRight size={15} />
              </a>
              <a href="/console/results" className="btn" onClick={handle}>
                View Verified Results
              </a>
            </div>
            <div className="hero-note">
              {connection === "live"
                ? "API telemetry is currently connected."
                : "Operational telemetry is available only when the API is connected."}
            </div>
            <LandingKpis />
          </div>
          <Architecture />
        </section>
        <section id="workflow" className="section">
          <div className="container">
            <div className="eyebrow">FROM SIGNAL TO EVIDENCE</div>
            <h2>Follow the incident, not just the alert.</h2>
            <HowItWorks />
            <p className="section-intro">
              The console brings together the information the service API
              reports: affected services, diagnostic evidence, proposed actions,
              policy decisions, and verification outcomes.
            </p>
            <div className="feature-grid">
              <Feature
                icon={<Activity size={17} />}
                title="Observe the state"
                body="Track service health and spot anomalies as they happen."
              />
              <Feature
                icon={<ClipboardList size={17} />}
                title="Inspect the decision"
                body="Inspect the evidence, proposed fix, and policy decision."
              />
              <Feature
                icon={<ArrowDownRight size={17} />}
                title="Review verification"
                body="Compare measurements before and after a fix."
              />
            </div>
          </div>
        </section>
        <section id="evidence" className="section">
          <div className="container">
            <div className="eyebrow">EVIDENCE & SAFETY</div>
            <h2>Visibility with boundaries.</h2>
            <p className="section-intro">
              The engine diagnoses and proposes fixes. Policy sets the boundaries.
              People approve protected actions. This console keeps the evidence visible.
            </p>
            <div className="safety-strip">
              <SafetyItem
                title="Read-only requests"
                text="Inspect incidents here. Approval and operating controls stay in your operator workflow."
              />
              <SafetyItem
                title="Unknown stays unknown"
                text="Missing fields are shown as unavailable, never converted to zero or a healthy state."
              />
              <SafetyItem
                title="Freshness is visible"
                text="Stale values are marked historical with the last successful update time."
              />
            </div>
          </div>
        </section>
        <section className="section">
          <div className="container closing">
            <div>
              <div className="eyebrow">INSPECT THE CURRENT STATE</div>
              <h2>Open the operations console.</h2>
              <p className="section-intro">
                Explore the live incident, inspect service dependencies, and review recovery evidence.
              </p>
            </div>
            <a href="/console" className="btn btn-primary" onClick={handle}>
              Open Console <ArrowRight size={15} />
            </a>
          </div>
        </section>
      </main>
      <footer className="footer">
        <div className="container footer-inner">
          <Brand />
          <span>Operational evidence, presented read-only.</span>
          <span className="source-badges" aria-label="Sources and integrations">
            <span>Prometheus</span>
            <span>Docker Compose</span>
            <span>Telegram</span>
            <span>LLM reports</span>
            <span>Kubernetes · validated offline</span>
          </span>
        </div>
      </footer>
    </div>
  );
}
function Architecture() {
  const [selected, setSelected] = useState("web");
  const notes: Record<string, string> = {
    web: "The storefront calls orders and inventory.",
    orders: "Orders coordinates payments and inventory.",
    inventory: "Inventory supplies stock availability.",
    payments: "Payments handles checkout authorization. Policy protects this service.",
  };
  return (
    <div className="architecture">
      <div className="arch-caption">
        Documented architecture
      </div>
      <svg
        className="arch-svg"
        viewBox="0 0 520 300"
        role="img"
        aria-label="Architecture illustration showing web depending on orders and inventory, with orders depending on payments and inventory"
      >
        <path
          className="arch-line"
          d="M258 73 L150 145 M258 73 L365 145 M150 190 L365 159 M150 190 L256 240"
        />
        <ArchNode x={205} y={34} w={106} title="web" sub="service" />
        <ArchNode x={96} y={132} w={106} title="orders" sub="service" />
        <ArchNode x={312} y={132} w={106} title="inventory" sub="service" />
        <ArchNode x={205} y={228} w={106} title="payments" sub="service" />
      </svg>
      <div className="architecture-controls" aria-label="Explore architecture">
        {Object.keys(notes).map((name) => <button className="tab" key={name} aria-pressed={selected === name} onClick={() => setSelected(name)}>{name}</button>)}
      </div>
      <p className="architecture-note" aria-live="polite">{notes[selected]}</p>
      <a className="text-link" href="/console/topology">Explore live topology <ArrowRight size={14} /></a>
    </div>
  );
}
function ArchNode({
  x,
  y,
  w,
  title,
  sub,
}: {
  x: number;
  y: number;
  w: number;
  title: string;
  sub: string;
}) {
  return (
    <g>
      <rect className="arch-node" x={x} y={y} width={w} height="54" rx="7" />
      <circle cx={x + 15} cy={y + 17} r="3" fill="#12b76a" />
      <text className="arch-label" x={x + 27} y={y + 21}>
        {title}
      </text>
      <text className="arch-sub" x={x + 14} y={y + 40}>
        {sub}
      </text>
    </g>
  );
}
function Feature({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <article className="feature-card">
      <div className="eyebrow">{icon}</div>
      <h3>{title}</h3>
      <p>{body}</p>
    </article>
  );
}
function SafetyItem({ title, text }: { title: string; text: string }) {
  return (
    <div className="safety-item">
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}
function ConnectionBadge() {
  const { connection, age } = useTelemetry();
  const labels = {
    connecting: "Connecting",
    live: `Live · updated ${age ?? 0}s ago`,
    partial: "Partial data",
    disconnected: "Disconnected · retrying",
  };
  return (
    <div className="connection" role="status">
      <span className={`dot ${connection}`} />
      {labels[connection]}
    </div>
  );
}
function PageContent({
  route,
  onNavigate,
}: {
  route: { page: Page; incidentId?: string };
  onNavigate: (e: React.MouseEvent<HTMLAnchorElement>) => void;
}) {
  const names: Record<Page, string> = {
    overview: "Overview",
    live: "Live Incident",
    integrations: "Sources & Integrations",
    incidents: "Incidents",
    topology: "Topology",
    approvals: "Approvals",
    safety: "Safety",
    audit: "Audit",
    results: "Verified Results",
  };
  return (
    <motion.div
      className="page"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="page-head">
        <div>
          <h1>{route.incidentId ? "Incident detail" : names[route.page]}</h1>
          <p>
            {route.incidentId
              ? "The evidence, decision, and measured outcome."
              : descriptions[route.page]}
          </p>
        </div>
        <ConnectionBadge />
      </div>
      {route.page === "overview" ? (
        <>
          <Overview onNavigate={onNavigate} />
          <Suspense fallback={<div className="empty">Loading charts…</div>}>
            <Charts />
          </Suspense>
        </>
      ) : route.page === "live" ? (
        <Suspense fallback={<div className="empty">Loading…</div>}>
          <LiveIncident />
        </Suspense>
      ) : route.page === "integrations" ? (
        <Suspense fallback={<div className="empty">Loading…</div>}>
          <Integrations />
        </Suspense>
      ) : route.page === "incidents" ? (
        <Incidents incidentId={route.incidentId} onNavigate={onNavigate} />
      ) : route.page === "topology" ? (
        <Topology />
      ) : route.page === "approvals" ? (
        <Approvals />
      ) : route.page === "safety" ? (
        <Safety />
      ) : route.page === "audit" ? (
        <Audit />
      ) : (
        <Results />
      )}
    </motion.div>
  );
}
const descriptions: Record<Page, string> = {
  overview:
    "Current operating mode, reported service state, and latest incident evidence.",
  live: "Follow detection, diagnosis, response, and verified recovery.",
  integrations: "Runtime, telemetry and integration facts, each with its source.",
  incidents: "Find an incident and follow the investigation.",
  topology:
    "Service dependencies returned by the API; links do not represent traffic.",
  approvals: "Items awaiting a human decision, as reported by the API.",
  safety: "Reported policy boundaries and kill-switch state.",
  audit: "A record of actions and verification outcomes.",
  results: "Recorded evaluation results from the repository source.",
};
function useEndpoint(
  key: "status" | "services" | "incidents" | "approvals" | "audit",
) {
  const { data } = useTelemetry();
  const item = data[key];
  return {
    item,
    current: !item.error && isFresh(item.updatedAt, Date.now()),
    value: item.value,
  };
}
function Historical({ stamp }: { stamp?: number }) {
  if (!stamp || !Number.isFinite(stamp) || isFresh(stamp, Date.now()))
    return null;
  return (
    <div className="notice" role="status">
      Historical data · last successful update{" "}
      {new Date(stamp).toLocaleTimeString()} · current values are unavailable.
    </div>
  );
}
function Unavailable({ label }: { label: string }) {
  return (
    <div className="empty">
      <strong>{label} unavailable</strong>Waiting for a valid response from the
      API.
    </div>
  );
}
function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="panel metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        <NumberTicker value={value} />
      </div>
      {hint && <div className="metric-hint">{hint}</div>}
    </div>
  );
}
function Overview({
  onNavigate,
}: {
  onNavigate: (e: React.MouseEvent<HTMLAnchorElement>) => void;
}) {
  const status = useEndpoint("status"),
    services = useEndpoint("services"),
    incidents = useEndpoint("incidents"),
    approvals = useEndpoint("approvals");
  const { samples } = useTelemetry();
  const s = isRecord(status.value) ? status.value : undefined;
  const statusModel = adaptStatus(status.value);
  const svc =
    isRecord(services.value) && isRecord(services.value.services)
      ? services.value.services
      : undefined;
  const inc = parseArray(incidents.value);
  const ap = parseArray(approvals.value);
  const open = statusModel?.openIncidents;
  const approvalsCount = ap?.length;
  const serviceEntries = svc ? Object.entries(svc) : [];
  const latest = adaptIncidents(incidents.value)
    ?.filter((item) => item.openedAt !== undefined)
    .sort((a, b) => (b.openedAt ?? 0) - (a.openedAt ?? 0))[0]?.raw;
  const reporting =
    status.current &&
    services.current &&
    incidents.current &&
    approvals.current;
  return (
    <>
      <Historical
        stamp={Math.min(
          ...([
            status.item.updatedAt,
            services.item.updatedAt,
            incidents.item.updatedAt,
            approvals.item.updatedAt,
          ].filter(Boolean) as number[]),
        )}
      />
      <div className="metric-grid">
        <Metric
          label="Operating mode"
          value={
            reporting ? (statusModel?.mode ?? "Not reported") : "Unavailable"
          }
          hint="Reported by /status"
        />
        <Metric
          label="Kill switch"
          value={
            reporting
              ? typeof s?.kill_switch === "boolean"
                ? s.kill_switch
                  ? "On"
                  : "Off"
                : "Not reported"
              : "Unavailable"
          }
          hint="No controls in this console"
        />
        <Metric
          label="Open incidents"
          value={
            reporting
              ? open === undefined
                ? "Not reported"
                : String(open)
              : "Unavailable"
          }
          hint="Reported by /status"
        />
        <Metric
          label="Pending approvals"
          value={
            reporting
              ? approvalsCount === undefined
                ? "Not reported"
                : String(approvalsCount)
              : "Unavailable"
          }
          hint="Returned approval records"
        />
      </div>
      <div className="content-grid">
        <section className="panel">
          <div className="panel-title">
            <h2>Service health</h2>
            <small>
              {reporting
                ? `${serviceEntries.length} returned services`
                : "Current state unavailable"}
            </small>
          </div>
          {!reporting || !svc ? (
            <Unavailable label="Service snapshots" />
          ) : (
            <div className="stack">
              {serviceEntries.map(([name, raw]) => (
                <ServiceRow
                  key={name}
                  name={name}
                  raw={raw}
                  samples={samples[name] ?? []}
                />
              ))}
            </div>
          )}
        </section>
        <section className="panel">
          <div className="panel-title">
            <h2>Current policy</h2>
            <small>Read-only</small>
          </div>
          {!reporting || !s ? (
            <Unavailable label="Policy details" />
          ) : (
            <PolicySummary status={s} />
          )}
        </section>
      </div>
      <section className="panel latest-panel">
        <div className="panel-title">
          <h2>Latest incident</h2>
          {latest && (
            <a
              className="text-link"
              href={`/console/incidents/${encodeURIComponent(String(latest.id ?? ""))}`}
              onClick={onNavigate}
            >
              Open details <ArrowRight size={12} />
            </a>
          )}
        </div>
        {!reporting ? (
          <Unavailable label="Latest incident" />
        ) : inc?.length === 0 ? (
          <div className="empty">
            <strong>No incidents reported</strong>The API returned an empty
            incident list.
          </div>
        ) : latest ? (
          <IncidentSummary incident={latest} />
        ) : (
          <div className="empty">
            <strong>Latest incident unavailable</strong>Returned incident
            records do not include a usable opened timestamp.
          </div>
        )}
      </section>
    </>
  );
}
function ServiceRow({
  name,
  raw,
  samples,
}: {
  name: string;
  raw: unknown;
  samples: Sample[];
}) {
  const service = adaptService(name, raw);
  const anomaly = service?.anomalous;
  const running = service?.running;
  const label =
    anomaly === true
      ? "Anomaly"
      : running === false
        ? "Not running"
        : anomaly === false
          ? "No anomaly reported"
          : running === true
            ? "Running"
            : "Not reported";
  const cls =
    anomaly === true || running === false
      ? "red"
      : anomaly === false || running === true
        ? "green"
        : "";
  return (
    <div className="service-row">
      <div className="service-primary">
        <div className="service-name">{service?.name ?? name}</div>
        <div className="service-meta">
          {service?.score !== undefined
            ? `Score ${service.score}`
            : "No score reported"}
        </div>
        {samples.filter((sample) => sample.value !== null).length >= 2 && (
          <Suspense fallback={<div className="service-chart" />}>
            <ScoreChart samples={samples} name={service?.name ?? name} />
          </Suspense>
        )}
      </div>
      <span className={`badge ${cls}`}>{label}</span>
    </div>
  );
}
function PolicySummary({ status }: { status: UnknownRecord }) {
  const model = adaptStatus(status);
  return (
    <div className="stack">
      <div className="service-row">
        <span className="service-name">Mode</span>
        <span className="badge cyan">{model?.mode ?? "Not reported"}</span>
      </div>
      <div className="service-row">
        <span className="service-name">Kill switch</span>
        <span className={`badge ${model?.killSwitch === true ? "red" : ""}`}>
          {typeof model?.killSwitch === "boolean"
            ? model.killSwitch
              ? "On"
              : "Off"
            : "Not reported"}
        </span>
      </div>
      <div>
        <div className="metric-label">Rulebook summary</div>
        <div style={{ marginTop: 8 }}>
          <PolicyRows policy={model?.policy} />
        </div>
      </div>
      <div>
        <div className="metric-label">Protected services</div>
        <div className="report" style={{ marginTop: 6 }}>
          {model?.protectedServices
            ? model.protectedServices.join(", ") || "None reported"
            : "Not reported"}
        </div>
      </div>
    </div>
  );
}
function IncidentSummary({ incident }: { incident: UnknownRecord }) {
  const model = adaptIncident(incident);
  return (
    <div className="incident-summary">
      <div className="summary-head">
        <div>
          <div className="summary-id">
            {model.id ?? "Incident ID not reported"}
          </div>
          <div className="summary-sub">
            {model.kind ?? "Type not reported"} · {formatTime(model.openedAt)}
          </div>
        </div>
        <StatusBadge value={model.status} />
      </div>
      <p className="summary-cause">
        Likely cause · {model.likelyCause ?? "Not reported"}
      </p>
      <div className="chip-row">
        {model.services ? (
          model.services.map((name) => (
            <span key={name} className="badge">
              {name}
            </span>
          ))
        ) : (
          <span className="muted">Affected services not reported</span>
        )}
      </div>
    </div>
  );
}
function StatusBadge({ value }: { value: unknown }) {
  const s = textValue(value);
  const cls = s?.includes("awaiting")
    ? "amber"
    : s?.includes("closed")
      ? "green"
      : s?.includes("open")
        ? "red"
        : "";
  return <span className={`badge ${cls}`}>{s ?? "Status not reported"}</span>;
}
class WebGLErrorBoundary extends Component<
  { onFailure: () => void; children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onFailure();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
function formatTime(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value))
    return "Time not reported";
  return new Date(value * 1000).toLocaleString();
}
function Incidents({
  incidentId,
  onNavigate,
}: {
  incidentId?: string;
  onNavigate: (e: React.MouseEvent<HTMLAnchorElement>) => void;
}) {
  const source = useEndpoint("incidents");
  const rows = parseArray(source.value);
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("");
  const { data } = useTelemetry();
  const canConfidence =
    !data.status.error &&
    isFresh(data.status.updatedAt, Date.now()) &&
    supportsConfidence(data.status.value);
  const selected = incidentId
    ? rows?.find((i) => parseIncidentId(i) === incidentId)
    : undefined;
  const filtered = rows?.filter((i) => {
    const q = query.toLowerCase();
    const hay = [
      i.id,
      i.status,
      i.kind,
      i.likely_cause,
      ...(Array.isArray(i.services) ? i.services : []),
    ]
      .map(String)
      .join(" ")
      .toLowerCase();
    return (
      (!q || hay.includes(q)) && (!filter || String(i.status ?? "") === filter)
    );
  });
  if (incidentId)
    return (
      <>
        {!source.current && <Historical stamp={source.item.updatedAt} />}
        <section className="panel">
          <div className="panel-title">
            <a
              href="/console/incidents"
              className="text-link"
              onClick={onNavigate}
            >
              ← All incidents
            </a>
            {selected && <StatusBadge value={selected.status} />}
          </div>
          {!source.current || !rows ? (
            <Unavailable label="Incident record" />
          ) : !selected ? (
            <div className="empty">
              <strong>Incident not found</strong>This identifier is not present
              in the current API response.
            </div>
          ) : (
            <IncidentNarrative
              incident={selected}
              canConfidence={canConfidence}
            />
          )}
        </section>
      </>
    );
  return (
    <>
      {!source.current && <Historical stamp={source.item.updatedAt} />}
      <section className="panel">
        <div className="filter-row">
          <label className="sr-only" htmlFor="incident-search">
            Filter incidents
          </label>
          <input
            id="incident-search"
            className="search"
            placeholder="Search returned incidents"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <label className="sr-only" htmlFor="status-filter">
            Filter by incident status
          </label>
          <select
            id="status-filter"
            className="search filter-select"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">All returned statuses</option>
            {[
              ...new Set(
                (rows ?? [])
                  .map((x) => textValue(x.status))
                  .filter((x): x is string => !!x),
              ),
            ].map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </div>
        {!source.current || !rows ? (
          <Unavailable label="Incidents" />
        ) : filtered!.length === 0 ? (
          <div className="empty">
            <strong>No matching incidents</strong>The API returned no records
            matching this filter.
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Incident</th>
                  <th>Status</th>
                  <th>Services</th>
                  <th>Cause</th>
                  <th>Opened</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered!.map((item, index) => (
                  <tr key={String(item.id ?? index)}>
                    <td>
                      {textValue(item.id) ?? "ID not reported"}
                      <div className="muted">
                        {textValue(item.kind) ?? "Type not reported"}
                      </div>
                    </td>
                    <td>
                      <StatusBadge value={item.status} />
                    </td>
                    <td>
                      {Array.isArray(item.services)
                        ? item.services
                            .filter((x) => typeof x === "string")
                            .join(", ") || "None reported"
                        : "Not reported"}
                    </td>
                    <td>{textValue(item.likely_cause) ?? "Not reported"}</td>
                    <td>{formatTime(item.opened_t)}</td>
                    <td>
                      <a
                        className="text-link"
                        href={`/console/incidents/${encodeURIComponent(String(item.id ?? ""))}`}
                        onClick={onNavigate}
                      >
                        Inspect <ArrowRight size={12} />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
function IncidentNarrative({
  incident,
  canConfidence,
}: {
  incident: UnknownRecord;
  canConfidence: boolean;
}) {
  const model = adaptIncident(incident);
  const evidence = parseArray(incident.evidence);
  const actions = parseArray(incident.actions);
  const timeline = parseArray(incident.timeline);
  const verification = isRecord(incident.verification)
    ? incident.verification
    : undefined;
  const diagnosis = isRecord(incident.diagnosis)
    ? incident.diagnosis
    : undefined;
  const report = isRecord(incident.report) ? incident.report : undefined;
  return (
    <>
      <div className="detail-overview">
        <div>
          <div className="eyebrow">
            {textValue(incident.kind) ?? "INCIDENT"}
          </div>
          <h2 className="detail-title">
            {model.likelyCause ?? "Cause not reported"}
          </h2>
          <div className="muted">
            {model.id ?? "Incident ID not reported"} · opened{" "}
            {formatTime(model.openedAt)}
          </div>
        </div>
        <StatusBadge value={incident.status} />
      </div>
      <div className="chip-row">
        {Array.isArray(incident.services) ? (
          incident.services
            .filter((x) => typeof x === "string")
            .map((x) => (
              <span className="badge" key={x}>
                {x}
              </span>
            ))
        ) : (
          <span className="muted">Affected services not reported</span>
        )}
        {canConfidence && typeof incident.confidence === "number" && (
          <span className="badge cyan">
            Confidence {Math.round(incident.confidence * 100)}%
          </span>
        )}
      </div>
      <div className="narrative-grid">
        <NarrativeBlock
          title="Observed issue"
          body={
            diagnosis
              ? displayFields(diagnosis)
              : (textValue(incident.likely_cause) ?? "Not reported")
          }
        />
        <NarrativeBlock
          title="Evidence"
          body={
            evidence?.length
              ? evidence.map((e, i) => (
                  <div className="evidence-row" key={String(e.id ?? i)}>
                    <strong>{textValue(e.tool) ?? "Evidence"}</strong>
                    <span>
                      {textValue(e.service) ?? "Service not reported"}
                    </span>
                    <p>{textValue(e.summary) ?? "Summary not reported"}</p>
                  </div>
                ))
              : "Not reported"
          }
        />
        <NarrativeBlock
          title="Proposed action"
          body={
            actions?.length
              ? actions.map((a, i) => (
                  <div className="evidence-row" key={i}>
                    <strong>
                      {textValue(a.runbook_id) ??
                        textValue(a.action) ??
                        "Action not named"}
                    </strong>
                    <span>
                      {textValue(a.verdict) ??
                        textValue(a.status) ??
                        "Decision not reported"}
                    </span>
                    <p>{displayFields(a)}</p>
                  </div>
                ))
              : "Not reported"
          }
        />
        <NarrativeBlock
          title="Policy decision & approval"
          body={
            actions?.length
              ? actions.map((a, i) => (
                  <div className="evidence-row" key={i}>
                    <strong>
                      {textValue(a.verdict) ?? "Verdict not reported"}
                    </strong>
                    <p>
                      {textValue(a.approved_by) ?? "Approver not reported"} ·{" "}
                      {textValue(a.reason) ?? "Reason not reported"}
                    </p>
                  </div>
                ))
              : "Not reported"
          }
        />
        <NarrativeBlock
          title="Verification result"
          body={verification ? displayFields(verification) : "Not reported"}
        />
        <NarrativeBlock
          title="Report"
          body={
            report
              ? displayFields(report)
              : (textValue(incident.report) ?? "Not reported")
          }
        />
        <ReportProvider meta={incident.report_meta} />
      </div>
      <InvestigationTrace incident={incident} />
      <div className="panel-subsection">
        <div className="panel-title">
          <h2>Incident timeline</h2>
          <small>API order preserved</small>
        </div>
        {timeline?.length ? (
          <div className="timeline">
            {timeline.map((t, i) => (
              <div className="timeline-item" key={i}>
                <h3>{maskReportVendor(textValue(t.msg) ?? "Event detail not reported")}</h3>
                {typeof t.t === "number" && <p>{formatTime(t.t)}</p>}
              </div>
            ))}
          </div>
        ) : (
          <div className="muted">Timeline not reported</div>
        )}
      </div>
    </>
  );
}
function displayFields(value: UnknownRecord): string {
  const entries = Object.entries(value).filter(
    ([, v]) => v !== null && v !== undefined,
  );
  return entries.length
    ? entries
        .map(
          ([k, v]) =>
            `${k.replaceAll("_", " ")}: ${typeof v === "string" || typeof v === "number" || typeof v === "boolean" ? String(v) : JSON.stringify(v)}`,
        )
        .join("\n")
    : "Not reported";
}
function NarrativeBlock({
  title,
  body,
}: {
  title: string;
  body: string | React.ReactNode;
}) {
  return (
    <section className="narrative-block">
      <h3>{title}</h3>
      <div className="narrative-body">
        {typeof body === "string" ? body : body}
      </div>
    </section>
  );
}
function Topology() {
  const source = useEndpoint("services");
  const payload = isRecord(source.value) ? source.value : undefined;
  const services = isRecord(payload?.services) ? payload.services : undefined;
  const topology = isRecord(payload?.topology) ? payload.topology : undefined;
  const names =
    adaptServices(source.value)?.map((service) => service.name) ?? [];
  const links: [string, string][] = [];
  if (topology)
    Object.entries(topology).forEach(([a, raw]) => {
      if (Array.isArray(raw))
        raw.forEach((b) => {
          if (typeof b === "string") links.push([a, b]);
        });
    });
  const [selected, setSelected] = useState<string>();
  const [view, setView] = useState<"2d" | "3d">("2d");
  const { data: liveData } = useCurrentTelemetry();
  const selectedData = selected && services ? services[selected] : undefined;
  const positions = names.map((name, i) => {
    const angle = (i / Math.max(names.length, 1)) * Math.PI * 2;
    return {
      name,
      x: 300 + Math.cos(angle) * 190,
      y: 190 + Math.sin(angle) * 120,
    };
  });
  const pos = (name: string) => positions.find((p) => p.name === name);
  return (
    <>
      <Historical stamp={source.item.updatedAt} />
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Service dependencies</h2>
            <small>Dependency links describe architecture, not traffic.</small>
          </div>
          {source.current && services && topology && (
            <div className="tabs" aria-label="Topology view">
              {(["2d", "3d"] as const).map((v) => (
                <button
                  key={v}
                  className="tab"
                  aria-pressed={view === v}
                  onClick={() => setView(v)}
                >
                  {v.toUpperCase()}
                </button>
              ))}
            </div>
          )}
        </div>
        {!source.current || !services || !topology ? (
          <Unavailable label="Topology" />
        ) : (
          <>
            <div className="topology-stage">
              {view === "2d" ? (
                <svg
                  className="topology-canvas"
                  viewBox="0 0 600 380"
                  role="img"
                  aria-label="Service dependency map returned by the API"
                >
                  {links.map(([a, b], i) => {
                    const p = pos(a),
                      q = pos(b);
                    return p && q ? (
                      <line
                        key={i}
                        x1={p.x}
                        y1={p.y}
                        x2={q.x}
                        y2={q.y}
                        className="topology-link"
                      />
                    ) : null;
                  })}
                  {positions.map(({ name, x, y }) => {
                    const state = serviceState(services?.[name]);
                    const stateLabel =
                      state === "down"
                        ? "not running"
                        : state === "anomaly"
                          ? "anomaly reported"
                          : state === "ok"
                            ? "no anomaly reported"
                            : "reported service";
                    const dot =
                      state === "down"
                        ? "#f04438"
                        : state === "anomaly"
                          ? "#f79009"
                          : state === "ok"
                            ? "#39ff14"
                            : "#8a948f";
                    return (
                    <g
                      key={name}
                      data-state={state}
                      onClick={() => setSelected(name)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelected(name);
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      aria-label={`Select service ${name}`}
                      className="topology-node"
                    >
                      <rect
                        x={x - 54}
                        y={y - 23}
                        width="108"
                        height="46"
                        rx="7"
                        className={[
                          selected === name ? "node-selected" : "",
                          state === "down" || state === "anomaly"
                            ? `node-${state}`
                            : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      />
                      <circle cx={x - 37} cy={y - 6} r="3" fill={dot} />
                      <text x={x - 25} y={y - 2}>
                        {name}
                      </text>
                      <text className="topology-node-sub" x={x - 37} y={y + 13}>
                        {stateLabel}
                      </text>
                    </g>
                    );
                  })}
                </svg>
              ) : (
                <Suspense
                  fallback={
                    <div className="empty">Loading lightweight 3D map…</div>
                  }
                >
                  <WebGLErrorBoundary onFailure={() => setView("2d")}>
                    <ThreeMap
                      names={names}
                      selected={selected}
                      onSelect={setSelected}
                      topology={topology}
                      states={Object.fromEntries(names.map((n) => [n, serviceState(services?.[n])]))}
                      root={(() => {
                        const inc = newestActive(liveData.incidents.value);
                        const r = inc && inc.abstained !== true && Array.isArray(inc.ranking) ? inc.ranking[0] : undefined;
                        return isRecord(r) ? textValue(r.service) : undefined;
                      })()}
                      incidentOpen={!!newestActive(liveData.incidents.value)}
                    />
                  </WebGLErrorBoundary>
                </Suspense>
              )}
            </div>
            <div className="topology-legend">
              <span>Service nodes are API-reported</span>
              <span>Lines are returned dependencies</span>
              <span>{view === "3d" ? "Drag to rotate · select a node" : "Select a node to inspect"}</span>
            </div>
            <div className="topology-detail">
              <div className="panel-title">
                <h2>{selected ?? "Select a service"}</h2>
                <small>Read-only service detail</small>
              </div>
              {selected ? (
                selectedData ? (
                  <ServiceDetail raw={selectedData} />
                ) : (
                  <div className="muted">Service details unavailable</div>
                )
              ) : (
                <div className="muted">
                  Select a node or choose from the service list below.
                </div>
              )}
            </div>
            <div className="service-select-list" aria-label="Services">
              {names.map((n) => (
                <button
                  key={n}
                  className="tab"
                  aria-pressed={selected === n}
                  onClick={() => setSelected(n)}
                >
                  {n}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}
function ServiceDetail({ raw }: { raw: unknown }) {
  const r = isRecord(raw) ? raw : undefined;
  return (
    <dl className="detail-list">
      {[
        [
          "Anomaly",
          typeof r?.anomalous === "boolean"
            ? r.anomalous
              ? "Reported"
              : "Not reported"
            : "Not reported",
        ],
        [
          "Score",
          typeof r?.score === "number" ? String(r.score) : "Not reported",
        ],
        [
          "Features",
          isRecord(r?.features) ? JSON.stringify(r.features) : "Not reported",
        ],
        [
          "Runtime state",
          isRecord(r?.state) ? JSON.stringify(r.state) : "Not reported",
        ],
      ].map(([k, v]) => (
        <div key={String(k)}>
          <dt>{String(k)}</dt>
          <dd>{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}
function Approvals() {
  const source = useEndpoint("approvals");
  const rows = parseArray(source.value);
  return (
    <>
      <Historical stamp={source.item.updatedAt} />
      <div className="notice" style={{ marginBottom: 14 }}>
        Approve or reject through your operator dashboard or configured Telegram bot.
      </div>
      <section className="panel">
        <div className="panel-title">
          <h2>Pending approvals</h2>
          <small>
            {source.current && rows
              ? `${rows.length} returned items`
              : "Unavailable"}
          </small>
        </div>
        {!source.current || !rows ? (
          <Unavailable label="Approval queue" />
        ) : rows.length === 0 ? (
          <div className="empty">
            <strong>No pending approvals reported</strong>The API returned an
            empty approval list.
          </div>
        ) : (
          <div className="approval-grid">
            {rows.map((a, i) => (
              <article
                className="approval-card"
                key={String(a.incident_id ?? i)}
              >
                <div className="summary-head">
                  <strong>
                    {textValue(a.incident_id) ?? "Incident ID not reported"}
                  </strong>
                  <span className="badge amber">Awaiting review</span>
                </div>
                <dl className="detail-list">
                  {[
                    ["Service", a.service],
                    ["Runbook", a.runbook_id],
                    ["Risk", a.risk],
                    ["Reason", a.reason],
                    ["Cause", a.cause],
                  ].map(([k, v]) => (
                    <div key={String(k)}>
                      <dt>{String(k)}</dt>
                      <dd>{textValue(v) ?? "Not reported"}</dd>
                    </div>
                  ))}
                </dl>
                {textValue(a.report) && (
                  <p className="report">{textValue(a.report)}</p>
                )}
                <p className="muted">
                  Expiry time not reported · no countdown shown
                </p>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
function Safety() {
  const source = useEndpoint("status");
  const s = isRecord(source.value) ? source.value : undefined;
  const policy = isRecord(s?.policy) ? s.policy : undefined;
  return (
    <>
      <Historical stamp={source.item.updatedAt} />
      {!source.current || !s ? (
        <section className="panel">
          <Unavailable label="Safety policy" />
        </section>
      ) : (
        <>
          <div className="notice" style={{ marginBottom: 14 }}>
            Observational policy view. No policy or kill-switch controls are
            available here.
          </div>
          <div className="metric-grid">
            <Metric
              label="Mode"
              value={textValue(s.mode) ?? "Not reported"}
              hint="Reported by /status"
            />
            <Metric
              label="Kill switch"
              value={
                typeof s.kill_switch === "boolean"
                  ? s.kill_switch
                    ? "On"
                    : "Off"
                  : "Not reported"
              }
              hint="Read-only state"
            />
            <Metric
              label="Probability display"
              value={supportsConfidence(s) ? "Permitted" : "Not permitted"}
              hint="Calibration API flag"
            />
            <Metric
              label="Protected services"
              value={
                Array.isArray(s.protected_services)
                  ? String(s.protected_services.length)
                  : "Not reported"
              }
              hint="Count of returned names"
            />
          </div>
          <section className="panel" style={{ marginTop: 12 }}>
            <div className="panel-title">
              <h2>Rulebook summary</h2>
              <small>From /status → policy</small>
            </div>
            {policy ? (
              <PolicyRows policy={policy} />
            ) : (
              <div className="empty">Policy details not reported</div>
            )}
            <div className="panel-title" style={{ marginTop: 22 }}>
              <h2>Protected services</h2>
            </div>
            {Array.isArray(s.protected_services) ? (
              s.protected_services.map((x, i) => (
                <span className="badge" key={i}>
                  {typeof x === "string" ? x : "Unrecognized value"}
                </span>
              ))
            ) : (
              <span className="muted">Not reported</span>
            )}
          </section>
        </>
      )}
    </>
  );
}
function Audit() {
  const source = useEndpoint("audit");
  const rows = parseArray(source.value);
  return (
    <>
      <Historical stamp={source.item.updatedAt} />
      <section className="panel">
        <div className="panel-title">
          <h2>Recent audit records</h2>
          <small>API returns the most recent bounded records</small>
        </div>
        {!source.current || !rows ? (
          <Unavailable label="Audit log" />
        ) : rows.length === 0 ? (
          <div className="empty">
            <strong>No audit records returned</strong>The API returned an empty
            audit list.
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Who</th>
                  <th>What</th>
                  <th>When</th>
                  <th>Result</th>
                  <th>Record</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td>
                      {textValue(r.approver) ??
                        textValue(r.actor) ??
                        textValue(r.who) ??
                        "Not reported"}
                    </td>
                    <td>{auditWhat(r) ?? "Not reported"}</td>
                    <td>
                      {formatTime(typeof r.t === "number" ? r.t : r.timestamp)}
                    </td>
                    <td>{auditResult(r) ?? "Not reported"}</td>
                    <td>
                      <pre className="audit-record">
                        {JSON.stringify(r, null, 2)}
                      </pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
function Results() {
  const excerpt = recordedResultsExcerpt();
  return (
    <>
      <div className="notice" style={{ marginBottom: 14 }}>
        Recorded repository results · not live telemetry. Source:
        docs/CURRENT_NUMBERS.md at integration source commit
        7cc615a48d8378dcf781b4f7e3deb428c16654c7.
      </div>
      <section className="panel">
        <div className="panel-title">
          <h2>Verified results</h2>
          <small>
            Selected source sections, labels and qualifiers preserved
          </small>
        </div>
        {excerpt ? (
          <div className="numbers-source">
            <SourceDocument source={excerpt} />
          </div>
        ) : (
          <div className="empty">
            <strong>Recorded results unavailable</strong>The source file did not
            contain the expected sections.
          </div>
        )}
      </section>
    </>
  );
}
function SourceDocument({ source }: { source: string }) {
  const lines = source.split(/\r?\n/);
  return (
    <div className="source-document">
      {lines.map((line, index) => {
        if (!line.trim()) return null;
        const heading = /^(#{1,3})\s+(.+)$/.exec(line);
        if (heading) {
          const Tag = heading[1].length === 1 ? "h3" : "h4";
          return <Tag key={index}>{inlineSource(heading[2])}</Tag>;
        }
        const bullet = /^(\s*)-\s*(.*)$/.exec(line);
        if (bullet && bullet[2].trim())
          return (
            <div
              className={`source-bullet ${bullet[1].length ? "nested" : ""}`}
              key={index}
            >
              <span aria-hidden="true">·</span>
              <span>{inlineSource(bullet[2])}</span>
            </div>
          );
        return <p key={index}>{inlineSource(line)}</p>;
      })}
    </div>
  );
}
function inlineSource(value: string) {
  return value.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`"))
      return <code key={index}>{part.slice(1, -1)}</code>;
    return part;
  });
}
