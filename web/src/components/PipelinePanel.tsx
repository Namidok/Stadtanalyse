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
  return (
    <div className="status-row" style={{ flexDirection: "column", alignItems: "flex-start", gap: 10 }}>
      <span className="status-chip">
        warehouse: <b>{warehouse.mode}</b>
      </span>
      <span className="status-chip">
        quality last run: <b>{quality.last_run ?? "not run yet"}</b>
      </span>
      <span className="status-chip">
        vehicles in snapshot: <b>{streaming.vehicles_in_snapshot}</b>
      </span>
      <span className="status-chip">
        ingest uptime: <b>{fmt(ingestion.uptime_seconds)}</b> · total records <b>{ingestion.total_records.toLocaleString()}</b>
      </span>
      <div style={{ width: "100%" }}>
        {counters.map(([stream, count]) => (
          <div key={stream} className="status-chip" style={{ display: "inline-block", marginRight: 6 }}>
            {stream}: <b>{count.toLocaleString()}</b>{" "}
            <span className="muted small">({ingestion.rates[stream]?.toFixed(1)}/s)</span>
          </div>
        ))}
      </div>
    </div>
  );
}
