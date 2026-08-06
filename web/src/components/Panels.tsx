import type { CityEvent, RouteReliability, WeatherImpact, WeatherObservation } from "../api";
import { CONDITION_COLORS } from "../api";

export function RouteTable({ routes }: { routes: RouteReliability[] }) {
  const rows = routes.slice(0, 8);
  const max = Math.max(...rows.map((r) => r.avg_delay_seconds), 1);
  if (rows.length === 0) return <span className="muted small">no data yet</span>;
  return (
    <table>
      <thead>
        <tr>
          <th>Route</th>
          <th>Mode</th>
          <th className="num">Avg</th>
          <th className="num">p95</th>
          <th style={{ width: 120 }}>On-time</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.route_id}>
            <td>
              <b>{r.route_id}</b>
            </td>
            <td className="muted">{r.route_mode}</td>
            <td className="num">{Math.round(r.avg_delay_seconds)}s</td>
            <td className="num">{Math.round(r.p95_delay_seconds)}s</td>
            <td>
              <div className="bar">
                <div style={{ width: `${(r.avg_delay_seconds / max) * 100}%`, background: r.avg_delay_seconds > 120 ? "#f87171" : "#38bdf8" }} />
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function EventImpactPanel({ events }: { events: CityEvent[] }) {
  const active = events.filter((e) => e.status === "ACTIVE");
  if (active.length === 0) return <span className="muted small">no active events</span>;
  return (
    <div className="status-row">
      {active.slice(0, 6).map((e) => (
        <span className="status-chip" key={e.event_id} title={e.name}>
          {e.category} · <b>{e.name}</b> · impact {e.impact.toFixed(1)}
        </span>
      ))}
    </div>
  );
}

export function WeatherPanel({ zones }: { zones: WeatherObservation[] }) {
  const top = zones.slice(0, 8);
  if (top.length === 0) return <span className="muted small">no observations yet</span>;
  return (
    <table>
      <thead>
        <tr>
          <th>Zone</th>
          <th>Condition</th>
          <th className="num">Temp</th>
          <th className="num">Precip</th>
          <th className="num">Wind</th>
        </tr>
      </thead>
      <tbody>
        {top.map((z) => (
          <tr key={z.zone_id}>
            <td>{z.zone_id}</td>
            <td>
              <span className="dot" style={{ background: CONDITION_COLORS[z.condition] ?? "#94a3b8" }} />
              {z.condition}
            </td>
            <td className="num">{z.temperature_c.toFixed(1)}°C</td>
            <td className="num">{z.precipitation_mm.toFixed(1)} mm</td>
            <td className="num">{z.wind_speed_kmh.toFixed(0)} km/h</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function WeatherImpactTable({ data }: { data: WeatherImpact[] }) {
  if (data.length === 0) return <span className="muted small">no data yet</span>;
  return (
    <table>
      <thead>
        <tr>
          <th>Condition</th>
          <th className="num">Obs</th>
          <th className="num">Avg delay</th>
          <th className="num">On-time %</th>
        </tr>
      </thead>
      <tbody>
        {data.map((d) => (
          <tr key={d.condition}>
            <td>{d.condition}</td>
            <td className="num">{d.observations}</td>
            <td className="num">{Math.round(d.avg_delay_seconds)}s</td>
            <td className="num">{d.on_time_pct.toFixed(1)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
