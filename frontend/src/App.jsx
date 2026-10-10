import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import FlowMap from "./FlowMap.jsx";

const API = (path, options) => fetch(`/api${path}`, options).then(async (response) => {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
});

const INCIDENTS = {
  stopped_vehicle: { label: "Stopped vehicle", icon: "Ⅱ", color: "amber" },
  congestion: { label: "Traffic congestion", icon: "≋", color: "orange" },
  collision: { label: "Possible collision", icon: "⚠", color: "red" },
  wrong_way: { label: "Wrong-way driving", icon: "↶", color: "violet" },
};
const TABS = {
  Active: (i) => i.status === "ACTIVE",
  Acknowledged: (i) => i.status === "ACKNOWLEDGED",
  History: (i) => ["RESOLVED", "FALSE_POSITIVE"].includes(i.status),
};
const fmtTime = (value) => value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
const pct = (value) => `${Math.round((Number(value) || 0) * 100)}%`;

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [status, setStatus] = useState(null);
  const [tab, setTab] = useState("Active");
  const [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const fileRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [nextIncidents, nextStatus] = await Promise.all([API("/incidents"), API("/status")]);
      setIncidents(Array.isArray(nextIncidents) ? nextIncidents : []);
      setStatus(nextStatus);
      setLastUpdated(new Date());
      setError("");
    } catch (e) {
      setError("Backend is not connected. Start the FlowGuard API on port 8000.");
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 1800);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const act = async (id, action) => {
    setBusy(true);
    try {
      await API(`/incidents/${id}/${action}`, { method: "POST" });
      await refresh();
    } catch (e) { setError(e.message || "Could not update this incident."); }
    finally { setBusy(false); }
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".mp4")) {
      setError("Please choose an MP4 video file.");
      event.target.value = "";
      return;
    }
    const form = new FormData();
    form.append("file", file);
    setBusy(true);
    try {
      const response = await fetch("/api/upload", { method: "POST", body: form });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || "Upload failed.");
      setError("");
      await refresh();
    } catch (e) { setError(e.message || "Video upload failed."); }
    finally { setBusy(false); event.target.value = ""; }
  };

  const visible = useMemo(() => incidents.filter(TABS[tab]).filter((i) => {
    const meta = INCIDENTS[i.type] || { label: i.type || "Incident" };
    const haystack = `${meta.label} ${i.type} ${i.status} ${i.why} ${i.id}`.toLowerCase();
    return haystack.includes(query.toLowerCase());
  }), [incidents, tab, query]);
  const selected = incidents.find((i) => i.id === selectedId);
  const activeCount = incidents.filter((i) => i.status === "ACTIVE").length;
  const acknowledgedCount = incidents.filter((i) => i.status === "ACKNOWLEDGED").length;
  const highCount = incidents.filter((i) => i.severity === "HIGH" && ["ACTIVE", "ACKNOWLEDGED"].includes(i.status)).length;
  const vehicleCount = status?.vehicles ?? 0;
  const visibility = Number(status?.visibility ?? 0);
  const isCalibrating = status?.calibrating;

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><span>F</span><i /></div><div><strong>FlowGuard</strong><small>TRAFFIC INTELLIGENCE</small></div></div>
      <div className="side-label">WORKSPACE</div>
      <div className="side-link selected"><span className="side-icon">▦</span><span>Command center</span><span className="side-pip" /></div>
      <div className="side-link" onClick={() => { setTab("Active"); document.querySelector(".incident-panel")?.scrollIntoView({ behavior: "smooth" }); }}><span className="side-icon">◉</span><span>Live incidents</span><span className="side-count">{activeCount}</span></div>
      <div className="side-link" onClick={() => setTab("History")}><span className="side-icon">◷</span><span>Incident history</span></div>
      <div className="side-label second">SYSTEM</div>
      <div className="side-link" onClick={() => fileRef.current?.click()}><span className="side-icon">⇧</span><span>Change video source</span></div>
      <div className="sidebar-bottom">
        <div className="system-card"><div className="system-head"><span className="live-dot" /> SYSTEM STATUS</div><strong>{error ? "Connection issue" : status ? (isCalibrating ? "Learning traffic flow" : "Monitoring active") : "Connecting…"}</strong><p>{error ? "Check that the backend is running." : "AI engine · Incident lifecycle"}</p><div className="system-line"><span style={{ width: error ? "18%" : "100%" }} /></div></div>
        <div className="team-label"><span className="team-avatar">QA</span><span><b>Quadcore AI</b><small>Team CBC111 · PS-41</small></span><span className="more">···</span></div>
      </div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <div className="crumb"><span>Workspace</span><b>/</b><strong>Command center</strong></div>
        <div className="top-actions"><div className="clock"><span className="live-dot" /> LIVE MONITORING</div><span className="top-divider" /><span className="updated">Updated {lastUpdated ? fmtTime(lastUpdated) : "—"}</span><button className="icon-button" title="Refresh data" onClick={refresh}>↻</button><button className="upload-button" onClick={() => fileRef.current?.click()}><span>＋</span> Upload footage</button><input ref={fileRef} type="file" accept="video/mp4,video/*" hidden onChange={upload} /></div>
      </header>

      <section className="page-heading"><div><div className="eyebrow">AI-POWERED ROAD SAFETY</div><h1>Traffic command center<span className="heading-dot">.</span></h1><p>One clear view of road activity, emerging incidents, and the evidence behind every alert.</p></div><div className="date-chip"><span className="calendar-icon">▦</span><div><small>MONITORING MODE</small><b>{isCalibrating ? "Baseline learning" : "Continuous monitoring"}</b></div></div></section>

      {error && <div className="error-banner"><span>!</span>{error}<button onClick={refresh}>Retry</button></div>}

      <section className="metrics-grid">
        <Metric icon="◉" label="Active incidents" value={activeCount} note={activeCount ? "Requires operator review" : "No active alerts"} tone="red" />
        <Metric icon="✓" label="Acknowledged" value={acknowledgedCount} note="Reviewed by operator" tone="green" />
        <Metric icon="▣" label="Vehicles in frame" value={vehicleCount} note="Current processed frame" tone="blue" />
        <Metric icon="◌" label="Visibility score" value={status ? pct(visibility) : "—"} note={visibility >= .7 ? "Conditions look clear" : "Lower confidence may apply"} tone="purple" />
      </section>

      <section className="map-section panel">
        <div className="panel-header"><div><div className="panel-title">Traffic incident map</div><div className="panel-subtitle">Google Maps view · camera location is configurable</div></div><span className="mini-tag">MAP PREVIEW</span></div>
        <FlowMap incidents={incidents} />
      </section>

      <section className="monitor-grid">
        <div className="panel feed-panel">
          <div className="panel-header"><div><div className="panel-title"><span className="title-live" /> Live camera feed</div><div className="panel-subtitle">CAM-01 <span className="bullet">·</span> Annotated vehicle tracking</div></div><div className="feed-actions"><span className={`status-pill ${isCalibrating ? "learning" : "online"}`}>{isCalibrating ? "● LEARNING" : "● ONLINE"}</span><button className="small-icon" title="Refresh feed" onClick={() => { const img = document.getElementById("traffic-stream"); if (img) img.src = `/api/stream?t=${Date.now()}`; }}>↻</button></div></div>
          <div className="feed-frame"><img id="traffic-stream" src="/api/stream" alt="Live annotated traffic feed" onError={(e) => { e.currentTarget.style.opacity = ".18"; }} /><div className="feed-overlay top-left"><span className="rec-dot" /> LIVE <span className="overlay-separator">|</span> CAM-01</div><div className="feed-overlay top-right">FLOWGUARD <span className="overlay-version">/ CV</span></div><div className="feed-overlay bottom-left"><span className="scan-icon">⌁</span> {isCalibrating ? `Learning normal flow · ${Math.round((status?.progress || 0) * 100)}%` : "Object tracking enabled"}</div><div className="feed-overlay bottom-right">{vehicleCount} OBJECTS</div></div>
          <div className="feed-footer"><div className="feed-footer-item"><span className="legend-box vehicle" /> Vehicle tracking <b>{vehicleCount}</b></div><div className="feed-footer-item"><span className="legend-box flow" /> Flow analysis <b>{status?.calibrating ? "Learning" : "Active"}</b></div><div className="feed-footer-item"><span className="legend-box alert" /> Incident alerts <b>{activeCount}</b></div></div>
          {isCalibrating && <div className="calibration"><div className="calibration-copy"><span>Learning this camera's normal traffic pattern</span><b>{Math.round((status?.progress || 0) * 100)}%</b></div><div className="progress-track"><span style={{ width: `${Math.round((status?.progress || 0) * 100)}%` }} /></div></div>}
        </div>

        <div className="panel incident-panel">
          <div className="panel-header incident-heading"><div><div className="panel-title">Incident intelligence <span className="counter-badge">{incidents.length}</span></div><div className="panel-subtitle">Review alerts and supporting evidence</div></div><span className="pulse-ring"><i /></span></div>
          <div className="incident-toolbar"><div className="tabs">{Object.keys(TABS).map((name) => <button key={name} className={tab === name ? "active" : ""} onClick={() => setTab(name)}>{name}<span>{incidents.filter(TABS[name]).length}</span></button>)}</div><label className="search-box"><span>⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search alerts" /></label></div>
          <div className="incident-list">
            {visible.length === 0 ? <div className="empty-state"><div className="empty-symbol">✓</div><strong>{query ? "No matching incidents" : tab === "Active" ? "All clear for now" : "Nothing to show yet"}</strong><p>{query ? "Try another keyword or incident ID." : tab === "Active" ? "New alerts will appear here when the system detects an unusual traffic pattern." : "Incidents will appear here as they are recorded."}</p></div> : visible.map((incident) => <IncidentCard key={incident.id} incident={incident} selected={selectedId === incident.id} onSelect={() => setSelectedId(incident.id)} onAction={act} busy={busy} />)}
          </div>
          <div className="incident-footer"><span><span className="live-dot" /> Auto-refresh every 1.8 sec</span><span>{visible.length} shown</span></div>
        </div>
      </section>

      <section className="bottom-grid">
        <div className="panel flow-panel"><div className="panel-header"><div><div className="panel-title">Detection overview</div><div className="panel-subtitle">Event patterns recognized by FlowGuard</div></div><span className="mini-tag">4 EVENT TYPES</span></div><div className="event-types">{Object.entries(INCIDENTS).map(([type, meta]) => <div className="event-type" key={type}><span className={`event-icon ${meta.color}`}>{meta.icon}</span><div><b>{meta.label}</b><small>{incidents.filter((i) => i.type === type).length} recorded</small></div><span className="event-arrow">↗</span></div>)}</div></div>
        <div className="panel performance-panel"><div className="panel-header"><div><div className="panel-title">System performance</div><div className="panel-subtitle">Current processing snapshot</div></div><span className="mini-tag">LIVE</span></div><div className="performance-list"><PerformanceRow label="Camera visibility" value={visibility} display={status ? pct(visibility) : "—"} /><PerformanceRow label="Flow calibration" value={status ? (status.calibrating ? status.progress || 0 : 1) : 0} display={status ? (status.calibrating ? `${Math.round((status.progress || 0) * 100)}%` : "Complete") : "—"} /><PerformanceRow label="Detection merge rate" value={status?.stats?.raw ? Math.min(1, (status.stats.merged || 0) / status.stats.raw) : 0} display={status?.stats?.raw ? pct((status.stats.merged || 0) / status.stats.raw) : "—"} /><div className="perf-foot"><span>Raw detections <b>{status?.stats?.raw ?? 0}</b></span><span>Alerts raised <b>{status?.stats?.alerts ?? 0}</b></span></div></div></div>
      </section>
      <footer className="page-footer"><span>FLOWGUARD <b>·</b> AI TRAFFIC INCIDENT MONITORING</span><span>Built by Quadcore AI <b>·</b> CBC2.0 Design Round</span></footer>
    </main>

    {selected && <EvidenceModal incident={selected} onClose={() => setSelectedId(null)} onAction={act} busy={busy} />}
  </div>;
}

