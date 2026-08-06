/** Semi-circular gauge with a gradient arc (0–100 scale). */
export function Gauge({ value, size = 150, label = "" }: { value: number; size?: number; label?: string }) {
  const v = Math.max(0, Math.min(100, value));
  const stroke = 11;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = Math.PI * r; // semicircle length
  const filled = (v / 100) * circ;
  const color = v >= 85 ? "#34d399" : v >= 60 ? "#fbbf24" : "#f87171";
  return (
    <svg width={size} height={size / 2 + stroke} viewBox={`0 0 ${size} ${size / 2 + stroke}`}>
      <defs>
        <linearGradient id="gauge-grad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#818cf8" />
        </linearGradient>
      </defs>
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke="rgba(148,163,184,0.15)"
        strokeWidth={stroke}
        strokeLinecap="round"
      />
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${filled} ${circ}`}
        style={{ transition: "stroke-dasharray 0.8s ease" }}
      />
      <text x={cx} y={cy + 2} textAnchor="middle" fontSize={size * 0.16} fontWeight={700} fill="#e6edf7" fontFamily="Space Grotesk, sans-serif">
        {Math.round(v)}
        <tspan fontSize={size * 0.09} fill="#5b6b85">%</tspan>
      </text>
      {label && (
        <text x={cx} y={cy + size * 0.14} textAnchor="middle" fontSize={size * 0.055} fill="#5b6b85" fontWeight={600} letterSpacing={2}>
          {label.toUpperCase()}
        </text>
      )}
    </svg>
  );
}
