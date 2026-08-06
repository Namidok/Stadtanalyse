import { useState } from "react";
import { api, type Prediction, type PredictionRequest } from "../api";

const CONDITIONS = ["clear", "partly_cloudy", "cloudy", "fog", "rain", "storm", "snow"];
const MODES = ["bus", "tram", "rail"];

const BUCKET_COLOR: Record<string, string> = {
  on_time: "#34d399",
  delayed: "#fbbf24",
  severe: "#f87171",
};

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

  const bucket = res?.predicted_bucket ?? "on_time";
  const probs = res?.probabilities;

  return (
    <div>
      <div className="ml-form">
        <div className="field">
          <label>Mode</label>
          <select value={req.route_mode} onChange={(e) => set("route_mode", e.target.value)}>
            {MODES.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Weather</label>
          <select value={req.condition} onChange={(e) => set("condition", e.target.value)}>
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Hour</label>
          <input type="number" min={0} max={23} value={req.hour_of_day} onChange={(e) => set("hour_of_day", Number(e.target.value))} />
        </div>
        <div className="field">
          <label>Rush hour</label>
          <select value={req.is_rush_hour} onChange={(e) => set("is_rush_hour", Number(e.target.value))}>
            <option value={1}>yes</option>
            <option value={0}>no</option>
          </select>
        </div>
        <div className="field">
          <label>Precip (mm)</label>
          <input type="number" step="0.5" min={0} value={req.precipitation_mm} onChange={(e) => set("precipitation_mm", Number(e.target.value))} />
        </div>
        <div className="field">
          <label>Wind (km/h)</label>
          <input type="number" step="1" min={0} value={req.wind_speed_kmh} onChange={(e) => set("wind_speed_kmh", Number(e.target.value))} />
        </div>
        <div className="field">
          <label>Event nearby</label>
          <select value={req.event_nearby} onChange={(e) => set("event_nearby", Number(e.target.value))}>
            <option value={1}>yes</option>
            <option value={0}>no</option>
          </select>
        </div>
        <div className="field">
          <label>Segment (km)</label>
          <input type="number" step="0.1" min={0} value={req.segment_km} onChange={(e) => set("segment_km", Number(e.target.value))} />
        </div>
        <div className="field">
          <label>Hist avg delay (s)</label>
          <input type="number" step="5" min={0} value={req.historical_avg_delay} onChange={(e) => set("historical_avg_delay", Number(e.target.value))} />
        </div>
        <div className="field toggle">
          <button className="btn" onClick={run} disabled={busy}>
            {busy ? "Predicting…" : "Predict delay"}
          </button>
        </div>
      </div>

      {res && (
        <div className="result">
          {res.loaded ? (
            <>
              <div className="faint small" style={{ marginBottom: 6 }}>PREDICTED DELAY · XGBoost v1</div>
              <span className="big">{Math.round(res.predicted_delay_seconds ?? 0)}</span>
              <span className="muted" style={{ fontSize: 18 }}>s</span>
              <span className={`bucket ${bucket}`}>{bucket}</span>
              {probs && (
                <div style={{ marginTop: 14 }}>
                  {Object.entries(probs).map(([k, v]) => (
                    <div key={k} className="prob-row" style={{ marginBottom: 8 }}>
                      <div className="row" style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                        <span className="muted">{k}</span>
                        <b className="mono">{(v * 100).toFixed(1)}%</b>
                      </div>
                      <div className="prob-bar">
                        <div style={{ width: `${(v * 100).toFixed(1)}%`, background: BUCKET_COLOR[k] ?? "#22d3ee" }} />
                      </div>
                    </div>
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
