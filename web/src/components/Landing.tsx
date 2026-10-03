import type { DataSource, Kpis } from "../api";
import { NumberTicker } from "./NumberTicker";
import { StreamBadge } from "./StreamBadge";

const FEATURES: Array<{ icon: string; title: string; desc: string; accent: string }> = [
  {
    icon: "M3 13l3-8 3 8M7 13v6M17 8a3 3 0 1 0 3 3M17 11v8M9 19h8",
    title: "Fleet Map",
    desc: "Simulated vehicle positions, moved along the real GTFS network, stream over Kafka onto an interactive city map. GTFS-RT carries trip delays, not GPS positions.",
    accent: "#22d3ee",
  },
  {
    icon: "M3 3v18h18M7 13v3M12 9v7M17 5v11",
    title: "Delay Analytics",
    desc: "Punctuality, route reliability and hotspots from real GTFS-RT trip delays (realtime.gtfs.de). Weather and event impact use simulated weather and events.",
    accent: "#818cf8",
  },
  {
    icon: "M20 6 9 17l-5-5",
    title: "Delay Predictor",
    desc: "An XGBoost model trained on the dbt gold.ml_features table, evaluated on a time-based split against simple baselines. Runs in the full local stack, not on this demo.",
    accent: "#34d399",
  },
  {
    icon: "M4 6h16M4 10h16M4 14h10M4 18h6",
    title: "Lakehouse Pipeline",
    desc: "Spark Structured Streaming lands Kafka topics in Bronze Delta tables on MinIO, a Spark batch job builds Silver, and dbt builds Gold marts in PostgreSQL.",
    accent: "#fbbf24",
  },
  {
    icon: "M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3Z",
    title: "Data Quality Checks",
    desc: "Great Expectations suites validate the Silver exports in the full local pipeline (make jobs / Airflow). They do not run on this public demo.",
    accent: "#f472b6",
  },
  {
    icon: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20ZM3.6 9h16.8M3.6 15h16.8M12 2a14 14 0 0 1 0 20M12 2a14 14 0 0 0 0 20",
    title: "Observability",
    desc: "In the full local stack, Prometheus scrapes the API and Kafka, Postgres and node exporters, and Grafana shows a platform dashboard. Not deployed on this demo.",
    accent: "#a78bfa",
  },
];

const STAGES: Array<{ label: string; sub: string; accent: string }> = [
  { label: "Sources", sub: "GTFS-RT + simulators", accent: "#22d3ee" },
  { label: "Kafka", sub: "4 raw topics", accent: "#38bdf8" },
  { label: "Bronze", sub: "Delta on MinIO", accent: "#38bdf8" },
  { label: "Silver", sub: "Spark batch → Delta", accent: "#818cf8" },
  { label: "Gold", sub: "dbt → Postgres", accent: "#a78bfa" },
  { label: "Serve", sub: "API + dashboard", accent: "#34d399" },
];

function Stat({ value, suffix, label, decimals }: { value: number; suffix: string; label: string; decimals?: number }) {
  return (
    <div className="land-stat">
      <div className="value">
        <NumberTicker value={value} suffix={suffix} decimals={decimals ?? 0} />
      </div>
      <div className="label">{label}</div>
    </div>
  );
}

