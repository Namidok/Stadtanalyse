import { useState } from "react";
import { api, type Prediction, type PredictionRequest } from "../api";

const CONDITIONS = ["clear", "partly_cloudy", "cloudy", "fog", "rain", "storm", "snow"];
const MODES = ["bus", "tram", "rail"];

export function MlPanel() {
  const [req, setReq] = useState<PredictionRequest>({
    route_mode: "bus",
    condition: "clear",
    hour_of_day: 8,
    day_of_week: 1,
    is_rush_hour: 1,
    segment_km: 0.8,
    temperature_c: 15,
    precipitation_mm: 0,
    wind_speed_kmh: 8,
    event_proximity_km: 10,
    event_nearby: 0,
    historical_avg_delay: 30,
    stop_zone_num: 3,
  });
  const [res, setRes] = useState<Prediction | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof PredictionRequest, v: number | string) => setReq((r) => ({ ...r, [k]: v }));

  const run = async () => {
    setBusy(true);
    try {
      setRes(await api.predict(req));
    } catch (err) {
      setRes({ loaded: false, error: String(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="form-row">
        <label>
          Mode{" "}
          <select value={req.route_mode} onChange={(e) => set("route_mode", e.target.value)}>
            {MODES.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
        <label>
          Weather{" "}
          <select value={req.condition} onChange={(e) => set("condition", e.target.value)}>
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Hour{" "}
          <input
            type="number"
            min={0}
            max={23}
            value={req.hour_of_day}
            onChange={(e) => set("hour_of_day", Number(e.target.value))}
          />
        </label>
        <label>
          Precip (mm){" "}
          <input
            type="number"
            step="0.5"
            min={0}
            value={req.precipitation_mm}
            onChange={(e) => set("precipitation_mm", Number(e.target.value))}
          />
        </label>
        <label>
          Wind (km/h){" "}
          <input
            type="number"
            step="1"
            min={0}
            value={req.wind_speed_kmh}
            onChange={(e) => set("wind_speed_kmh", Number(e.target.value))}
          />
        </label>
      </div>
      <div className="form-row">
        <label>
          Rush hour{" "}
          <select value={req.is_rush_hour} onChange={(e) => set("is_rush_hour", Number(e.target.value))}>
            <option value={1}>yes</option>
            <option value={0}>no</option>
          </select>
        </label>
        <label>
          Event nearby{" "}
          <select value={req.event_nearby} onChange={(e) => set("event_nearby", Number(e.target.value))}>
            <option value={1}>yes</option>
            <option value={0}>no</option>
          </select>
        </label>
        <label>
          Segment (km){" "}
          <input
            type="number"
            step="0.1"
            min={0}
            value={req.segment_km}
            onChange={(e) => set("segment_km", Number(e.target.value))}
          />
        </label>
        <label>
          Hist avg delay (s){" "}
          <input
            type="number"
            step="5"
            min={0}
            value={req.historical_avg_delay}
            onChange={(e) => set("historical_avg_delay", Number(e.target.value))}
          />
        </label>
        <button className="btn" onClick={run} disabled={busy}>
          {busy ? "…" : "Predict"}
        </button>
      </div>

      {res && (
        <div className="result-card">
          {res.loaded ? (
            <>
              <div>
                Predicted delay <span className="big">{Math.round(res.predicted_delay_seconds ?? 0)}s</span>
                <span className="muted small"> · bucket: {res.predicted_bucket}</span>
              </div>
              {res.probabilities && (
                <div className="legend" style={{ marginTop: 8 }}>
                  {Object.entries(res.probabilities).map(([k, v]) => (
                    <span key={k}>
                      <span className="dot" style={{ background: v > 0.5 ? "#38bdf8" : "#1e2a44" }} />
                      {k} {(v * 100).toFixed(1)}%
                    </span>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="muted small">model unavailable: {res.error ?? "not loaded"}</div>
          )}
        </div>
      )}
    </div>
  );
}
