import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  positionsStream,
  type City,
  type CityEvent,
  type DataSource,
  type Hotspot,
  type Kpis,
  type PipelineStatus,
  type RouteReliability,
  type TrendPoint,
  type VehiclePosition,
  type WeatherImpact,
  type WeatherObservation,
} from "./api";
import { Sidebar, type ViewId } from "./components/Sidebar";
import { KpiCard } from "./components/Kpi";
import { LiveMap } from "./components/LiveMap";
import { ImpactChart, HotspotChart, TrendsChart } from "./components/Charts";
import { EventImpactPanel, RouteTable, WeatherImpactTable, WeatherPanel } from "./components/Panels";
import { MlPanel } from "./components/MlPanel";
import { PipelinePanel } from "./components/PipelinePanel";
import { Gauge } from "./components/Gauge";
import { Landing } from "./components/Landing";

const TITLES: Record<Exclude<ViewId, "landing">, string> = {
  overview: "Command Overview",
  map: "Live Fleet Map",
  analytics: "Network Analytics",
  ml: "Delay Predictor",
  pipeline: "Data Pipeline",
};

function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="clock">{now.toLocaleTimeString()}</span>;
}

function PanelHead({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="panel-head">
      <h3>{title}</h3>
      <div className="spacer" />
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

function CityPicker({ cities, city, disabled, onSelect }: { cities: City[]; city: City | null; disabled: boolean; onSelect: (name: string) => void }) {
  return (
    <label className="city-picker" title="Switch city">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
      </svg>
      <select value={city?.name ?? ""} onChange={(e) => onSelect(e.target.value)} disabled={disabled || cities.length === 0}>
        {cities.map((c) => (
          <option key={c.name} value={c.name}>
            {c.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function DataSourceBadge({ source }: { source: DataSource | null }) {
  if (!source) return null;
  return (
    <span className={`pill-source ${source.mode === "real" ? "real" : "synth"}`} title={source.detail}>
      {source.label}
    </span>
  );
}

export default function App() {
  const [view, setView] = useState<ViewId>("landing");
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [positions, setPositions] = useState<VehiclePosition[]>([]);
  const [routes, setRoutes] = useState<RouteReliability[]>([]);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [weather, setWeather] = useState<WeatherObservation[]>([]);
  const [weatherImpact, setWeatherImpact] = useState<WeatherImpact[]>([]);
  const [events, setEvents] = useState<CityEvent[]>([]);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastSync, setLastSync] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);
  const [cities, setCities] = useState<City[]>([]);
  const [city, setCity] = useState<City | null>(null);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const [switching, setSwitching] = useState(false);
  const liveRef = useRef(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [k, r, t, h, w, wi, e, p] = await Promise.all([
        api.kpis(),
        api.routes(),
        api.trends(24),
        api.hotspots(),
        api.weatherCurrent(),
        api.weatherImpact(),
        api.eventsActive(),
        api.pipeline(),
      ]);
      setKpis(k);
      setRoutes(r);
      setTrends(t);
      setHotspots(h);
      setWeather(w.zones);
      setWeatherImpact(wi);
      setEvents(e);
      setPipeline(p);
      setLastSync(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("refresh failed", err);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10_000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    api.cities().then((c) => setCities(c.cities)).catch(() => {});
    api.cityCurrent().then((c) => setCity(c)).catch(() => {});
    api.dataSource().then(setDataSource).catch(() => {});
  }, []);

  const switchCity = useCallback(async (name: string) => {
    if (!name || name === city?.name) return;
    setSwitching(true);
    try {
      await api.switchCity(name);
      const cur = await api.cityCurrent();
      setCity(cur);
      setLastSync(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("switch city failed", err);
    } finally {
      setSwitching(false);
      refresh();
    }
  }, [city, refresh]);

  useEffect(() => {
    const close = positionsStream(
      (p) => {
        setPositions(p);
        liveRef.current = true;
        setConnected(true);
      },
      () => {
        setConnected(false);
        api.positions().then(({ positions: p }) => {
          setPositions(p);
          liveRef.current = false;
        }).catch(() => {});
      },
    );
    return close;
  }, []);

  const source = kpis?.data_source ?? (liveRef.current ? "live-stream" : "warehouse");
  const live = connected && liveRef.current;
  const vehicles = positions.length || kpis?.vehicles_tracked || 0;

  if (view === "landing") {
    return <Landing kpis={kpis} live={live} vehicles={vehicles} city={city?.name} dataSource={dataSource} onEnter={() => setView("overview")} />;
  }

  const title = TITLES[view];
  const mapCenter: [number, number] = [city?.lat ?? 52.52, city?.lon ?? 13.405];

  return (
    <div className="app">
      <Sidebar view={view} onView={setView} live={live} source={source} vehicles={vehicles} city={city?.name ?? "Berlin"} />

      <div className="main">
        <div className="topbar">
          <div>
            <div className="crumb">Stadtanalyse / {title.toLowerCase()}</div>
            <h1>{title}</h1>
          </div>
          <div className="spacer" />
          <CityPicker cities={cities} city={city} disabled={switching} onSelect={switchCity} />
          <DataSourceBadge source={dataSource} />
          {live ? <span className="pill-live">LIVE STREAM</span> : <span className="pill-snap">warehouse snapshot</span>}
          <span className="clock">{lastSync}</span>
          <Clock />
          <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={refreshing}>
            {refreshing ? "…" : "Refresh"}
          </button>
          <a className="btn btn-ghost btn-sm" href="/docs" target="_blank" rel="noreferrer">
            API docs ↗
          </a>
        </div>

        <div className="content">
          {view === "overview" && (
            <>
              <KpiCard kpis={kpis} live={live} />
              <div className="grid-3">
                <div className="panel">
                  <PanelHead title="Punctuality" hint="last 24h" />
                  <div className="gauge-wrap">
                    <Gauge value={kpis?.on_time_pct ?? 0} label="on-time" />
                    <div className="gauge-side">
                      <div className="row"><span>Avg delay</span><b>{(kpis?.avg_delay_seconds ?? 0).toFixed(0)}s</b></div>
                      <div className="row"><span>Severe</span><b>{kpis?.severe_delays ?? 0}</b></div>
                      <div className="row"><span>Speed</span><b>{(kpis?.avg_speed_kmh ?? 0).toFixed(1)} km/h</b></div>
                      <div className="row"><span>Events</span><b>{kpis?.active_events ?? 0}</b></div>
                    </div>
                  </div>
                </div>
                <div className="panel">
                  <PanelHead title="Delay Trend" hint="24h" />
                  <TrendsChart trends={trends} />
                </div>
                <div className="panel">
                  <PanelHead title="Top Hotspots" hint="by avg delay" />
                  <HotspotChart hotspots={hotspots} />
                </div>
              </div>
              <div className="grid">
                <div className="panel">
                  <PanelHead title={`Live Fleet Map · ${city?.name ?? ""}`} hint="weather zones + events" />
                  <LiveMap key={city?.name ?? "default"} positions={positions} events={events} weather={weather} height={400} center={mapCenter} />
                </div>
                <div className="panel">
                  <PanelHead title="Route Reliability" />
                  <RouteTable routes={routes} />
                  <PanelHead title="Weather Impact" />
                  <WeatherImpactTable data={weatherImpact} />
                </div>
              </div>
            </>
          )}

          {view === "map" && (
            <div className="panel" style={{ padding: 0 }}>
              <div className="panel-head" style={{ padding: "18px 18px 6px" }}>
                <h3>Live Fleet Map · {city?.name ?? ""}</h3>
                <div className="spacer" />
                <span className="hint">{positions.length} vehicles · {events.length} events · {weather.length} weather zones</span>
              </div>
              <LiveMap key={city?.name ?? "default"} positions={positions} events={events} weather={weather} height={760} center={mapCenter} />
            </div>
          )}

          {view === "analytics" && (
            <>
              <div className="grid">
                <div className="panel">
                  <PanelHead title="Network Delay Trend" hint="24h" />
                  <TrendsChart trends={trends} />
                </div>
                <div className="panel">
                  <PanelHead title="Weather Impact on Delays" />
                  <ImpactChart data={weatherImpact} />
                </div>
              </div>
              <div className="grid">
                <div className="panel">
                  <PanelHead title="Congestion Hotspots" hint="top 10 grid cells" />
                  <HotspotChart hotspots={hotspots} />
                </div>
                <div className="panel">
                  <PanelHead title="Route Reliability" />
                  <RouteTable routes={routes} />
                </div>
              </div>
              <div className="grid">
                <div className="panel">
                  <PanelHead title="Weather per Zone" />
                  <WeatherPanel zones={weather} />
                </div>
                <div className="panel">
                  <PanelHead title="Active City Events" />
                  <EventImpactPanel events={events} />
                </div>
              </div>
            </>
          )}

          {view === "ml" && (
            <div className="panel">
              <PanelHead title="Trip Delay Predictor" hint="XGBoost · trained on the silver warehouse" />
              <MlPanel />
            </div>
          )}

          {view === "pipeline" && (
            <>
              <div className="grid">
                <div className="panel">
                  <PanelHead title="Ingestion &amp; Warehouse Health" />
                  <PipelinePanel pipeline={pipeline} />
                </div>
                <div className="panel">
                  <PanelHead title="Batch Flow" hint="Airflow · 15 min" />
                  <div className="status-grid" style={{ gridTemplateColumns: "1fr" }}>
                    {[
                      ["Stream", "Kafka → bronze lakehouse (MinIO)"],
                      ["Gold", "dbt transforms bronze → silver → gold"],
                      ["Quality", "Great Expectations suites on gold"],
                      ["Retrain", "XGBoost delay model on silver Δ"],
                    ].map(([k, v]) => (
                      <div className="status-card" key={k} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className="lbl">{k}</span>
                        <span className="faint small" style={{ textAlign: "right" }}>{v}</span>
                      </div>
                    ))}
                  </div>
                  <div className="muted small" style={{ marginTop: 12 }}>
                    Data source: <b>{source}</b> · last sync <b>{lastSync}</b>
                  </div>
                </div>
              </div>
              <div className="panel">
                <PanelHead title="Live Stream Frames" hint="SSE · 1s" />
                <div className="muted small">
                  Positions stream is connected {live ? "live via Kafka topic `raw.transport.vehicle.positions`" : "in snapshot mode (DuckDB demo seed)"}. {positions.length} vehicles rendered.
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