export function Landing({ kpis, apiOnline, streaming, vehicles, city, dataSource, onEnter }: { kpis: Kpis | null; apiOnline: boolean | null; streaming: boolean; vehicles: number; city?: string; dataSource: DataSource | null; onEnter: () => void }) {
  return (
    <div className="landing">
      <div className="land-hero">
        <div className="land-badge">
          <StreamBadge apiOnline={apiOnline} source={dataSource} streaming={streaming} city={city} />
          {apiOnline !== false && dataSource && (
            <span className={`pill-source ${dataSource.mode === "real" ? "real" : "synth"}`} title={dataSource.detail}>
              {dataSource.label}
            </span>
          )}
        </div>
        <div className="land-mark">
          <svg viewBox="0 0 24 24" width="34" height="34">
            <g fill="currentColor">
              <rect x="5" y="13" width="3" height="6" rx="0.6" />
              <rect x="9" y="10" width="3.4" height="9" rx="0.6" />
              <rect x="13.2" y="14" width="2.6" height="5" rx="0.5" />
              <rect x="16.6" y="11.5" width="2.4" height="7.5" rx="0.5" />
            </g>
            <polyline points="5.5,19 10,16 14,12 18.5,6.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="10" cy="16" r="0.9" fill="currentColor" />
            <circle cx="14" cy="12" r="0.9" fill="currentColor" />
            <circle cx="18.5" cy="6.5" r="1.2" fill="currentColor" />
          </svg>
        </div>
        <h1 className="land-title">
          Stadt<em>analyse</em>
        </h1>
        <p className="land-sub">A smart urban-mobility analytics platform. It streams real GTFS-RT trip delays from realtime.gtfs.de, plus simulated vehicle positions, weather and city events, through Kafka into a Delta Lake, and turns them into delay analytics and a delay-prediction model.</p>

        <div className="land-cta">
          <button className="btn land-btn" onClick={onEnter}>
            Enter dashboard
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
          <button className="btn btn-ghost land-btn" onClick={() => document.getElementById("land-features")?.scrollIntoView({ behavior: "smooth" })}>
            Explore the platform
          </button>
        </div>

        {apiOnline === false ? (
          <div className="offline-note">
            <b>Demo API offline</b>
            The backend for this demo isn't responding right now, so no figures are shown. The full pipeline runs locally with Docker Compose; see the README.
          </div>
        ) : (
          <div className="land-stats">
            <Stat value={vehicles || kpis?.vehicles_tracked || 0} suffix="" label="vehicles tracked" />
            <Stat value={kpis?.on_time_pct ?? 0} suffix="%" label="on-time rate" decimals={1} />
            <Stat value={kpis?.avg_delay_seconds ?? 0} suffix="s" label="avg delay" />
            <Stat value={kpis?.active_events ?? 0} suffix="" label="active events" />
          </div>
        )}
      </div>

      <div id="land-features" className="land-section">
        <h2 className="land-h2">What Stadtanalyse does</h2>
        <div className="land-features">
          {FEATURES.map((f) => (
            <div className="land-card" key={f.title}>
              <div className="land-ico" style={{ color: f.accent, background: `rgba(0,0,0,0.25)` }}>
                <svg viewBox="0 0 24 24" fill="none" stroke={f.accent} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="22" height="22">
                  <path d={f.icon} />
                </svg>
              </div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="land-section">
        <h2 className="land-h2">The data flow</h2>
        <div className="land-flow">
          {STAGES.map((s, i) => (
            <div key={s.label} className="land-flow-stage">
              <div className="land-flow-node" style={{ borderColor: s.accent }}>
                <b>{s.label}</b>
                <span>{s.sub}</span>
              </div>
              {i < STAGES.length - 1 && (
                <div className="land-flow-arrow">→</div>
              )}
            </div>
          ))}
        </div>
        <p className="land-flow-note">
          Full local pipeline: real GTFS-RT trip delays from realtime.gtfs.de (polled every 20 s) plus simulated vehicle positions, weather and events flow through 4 Kafka topics. Spark Structured Streaming writes Bronze Delta tables on MinIO, a Spark batch job builds Silver, Great Expectations checks the Silver exports, dbt builds Gold marts in PostgreSQL, and XGBoost retrains on gold.ml_features. In the synthetic local mode an Airflow DAG runs these batch steps every 15 minutes.
        </p>
        {dataSource?.memory_mode && (
          <p className="land-flow-note">
            This public demo is a snapshot: the API serves a fixed, synthetic DuckDB sample from memory. No Kafka, Spark, Postgres, Great Expectations or ML model runs on this server.
          </p>
        )}
      </div>

      <div className="land-footer">
        <button className="btn land-btn" onClick={onEnter}>
          Launch the dashboard
        </button>
        <div className="land-foot-note">Stadtanalyse · Kafka → Spark → Delta on MinIO → dbt → Postgres · FastAPI + React · Airflow · Prometheus &amp; Grafana (full local stack)</div>
      </div>
    </div>
  );
}
