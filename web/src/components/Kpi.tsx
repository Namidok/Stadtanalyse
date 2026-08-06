import type { ReactNode } from "react";
import type { Kpis } from "../api";
import { NumberTicker } from "./NumberTicker";

function cls(value: number, good: number, bad: number): string {
  if (value <= good) return "good";
  if (value >= bad) return "bad";
  return "warn";
}

const ICONS: Array<{ label: string; ico: ReactNode }> = [
  {
    label: "Vehicles Tracked",
    ico: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
        <path d="M3 13l3-8 3 8M7 13v6M17 8a3 3 0 1 0 3 3M17 11v8" />
      </svg>
    ),
  },
  {
    label: "Avg Delay",
    ico: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
    ),
  },
  {
    label: "On-Time Rate",
    ico: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
        <path d="M20 6 9 17l-5-5" />
      </svg>
    ),
  },
  {
    label: "Severe Delays",
    ico: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
        <path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3Z" />
      </svg>
    ),
  },
  {
    label: "Avg Speed",
    ico: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
        <path d="M5 12a7 7 0 0 1 14 0" />
        <path d="M12 12l4-4" />
        <path d="M3 17h18" />
      </svg>
    ),
  },
  {
    label: "Active Events",
    ico: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
        <path d="M8 2v4M16 2v4M4 6h16M6 6v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6" />
      </svg>
    ),
  },
];

function Pill({ live }: { live: boolean }) {
  return live ? <span className="pill-live" style={{ padding: "2px 8px", fontSize: 10 }}>LIVE</span> : <span className="pill-snap" style={{ padding: "2px 8px", fontSize: 10 }}>SNAP</span>;
}

export function KpiCard({ kpis, live }: { kpis: Kpis | null; live: boolean }) {
  if (!kpis) return <div className="kpis"><span className="muted small">loading KPIs…</span></div>;
  const items: Array<{ label: string; value: number; suffix: string; decimals?: number; cls?: string; ticker: boolean; sub: string }> = [
    { label: "Vehicles Tracked", value: kpis.vehicles_tracked, suffix: "", cls: "good", ticker: true, sub: "active fleet" },
    { label: "Avg Delay", value: kpis.avg_delay_seconds, suffix: "s", cls: cls(kpis.avg_delay_seconds, 60, 300), ticker: true, sub: "network-wide" },
    { label: "On-Time Rate", value: kpis.on_time_pct, suffix: "%", decimals: 1, cls: cls(kpis.on_time_pct, 100, 60), ticker: true, sub: "punctuality" },
    { label: "Severe Delays", value: kpis.severe_delays, suffix: "", cls: kpis.severe_delays > 10 ? "bad" : "good", ticker: true, sub: ">5 min late" },
    { label: "Avg Speed", value: kpis.avg_speed_kmh, suffix: " km/h", decimals: 1, cls: "", ticker: true, sub: "fleet mean" },
    { label: "Active Events", value: kpis.active_events, suffix: "", cls: kpis.active_events > 0 ? "warn" : "good", ticker: true, sub: "city-wide" },
  ];
  return (
    <div className="kpis">
      {items.map((it, i) => (
        <div className="kpi" key={it.label} style={{ animationDelay: `${i * 60}ms` }}>
          <div className="top">
            <span className="label">{it.label}</span>
            <span className="ico">{ICONS[i].ico}</span>
          </div>
          <div className={`value ${it.cls ?? ""}`}>
            <NumberTicker value={it.value} decimals={it.decimals ?? 0} suffix={it.suffix} />
          </div>
          <div className="sub">
            <Pill live={live} />
            <span>{it.sub}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
