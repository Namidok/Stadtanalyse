import { useEffect } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import { CONDITION_COLORS, MODE_COLORS, fmtDelay, type CityEvent, type VehiclePosition, type WeatherObservation } from "../api";

interface Props {
  positions: VehiclePosition[];
  events: CityEvent[];
  weather: WeatherObservation[];
}

function delayColor(delay: number | undefined): string {
  if (delay == null || delay <= 30) return "#4ade80";
  if (delay <= 120) return "#facc15";
  if (delay <= 300) return "#fb923c";
  return "#f87171";
}

export function LiveMap({ positions, events, weather }: Props) {
  useEffect(() => {
    // reset any stale map sizing after data swap
  }, [positions.length]);

  return (
    <MapContainer
      center={[52.52, 13.405]}
      zoom={12}
      scrollWheelZoom
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {weather.map((z) => (
        <CircleMarker
          key={`w-${z.zone_id}`}
          center={[z.lat, z.lon]}
          radius={16}
          pathOptions={{
            color: CONDITION_COLORS[z.condition] ?? "#94a3b8",
            opacity: 0.5,
            fillOpacity: 0.18,
            weight: 1,
          }}
        >
          <Tooltip>
            {z.zone_id} · {z.condition} · {z.temperature_c.toFixed(1)}°C
          </Tooltip>
        </CircleMarker>
      ))}

      {events.map((e) => (
        <CircleMarker
          key={`e-${e.event_id}`}
          center={[e.lat, e.lon]}
          radius={10 + Math.min(18, e.impact * 12)}
          pathOptions={{ color: "#f472b6", opacity: 0.9, fillOpacity: 0.25, weight: 1.5, dashArray: "4 4" }}
        >
          <Popup>
            <b>{e.name}</b> <span className="muted">({e.category})</span>
            <br />
            attendance ~{e.expected_attendance.toLocaleString()} · impact {e.impact.toFixed(1)}
          </Popup>
        </CircleMarker>
      ))}

      {positions.slice(0, 300).map((p) => (
        <CircleMarker
          key={p.vehicle_id}
          center={[p.lat, p.lon]}
          radius={4}
          pathOptions={{
            color: delayColor(p.delay_seconds),
            fillColor: MODE_COLORS[p.route_mode] ?? delayColor(p.delay_seconds),
            fillOpacity: 0.9,
            weight: 1,
            opacity: 0.9,
          }}
        >
          <Popup>
            <b>{p.vehicle_id}</b> · {p.route_mode} · route {p.route_id}
            <br />
            delay <b>{fmtDelay(p.delay_seconds ?? 0)}</b> · {p.speed_kmh?.toFixed(1)} km/h
            <br />
            congestion {p.congestion_level?.toFixed(2)}
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