function Metric({ icon, label, value, note, tone }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-note"><span className={`note-dot ${tone}`} />{note}</div><div className={`metric-glow ${tone}`} /></div>;
}

function IncidentCard({ incident, selected, onSelect, onAction, busy }) {
  const meta = INCIDENTS[incident.type] || { label: incident.type || "Traffic incident", icon: "!", color: "amber" };
  const severity = (incident.severity || "MEDIUM").toLowerCase();
  return <article className={`incident-card ${selected ? "chosen" : ""}`} onClick={onSelect}>
    <div className={`incident-stripe ${severity}`} /><div className="incident-card-main"><div className="incident-card-top"><span className={`event-icon compact ${meta.color}`}>{meta.icon}</span><div className="incident-name"><b>{meta.label}</b><small>Incident #{incident.id} <span>·</span> {fmtTime(incident.created_at)}</small></div><span className={`severity ${severity}`}>{incident.severity || "MEDIUM"}</span></div><p className="incident-why">{incident.why || "An unusual traffic pattern was detected."}</p><div className="incident-meta"><span>Confidence <b>{pct(incident.confidence)}</b></span><span>Frames merged <b>{incident.detections ?? 1}</b></span><span className={`state-label ${String(incident.status).toLowerCase()}`}>{String(incident.status || "ACTIVE").replace("_", " ")}</span></div>
      {incident.status === "ACTIVE" && <div className="incident-actions" onClick={(e) => e.stopPropagation()}><button className="ack-button" disabled={busy} onClick={() => onAction(incident.id, "acknowledge")}>✓ Acknowledge</button><button className="false-button" disabled={busy} onClick={() => onAction(incident.id, "false-positive")}>↗ False positive</button></div>}
      {(incident.clip || incident.keyframe) && <button className="evidence-link" onClick={(e) => { e.stopPropagation(); onSelect(); }}>View evidence <span>↗</span></button>}
    </div>
  </article>;
}

