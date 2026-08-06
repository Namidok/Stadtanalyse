import L from "leaflet";
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, Tooltip } from "react-leaflet";
import { CONDITION_COLORS, fmtDelay, MODE_COLORS, type CityEvent, type VehiclePosition, type WeatherObservation } from "../api";

interface Props {
  positions: VehiclePosition[];
  events: CityEvent[];
  weather: WeatherObservation[];
  height?: number;
}

function delayClass(delay: number | undefined): string {
  if (delay == null || delay <= 30) return "on-time";
  if (delay <= 120) return "mid";
  if (delay <= 300) return "late";
  return "severe";
}

function modeClass(mode: string | undefined): string {
  if (mode === "rail" || mode === "tram" || mode === "bus") return mode;
  return "";
}

function makePinIcon(p: VehiclePosition): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div class="pin ${delayClass(p.delay_seconds)} ${modeClass(p.route_mode)}"></div>`,
    iconSize: [13, 13],
    iconAnchor: [7, 7],
  });
}

function makeEventIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: '<div class="event-ripple"><div class="event-core"></div></div>',
    iconSize: [4, 4],
    iconAnchor: [2, 2],
  });
}

export function LiveMap({ positions, events, weather, height = 460 }: Props) {
  return (
    <div style={{ position: "relative" }}>
      <div className="map-wrap" style={{ height }}>
        <MapContainer center={[52.52, 13.405]} zoom={12} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />

          {weather.map((z) => (
            <CircleMarker
              key={`w-${z.zone_id}`}
              center={[z.lat, z.lon]}
              radius={18}
              pathOptions={{
                color: CONDITION_COLORS[z.condition] ?? "#94a3b8",
                opacity: 0.45,
                fillOpacity: 0.14,
                weight: 1.2,
              }}
            >
              <Tooltip>
                <b>{z.zone_id}</b> · {z.condition} · {z.temperature_c.toFixed(1)}°C
              </Tooltip>
            </CircleMarker>
          ))}

          {events.map((e) => (
            <Marker key={`e-${e.event_id}`} position={[e.lat, e.lon]} icon={makeEventIcon()}>
              <Popup>
                <b>{e.name}</b> <span className="muted">({e.category})</span>
                <br />
                attendance ~{e.expected_attendance.toLocaleString()} · impact {e.impact.toFixed(1)}
              </Popup>
            </Marker>
          ))}

          {positions.slice(0, 400).map((p) => (
            <Marker key={p.vehicle_id} position={[p.lat, p.lon]} icon={makePinIcon(p)}>
              <Popup>
                <b>{p.vehicle_id}</b> · {p.route_mode} · route {p.route_id}
                <br />
                delay <b>{fmtDelay(p.delay_seconds ?? 0)}</b> · {p.speed_kmh?.toFixed(1)} km/h
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      <div className="map-legend">
        <span><span className="dot" style={{ background: MODE_COLORS.rail ?? "#60a5fa" }} />rail</span>
        <span><span className="dot" style={{ background: MODE_COLORS.tram ?? "#a78bfa" }} />tram</span>
        <span><span className="dot" style={{ background: MODE_COLORS.bus ?? "#fbbf24" }} />bus</span>
        <span className="faint">·</span>
        <span><span className="dot" style={{ background: "#34d399" }} />on-time</span>
        <span><span className="dot" style={{ background: "#fb923c" }} />delayed</span>
        <span><span className="dot" style={{ background: "#f87171" }} />severe</span>
        <span className="faint">·</span>
        <span><span className="dot" style={{ background: "#f472b6", borderRadius: "50%" }} />event</span>
      </div>
    </div>
  );
}
