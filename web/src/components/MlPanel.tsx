import { useState } from "react";
import { api, type Prediction, type PredictionRequest } from "../api";

const CONDITIONS = ["clear", "partly_cloudy", "cloudy", "fog", "rain", "storm", "snow"];
const MODES = ["bus", "tram", "rail"];

const BUCKET_COLOR: Record<string, string> = {
  on_time: "#34d399",
  delayed: "#fbbf24",
  severe: "#f87171",
};

const BUCKET_NOTE: Record<string, string> = {
  on_time: "Expect the vehicle to hold its schedule.",
  delayed: "Expect a short delay — allow a few extra minutes.",
  severe: "Expect significant disruption on this trip.",
};

type Preset = { name: string; icon: string; patch: Partial<PredictionRequest> };

const PRESETS: Preset[] = [
  { name: "Clear off-peak", icon: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z", patch: { route_mode: "tram", condition: "clear", hour_of_day: 14, day_of_week: 3, is_rush_hour: 0, precipitation_mm: 0, wind_speed_kmh: 6, event_nearby: 0, event_proximity_km: 10, historical_avg_delay: 20, segment_km: 0.6 } },
  { name: "Rush-hour rain", icon: "M16 3h2a4 4 0 0 1 0 8h-2M16 7h6M16 11h4", patch: { route_mode: "bus", condition: "rain", hour_of_day: 8, day_of_week: 1, is_rush_hour: 1, precipitation_mm: 3, wind_speed_kmh: 18, event_nearby: 1, event_proximity_km: 2, historical_avg_delay: 45, segment_km: 0.8 } },
  { name: "Night storm", icon: "M12 3v2M5.6 5.6l1.4 1.4M20 12h-2M18.4 5.6 17 7M12 19v2M5.6 18.4 7 17", patch: { route_mode: "rail", condition: "storm", hour_of_day: 23, day_of_week: 6, is_rush_hour: 0, precipitation_mm: 8, wind_speed_kmh: 35, event_nearby: 1, event_proximity_km: 1.5, historical_avg_delay: 50, segment_km: 1.2 } },
];

const DEFAULT_REQ: PredictionRequest = {
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
};

function Slider({ label, min, max, step, value, onChange, unit }: { label: string; min: number; max: number; step: number; value: number; onChange: (v: number) => void; unit?: string }) {
  return (
    <div className="field slider">
      <div className="slider-head">
        <label>{label}</label>
        <span className="slider-val">{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="field">
      <label>{label}</label>
      <div className="seg">
        {([["No", 0], ["Yes", 1]] as [string, number][]).map(([t, v]) => (
          <button key={t} className={value === v ? "seg-on" : ""} onClick={() => onChange(v)}>{t}</button>
        ))}
      </div>
    </div>
  );
}

export function MlPanel() {
  const [req, setReq] = useState<PredictionRequest>(DEFAULT_REQ);
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

  const bucket = res?.predicted_bucket ?? "";
  const probs = res?.probabilities;

  return (
    <div className="predictor">
      <div className="predictor-form">
        <div className="presets">
          {PRESETS.map((p) => (
            <button key={p.name} className="preset" onClick={() => setReq((r) => ({ ...r, ...p.patch }))}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
                <path d={p.icon} />
              </svg>
              {p.name}
            </button>
          ))}
        </div>

        <div className="ml-form">
          <div className="field">
            <label>Vehicle mode</label>
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
          <Toggle label="Rush hour" value={req.is_rush_hour} onChange={(v) => set("is_rush_hour", v)} />
          <Toggle label="Event nearby" value={req.event_nearby} onChange={(v) => set("event_nearby", v)} />

          <Slider label="Hour of day" min={0} max={23} step={1} value={req.hour_of_day} onChange={(v) => set("hour_of_day", v)} />
          <Slider label="Precipitation" min={0} max={10} step={0.5} value={req.precipitation_mm} onChange={(v) => set("precipitation_mm", v)} unit="mm" />
          <Slider label="Wind speed" min={0} max={50} step={1} value={req.wind_speed_kmh} onChange={(v) => set("wind_speed_kmh", v)} unit="km/h" />
          <Slider label="Segment length" min={0.1} max={3} step={0.1} value={req.segment_km} onChange={(v) => set("segment_km", v)} unit="km" />
          <Slider label="Historical avg delay" min={0} max={120} step={5} value={req.historical_avg_delay} onChange={(v) => set("historical_avg_delay", v)} unit="s" />
        </div>

        <div className="predictor-actions">
          <button className="btn" onClick={run} disabled={busy}>
            {busy ? "Predicting…" : "Predict trip delay"}
          </button>
        </div>
      </div>

      <div className="predictor-result">
        {!res && (
          <div className="empty" style={{ paddingTop: 60, paddingBottom: 60 }}>
            <div className="predictor-ico">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="26" height="26">
                <path d="M20 6 9 17l-5-5" />
              </svg>
            </div>
            <p style={{ marginTop: 12 }}>Configure a trip scenario and hit <b>Predict</b> to see the expected delay.</p>
          </div>
        )}

        {res?.loaded && (
          <>
            <div className="result-num">
              <span className="big">{Math.round(res.predicted_delay_seconds ?? 0)}</span>
              <span className="unit">s</span>
            </div>
            <div className="result-row">
              <span className="bucket-line">Expected delay</span>
              <span className={`bucket ${bucket}`}>{bucket}</span>
            </div>
            <p className="result-note">{BUCKET_NOTE[bucket] ?? ""}</p>

            {probs && (
              <div style={{ marginTop: 16 }}>
                <div className="faint small" style={{ marginBottom: 8 }}>MODEL CONFIDENCE</div>
                {Object.entries(probs).map(([k, v]) => (
                  <div key={k} style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
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
            <div className="model-foot">
              <span className="pill ok">model loaded</span>
              <span className="faint small">XGBoost · silver warehouse</span>
            </div>
          </>
        )}

        {res && !res.loaded && (
          <div className="empty">
            <div className="muted">model unavailable: {res.error ?? "not loaded"}</div>
          </div>
        )}
      </div>
    </div>
  );
}
