import type { DataSource } from "../api";

/** LIVE only when the API reports real data arriving over Kafka right now and
 *  the SSE stream is connected. Memory mode / synthetic data is never "live". */
export function isLiveStream(source: DataSource | null, streaming: boolean): boolean {
  return streaming && source?.live === true;
}

export function StreamBadge({ apiOnline, source, streaming, city }: { apiOnline: boolean | null; source: DataSource | null; streaming: boolean; city?: string }) {
  if (apiOnline === false) return <span className="pill-offline">DEMO API OFFLINE</span>;
  if (isLiveStream(source, streaming)) {
    return <span className="pill-live">LIVE · KAFKA STREAM{city ? ` · ${city.toUpperCase()}` : ""}</span>;
  }
  if (!source) return <span className="pill-snap">CONNECTING…</span>;
  if (source.memory_mode || source.mode === "synthetic") return <span className="pill-snap">DEMO SNAPSHOT (synthetic data)</span>;
  return <span className="pill-snap">WAREHOUSE SNAPSHOT · KAFKA NOT CONNECTED</span>;
}
