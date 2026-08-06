import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  positionsStream,
  type CityEvent,
  type Hotspot,
  type Kpis,
  type PipelineStatus,
  type RouteReliability,
  type TrendPoint,
  type VehiclePosition,
  type WeatherImpact,
  type WeatherObservation,
} from "./api";
import { EventImpactPanel, RouteTable, WeatherPanel } from "./components/Panels";
import { HotspotChart, ImpactChart, TrendsChart } from "./components/Charts";
import { LiveMap } from "./components/LiveMap";
import { MlPanel } from "./components/MlPanel";
import { PipelinePanel } from "./components/PipelinePanel";
import { KpiCard } from "./components/Kpi";

export default function App() {
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
  const liveRef = useRef(false);

  const refresh = useCallback(async () => {
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
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10_000);
    return () => clearInterval(id);
  }, [refresh]);

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

  return (
    <div className="app">
      <header>
        <div className="logo">
          City<span>Pulse</span>
        </div>
        <div className="sub">Smart Urban Mobility Data Lake &amp; Analytics</div>
        <div className="spacer" />
        {live ? (
          <span className="pill live">● LIVE STREAM</span>
        ) : (
          <span className="pill warn">▲ warehouse snapshot</span>
        )}
        <span className="pill">source: {source}</span>
        <span className="pill">{lastSync}</span>
      </header>

      <main>
        <KpiCard kpis={kpis} />

        <div className="grid">
          <div className="panel">
            <h3>Live Fleet Map · Berlin</h3>
            <div className="map-wrap">
              <LiveMap positions={positions} events={events} weather={weather} />
            </div>
          </div>
          <div className="panel">
            <h3>Route Reliability</h3>
            <RouteTable routes={routes} />
            <h3 style={{ marginTop: 16 }}>City Events</h3>
            <EventImpactPanel events={events} />
          </div>
        </div>

        <div className="charts">
          <div className="panel">
            <h3>Network Delay Trend (24h)</h3>
            <TrendsChart trends={trends} />
          </div>
          <div className="panel">
            <h3>Congestion Hotspots</h3>
            <HotspotChart hotspots={hotspots} />
          </div>
          <div className="panel">
            <h3>Weather Impact on Delays</h3>
            <ImpactChart data={weatherImpact} />
          </div>
          <div className="panel">
            <h3>Weather per Zone</h3>
            <WeatherPanel zones={weather} />
          </div>
        </div>

        <div className="grid">
          <div className="panel">
            <h3>Delay Prediction (XGBoost)</h3>
            <MlPanel />
          </div>
          <div className="panel">
            <h3>Pipeline Health</h3>
            <PipelinePanel pipeline={pipeline} />
          </div>
        </div>
      </main>
    </div>
  );
}
