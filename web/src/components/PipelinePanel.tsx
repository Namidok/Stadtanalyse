import type { PipelineStatus } from "../api";

function fmt(seconds: number): string {
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s % 60}s` : `${s}s`;
}

export function PipelinePanel({ pipeline }: { pipeline: PipelineStatus | null }) {
  if (!pipeline) return <span className="muted small">no status yet</span>;
  const { ingestion, warehouse, quality, streaming } = pipeline;
  const counters = Object.entries(ingestion.counters);
  const total = ingestion.total_records;
  const ok = warehouse.mode === "duckdb" || warehouse.mode === "postgres";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="status-grid">
        <div className="status-card">
          <div className="lbl">Warehouse Mode</div>
          <div className="val">
            <span className={`pill ${ok ? "ok" : "warn"}`}>{warehouse.mode}</span>
          </div>
        </div>
        <div className="status-card">
          <div className="lbl">Streaming Snapshot</div>
          <div className="val">{streaming.vehicles_in_snapshot.toLocaleString()} vehicles</div>
        </div>
        <div className="status-card">
          <div className="lbl">Ingest Uptime</div>
          <div className="val">{fmt(ingestion.uptime_seconds)}</div>
        </div>
        <div className="status-card">
          <div className="lbl">Quality Last Run</div>
          <div className="val">{quality.last_run ?? "not run yet"}</div>
        </div>
      </div>

      <div className="status-card">
        <div className="lbl">Ingestion Counters</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 22, marginTop: 8 }}>
          {counters.map(([stream, count]) => (
            <div key={stream} className="ring-cell">
              <span className="cnt">{count.toLocaleString()}</span>
              <span className="name">{stream}</span>
              <span className="faint" style={{ fontSize: 10 }}>{ingestion.rates[stream]?.toFixed(1)}/s</span>
            </div>
          ))}
        </div>
        <div className="faint small" style={{ marginTop: 6 }}>
          total records: <b className="mono" style={{ color: "var(--text)" }}>{total.toLocaleString()}</b>
        </div>
      </div>
    </div>
  );
}
