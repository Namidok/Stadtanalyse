import type { Kpis } from "../api";

function cls(value: number, good: number, bad: number): string {
  if (value <= good) return "good";
  if (value >= bad) return "bad";
  return "warn";
}

export function KpiCard({ kpis }: { kpis: Kpis | null }) {
  if (!kpis) return <div className="kpis"><span className="muted small">loading KPIs…</span></div>;
  const items: Array<{ label: string; value: string; cls?: string }> = [
    { label: "Vehicles Tracked", value: String(kpis.vehicles_tracked) },
    { label: "Avg Delay", value: `${Math.round(kpis.avg_delay_seconds)}s`, cls: cls(kpis.avg_delay_seconds, 60, 300) },
    { label: "On-Time %", value: `${kpis.on_time_pct.toFixed(1)}%`, cls: cls(kpis.on_time_pct, 100, 60) },
    { label: "Severe Delays", value: String(kpis.severe_delays), cls: kpis.severe_delays > 10 ? "bad" : "good" },
    { label: "Avg Speed", value: `${kpis.avg_speed_kmh.toFixed(1)} km/h` },
    { label: "Active Events", value: String(kpis.active_events), cls: kpis.active_events > 0 ? "warn" : "good" },
  ];
  return (
    <div className="kpis">
      {items.map((it) => (
        <div className="kpi" key={it.label}>
          <div className="label">{it.label}</div>
          <div className={`value ${it.cls ?? ""}`}>{it.value}</div>
        </div>
      ))}
    </div>
  );
}
