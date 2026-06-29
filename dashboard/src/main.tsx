import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  Play,
  RefreshCcw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import "./styles.css";

const API_URL = import.meta.env.VITE_HEALER_API_URL ?? "http://localhost:8000";

type Health = {
  status: string;
  audit_backend: string;
  rag_embedding: string;
};

type AuditLog = {
  id: string;
  incident_id: string;
  service: string;
  alert_name: string;
  decision: string;
  confidence: number | null;
  selected_action: string | null;
  alert_resolved: boolean;
  received_at: string;
  completed_at: string | null;
  record: {
    diagnosis?: { root_cause?: string };
    execution?: { output?: string; status?: string };
    policy_gate?: { checks?: Record<string, unknown> };
  };
};

type QueueItem = {
  id: string;
  incident_id: string;
  service: string;
  alert_name: string;
  action: string;
  confidence: number;
  reasoning: string;
  status: string;
  created_at: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [message, setMessage] = useState("Ready");
  const [loading, setLoading] = useState(false);

  const stats = useMemo(() => {
    const resolved = audit.filter((item) => item.alert_resolved).length;
    const queued = queue.length;
    const auto = audit.filter((item) => item.decision === "auto_execute").length;
    const latestConfidence =
      audit.find((item) => item.confidence !== null)?.confidence ?? null;
    return { resolved, queued, auto, latestConfidence };
  }, [audit, queue]);

  async function refresh() {
    try {
      const [healthData, auditData, queueData] = await Promise.all([
        request<Health>("/health"),
        request<AuditLog[]>("/audit?limit=25"),
        request<QueueItem[]>("/approval/queue"),
      ]);
      setHealth(healthData);
      setAudit(auditData);
      setQueue(queueData);
      setMessage("Synced");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to sync");
    }
  }

  async function triggerDemo(service: string) {
    setLoading(true);
    try {
      await request("/demo/incident", {
        method: "POST",
        body: JSON.stringify({ service }),
      });
      setMessage(`Demo incident submitted for ${service}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Trigger failed");
    } finally {
      setLoading(false);
    }
  }

  async function decide(incidentId: string, status: "approved" | "rejected") {
    setLoading(true);
    try {
      await request("/approval/action", {
        method: "POST",
        body: JSON.stringify({ incident_id: incidentId, status }),
      });
      setMessage(`Action ${status}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Approval failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 8000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SRE control surface</p>
          <h1>Self-Healing Monitor</h1>
        </div>
        <div className="top-actions">
          <span className="status-line">{message}</span>
          <button className="icon-button" onClick={refresh} aria-label="Refresh">
            <RefreshCcw size={18} />
          </button>
        </div>
      </header>

      <section className="status-grid">
        <Metric title="API" value={health?.status ?? "offline"} icon={<Activity />} tone={health ? "good" : "warn"} />
        <Metric title="Audit backend" value={health?.audit_backend ?? "unknown"} icon={<Database />} />
        <Metric title="Queued" value={String(stats.queued)} icon={<Clock3 />} tone={stats.queued ? "warn" : "good"} />
        <Metric title="Auto-executed" value={String(stats.auto)} icon={<ShieldCheck />} />
        <Metric title="Resolved" value={String(stats.resolved)} icon={<CheckCircle2 />} tone="good" />
        <Metric
          title="Latest confidence"
          value={stats.latestConfidence === null ? "--" : `${Math.round(stats.latestConfidence * 100)}%`}
          icon={<AlertTriangle />}
        />
      </section>

      <section className="command-strip">
        <button disabled={loading} onClick={() => triggerDemo("leaky_service")}>
          <Play size={16} /> High memory demo
        </button>
        <button disabled={loading} onClick={() => triggerDemo("flaky_service")}>
          <Play size={16} /> Error-rate demo
        </button>
      </section>

      <section className="workspace">
        <div className="panel queue-panel">
          <div className="panel-heading">
            <h2>Approval Queue</h2>
            <span>{queue.length} pending</span>
          </div>
          <div className="list">
            {queue.length === 0 ? (
              <Empty text="No human approvals pending." />
            ) : (
              queue.map((item) => (
                <article className="queue-item" key={item.id}>
                  <div>
                    <strong>{item.alert_name}</strong>
                    <p>{item.service} wants {item.action}</p>
                    <small>{item.reasoning}</small>
                  </div>
                  <div className="decision-buttons">
                    <button onClick={() => decide(item.incident_id, "approved")} aria-label="Approve">
                      <CheckCircle2 size={16} /> Approve
                    </button>
                    <button className="danger" onClick={() => decide(item.incident_id, "rejected")} aria-label="Reject">
                      <XCircle size={16} /> Reject
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </div>

        <div className="panel audit-panel">
          <div className="panel-heading">
            <h2>Audit Log</h2>
            <span>{audit.length} recent</span>
          </div>
          <div className="timeline">
            {audit.length === 0 ? (
              <Empty text="No audit records yet." />
            ) : (
              audit.map((item) => (
                <article className="audit-row" key={item.id}>
                  <div className={`signal ${item.alert_resolved ? "resolved" : "open"}`} />
                  <div>
                    <div className="row-title">
                      <strong>{item.alert_name}</strong>
                      <span>{item.decision}</span>
                    </div>
                    <p>{item.record?.diagnosis?.root_cause ?? "No diagnosis recorded"}</p>
                    <small>
                      {item.service} · {item.selected_action ?? "no action"} · {new Date(item.received_at).toLocaleString()}
                    </small>
                  </div>
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

function Metric({
  title,
  value,
  icon,
  tone = "neutral",
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  tone?: "neutral" | "good" | "warn";
}) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}

createRoot(document.getElementById("root")!).render(<App />);
