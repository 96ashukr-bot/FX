import { useEffect, useState } from "react";
import { Activity, BarChart3, Copy, LayoutDashboard, Radio, Settings, ShieldCheck, WalletCards } from "lucide-react";
import { api } from "./api";

type Branding = { name: string; branding: { primary_color?: string; logo_url?: string } };
type Account = { id: string; platform: string; broker_name: string; login: string; connection_status: string; last_equity?: string };
type Intent = { id: string; canonical_symbol: string; side: string; state: string; requested_volume: string; created_at: string };

const navigation = [
  [LayoutDashboard, "Overview"], [WalletCards, "Accounts"], [Activity, "Orders & Positions"],
  [Radio, "Strategies"], [Copy, "Copy Trading"], [ShieldCheck, "Risk Controls"],
  [BarChart3, "Reports"], [Settings, "Settings"],
] as const;

export default function App() {
  const [branding, setBranding] = useState<Branding>({ name: "FX", branding: {} });
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [intents, setIntents] = useState<Intent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Branding>("/branding").then(setBranding).catch(() => undefined);
    if (localStorage.getItem("access_token")) {
      Promise.all([api<Account[]>("/accounts"), api<Intent[]>("/intents")])
        .then(([nextAccounts, nextIntents]) => { setAccounts(nextAccounts); setIntents(nextIntents); })
        .catch((reason) => setError(reason.message));
    }
  }, []);

  const connected = accounts.filter((item) => item.connection_status === "CONNECTED").length;
  const active = intents.filter((item) => ["QUEUED", "CLAIMED", "SUBMITTED", "ACCEPTED", "PARTIAL"].includes(item.state)).length;
  const primary = branding.branding.primary_color || "#57e0a1";

  return <div className="shell" style={{ "--brand": primary } as React.CSSProperties}>
    <aside>
      <div className="brand">
        {branding.branding.logo_url ? <img src={branding.branding.logo_url} alt="" /> : <span>FX</span>}
        <div><strong>{branding.name}</strong><small>Trading command centre</small></div>
      </div>
      <nav>{navigation.map(([Icon, label], index) => <button className={index === 0 ? "active" : ""} key={label}><Icon size={18} />{label}</button>)}</nav>
      <div className="node-health"><span className="pulse" /> Execution network operational</div>
    </aside>
    <main>
      <header><div><p>COMMAND CENTRE</p><h1>Trading overview</h1></div><button className="trade">New manual trade</button></header>
      {error && <div className="error">{error}</div>}
      <section className="metrics">
        <Metric label="Connected accounts" value={`${connected}/${accounts.length}`} meta="MT4 and MT5" />
        <Metric label="Active instructions" value={String(active)} meta="Across all accounts" />
        <Metric label="Execution state" value="Live" meta="Terminal gateway" positive />
        <Metric label="Risk engine" value="Armed" meta="Protection monitored" positive />
      </section>
      <section className="grid">
        <article className="panel accounts"><PanelTitle title="Trading accounts" action="Manage" />
          {accounts.length ? accounts.slice(0, 6).map((account) => <div className="account" key={account.id}>
            <span className={`platform ${account.platform.toLowerCase()}`}>{account.platform}</span>
            <div><strong>{account.broker_name}</strong><small>{account.login}</small></div>
            <span className={`status ${account.connection_status.toLowerCase()}`}>{account.connection_status}</span>
          </div>) : <Empty text="Connect an MT4 or MT5 terminal to begin." />}
        </article>
        <article className="panel activity"><PanelTitle title="Latest execution activity" action="View all" />
          {intents.length ? intents.slice(0, 7).map((intent) => <div className="intent" key={intent.id}>
            <span className={`side ${intent.side.toLowerCase()}`}>{intent.side}</span>
            <div><strong>{intent.canonical_symbol}</strong><small>{intent.requested_volume} lots</small></div>
            <span className="intent-state">{intent.state}</span>
          </div>) : <Empty text="Execution events will appear here." />}
        </article>
      </section>
    </main>
  </div>;
}

function Metric({ label, value, meta, positive = false }: { label: string; value: string; meta: string; positive?: boolean }) {
  return <article className="metric"><small>{label}</small><strong className={positive ? "positive" : ""}>{value}</strong><span>{meta}</span></article>;
}
function PanelTitle({ title, action }: { title: string; action: string }) { return <div className="panel-title"><h2>{title}</h2><button>{action}</button></div>; }
function Empty({ text }: { text: string }) { return <div className="empty">{text}</div>; }
