// API client + shared types for the Stadtanalyse dashboard.
export interface VehiclePosition {
  vehicle_id: string;
  route_id: string;
  route_mode: string;
  trip_id?: string;
  lat: number;
  lon: number;
  speed_kmh?: number;
  delay_seconds?: number;
  congestion_level?: number;
  event_ts?: string;
}

export interface WeatherObservation {
  zone_id: string;
  lat: number;
  lon: number;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_kmh: number;
  precipitation_mm: number;
  condition: string;
  visibility_km: number;
  event_ts?: string;
}

export interface CityEvent {
  event_id: string;
  name: string;
  category: string;
  lat: number;
  lon: number;
  start_time_utc: string;
  end_time_utc: string;
  expected_attendance: number;
  impact: number;
  impact_radius_km: number;
  status: string;
}

export interface Kpis {
  vehicles_tracked: number;
  avg_delay_seconds: number;
  on_time_pct: number;
  severe_delays: number;
  avg_speed_kmh: number;
  active_events: number;
  data_source: string;
}

export interface RouteReliability {
  route_id: string;
  route_mode: string;
  avg_delay_seconds: number;
  p95_delay_seconds: number;
  on_time_pct: number;
  severe_pct: number;
  stops_observed: number;
}

export interface TrendPoint {
  bucket: string;
  avg_delay_seconds: number;
  observations: number;
  on_time_pct: number;
}

export interface Hotspot {
  grid_cell: string;
  lat: number;
  lon: number;
  avg_delay_seconds: number;
  avg_speed_kmh: number;
  avg_congestion: number;
  vehicles: number;
}

export interface WeatherImpact {
  condition: string;
  observations: number;
  avg_delay_seconds: number;
  on_time_pct: number;
}

export interface EventImpact {
  proximity_bucket: string;
  observations: number;
  avg_delay_seconds: number;
  on_time_pct: number;
  avg_event_impact: number;
}

export interface PipelineStatus {
  ingestion: {
    total_records: number;
    rates: Record<string, number>;
    counters: Record<string, number>;
    uptime_seconds: number;
  };
  warehouse: { mode: string };
  quality: { last_run: string | null };
  streaming: { vehicles_in_snapshot: number };
}

export interface Prediction {
  loaded: boolean;
  error?: string | null;
  predicted_delay_seconds?: number;
  predicted_bucket?: string;
  probabilities?: Record<string, number>;
  features_used?: Record<string, unknown>;
}

export interface PredictionRequest {
  route_mode: string;
  condition: string;
  hour_of_day: number;
  day_of_week: number;
  is_rush_hour: number;
  segment_km: number;
  temperature_c: number;
  precipitation_mm: number;
  wind_speed_kmh: number;
  event_proximity_km: number;
  event_nearby: number;
  historical_avg_delay: number;
  stop_zone_num: number;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  kpis: () => get<Kpis>("/api/v1/kpis"),
  positions: () => get<{ positions: VehiclePosition[] }>("/api/v1/live/snapshot"),
  routes: () => get<RouteReliability[]>("/api/v1/routes/reliability"),
  trends: (hours = 24) => get<TrendPoint[]>(`/api/v1/delays/trends?hours=${hours}`),
  hotspots: () => get<Hotspot[]>("/api/v1/hotspots"),
  weatherCurrent: () => get<{ city: WeatherObservation | null; zones: WeatherObservation[] }>("/api/v1/weather/current"),
  weatherImpact: () => get<WeatherImpact[]>("/api/v1/weather/impact"),
  eventsActive: () => get<CityEvent[]>("/api/v1/events/active"),
  eventsImpact: () => get<EventImpact[]>("/api/v1/events/impact"),
  pipeline: () => get<PipelineStatus>("/api/v1/monitoring/pipeline"),
  predict: (req: PredictionRequest) => post<Prediction>("/api/v1/ml/predict", req),
};

export function positionsStream(onPositions: (p: VehiclePosition[]) => void, onError: () => void): () => void {
  let es: EventSource | null = null;
  try {
    es = new EventSource("/api/v1/live/positions/stream");
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as { positions: VehiclePosition[] };
        onPositions(data.positions);
      } catch {
        /* ignore malformed frames */
      }
    };
    es.onerror = () => {
      es?.close();
      onError();
    };
  } catch {
    onError();
  }
  return () => es?.close();
}

export const CONDITION_COLORS: Record<string, string> = {
  clear: "#4ade80",
  partly_cloudy: "#a3e635",
  cloudy: "#facc15",
  fog: "#94a3b8",
  rain: "#60a5fa",
  storm: "#a855f7",
  snow: "#e2e8f0",
};

export const MODE_COLORS: Record<string, string> = {
  rail: "#3b82f6",
  tram: "#8b5cf6",
  bus: "#f59e0b",
};

export function fmtDelay(sec: number): string {
  if (sec <= 0) return "on time";
  const m = Math.floor(sec / 60);
  return m >= 1 ? `${m}m ${Math.round(sec % 60)}s` : `${Math.round(sec)}s`;
}