function PerformanceRow({ label, value, display }) {
  return <div className="performance-row"><div className="performance-label"><span>{label}</span><b>{display}</b></div><div className="progress-track"><span style={{ width: `${Math.max(0, Math.min(100, Number(value) * 100))}%` }} /></div></div>;
}

function EvidenceModal({ incident, onClose, onAction, busy }) {
  const meta = INCIDENTS[incident.type] || { label: incident.type || "Incident", color: "amber", icon: "!" };
  useEffect(() => { const handle = (event) => event.key === "Escape" && onClose(); window.addEventListener("keydown", handle); return () => window.removeEventListener("keydown", handle); }, [onClose]);
  return <div className="modal-backdrop" onClick={onClose}><section className="evidence-modal" onClick={(e) => e.stopPropagation()}><div className="modal-header"><div><div className="eyebrow">INCIDENT EVIDENCE</div><h2><span className={`event-icon compact ${meta.color}`}>{meta.icon}</span>{meta.label}</h2><p>Incident #{incident.id} <span>·</span> {fmtTime(incident.created_at)}</p></div><button className="close-button" onClick={onClose}>×</button></div><div className="evidence-status-row"><span className={`severity ${(incident.severity || "MEDIUM").toLowerCase()}`}>{incident.severity || "MEDIUM"} SEVERITY</span><span className={`state-label ${String(incident.status).toLowerCase()}`}>{String(incident.status || "ACTIVE").replace("_", " ")}</span><span className="evidence-confidence">Confidence <b>{pct(incident.confidence)}</b></span></div><div className="evidence-media">{incident.clip ? <video src={`/evidence/${incident.clip}`} controls autoPlay muted loop /> : incident.keyframe ? <img src={`/evidence/${incident.keyframe}`} alt="Annotated incident keyframe" /> : <div className="evidence-pending"><span>◷</span><b>Evidence is being prepared</b><small>The image or video will appear when processing is complete.</small></div>}</div><div className="why-box"><span className="why-icon">i</span><div><b>Why FlowGuard flagged this</b><p>{incident.why || "No explanation was provided by the backend."}</p></div></div><div className="modal-actions">{incident.status === "ACTIVE" && <><button className="false-button" disabled={busy} onClick={() => onAction(incident.id, "false-positive")}>Mark false positive</button><button className="ack-button" disabled={busy} onClick={() => onAction(incident.id, "acknowledge")}>✓ Acknowledge incident</button></>}<button className="close-secondary" onClick={onClose}>Close details</button></div></section></div>;
}
