import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Hotspot, TrendPoint, WeatherImpact } from "../api";
import { CONDITION_COLORS } from "../api";

const TOOLTIP_STYLE = {
  background: "#111a2e",
  border: "1px solid #1e2a44",
  borderRadius: 8,
  fontSize: 12,
};

export function TrendsChart({ trends }: { trends: TrendPoint[] }) {
  const data = trends.map((t) => ({
    label: new Date(t.bucket).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    "avg delay (s)": Math.round(t.avg_delay_seconds),
    "on-time %": t.on_time_pct,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data}>
        <CartesianGrid stroke="#1e2a44" strokeDasharray="3 3" />
        <XAxis dataKey="label" stroke="#7d8db1" fontSize={10} interval="preserveStartEnd" />
        <YAxis stroke="#7d8db1" fontSize={10} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line type="monotone" dataKey="avg delay (s)" stroke="#38bdf8" dot={false} strokeWidth={2} />
        <Line type="monotone" dataKey="on-time %" stroke="#4ade80" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function HotspotChart({ hotspots }: { hotspots: Hotspot[] }) {
  const data = hotspots.slice(0, 10).map((h) => ({
    cell: h.grid_cell.split("|")[1],
    "avg delay (s)": Math.round(h.avg_delay_seconds),
    vehicles: h.vehicles,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} layout="vertical" margin={{ left: 0 }}>
        <CartesianGrid stroke="#1e2a44" strokeDasharray="3 3" />
        <XAxis type="number" stroke="#7d8db1" fontSize={10} />
        <YAxis dataKey="cell" type="category" stroke="#7d8db1" fontSize={10} width={50} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Bar dataKey="avg delay (s)" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={i < 3 ? "#f87171" : "#facc15"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ImpactChart({ data }: { data: WeatherImpact[] }) {
  const rows = data.map((d) => ({
    condition: d.condition,
    "avg delay (s)": Math.round(d.avg_delay_seconds),
    "on-time %": d.on_time_pct,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows}>
        <CartesianGrid stroke="#1e2a44" strokeDasharray="3 3" />
        <XAxis dataKey="condition" stroke="#7d8db1" fontSize={10} />
        <YAxis stroke="#7d8db1" fontSize={10} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="avg delay (s)" radius={[4, 4, 0, 0]}>
          {rows.map((r) => (
            <Cell key={r.condition} fill={CONDITION_COLORS[r.condition] ?? "#94a3b8"} />
          ))}
        </Bar>
        <Bar dataKey="on-time %" fill="#4ade80" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
