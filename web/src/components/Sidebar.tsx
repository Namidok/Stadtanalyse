import type { ReactNode } from "react";

export type ViewId = "landing" | "overview" | "map" | "analytics" | "ml" | "pipeline";

const ICONS: Record<ViewId, ReactNode> = {
  landing: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="19" height="19">
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
    </svg>
  ),
  overview: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="19" height="19">
      <path d="M3 3v18h18" />
      <path d="M7 15l3-4 3 3 4-6" />
    </svg>
  ),
  map: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="19" height="19">
      <path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  ),
  analytics: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="19" height="19">
      <path d="M3 3v18h18" />
      <path d="M7 13v3M12 9v7M17 5v11" />
    </svg>
  ),
  ml: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="19" height="19">
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <path d="M9 12a3 3 0 1 0 3-3" />
      <path d="M12 9V5" />
    </svg>
  ),
  pipeline: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="19" height="19">
      <circle cx="5" cy="6" r="2" />
      <circle cx="5" cy="18" r="2" />
      <circle cx="19" cy="12" r="2" />
      <path d="M5 8v8M7 6h6a3 3 0 0 1 3 3v1M19 10v2" />
    </svg>
  ),
};

const NAV: Array<{ id: ViewId; label: string }> = [
  { id: "landing", label: "Home" },
];

const DASH: Array<{ id: ViewId; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "map", label: "Live Map" },
  { id: "analytics", label: "Analytics" },
  { id: "ml", label: "Delay Predictor" },
  { id: "pipeline", label: "Data Pipeline" },
];

function NavList({ items, view, onView }: { items: Array<{ id: ViewId; label: string }>; view: ViewId; onView: (v: ViewId) => void }) {
  return (
    <>
      {items.map((it) => (
        <div key={it.id} className={`nav-item ${view === it.id ? "active" : ""}`} onClick={() => onView(it.id)}>
          <span className="nav-icon">{ICONS[it.id]}</span>
          {it.label}
        </div>
      ))}
    </>
  );
}

export function Sidebar({
  view,
  onView,
  live,
  source,
  vehicles,
  city,
}: {
  view: ViewId;
  onView: (v: ViewId) => void;
  live: boolean;
  source: string;
  vehicles: number;
  city: string;
}) {
  return (
    <aside className="sidebar">
      <div className="brand" onClick={() => onView("landing")}>
        <div className="mark">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" width="20" height="20">
            <path d="M3 13l3-8 3 8M7 13v6M17 8a3 3 0 1 0 3 3M17 11v8M9 19h8" />
          </svg>
        </div>
        <div>
          <div className="name">
            Stadt<em>analyse</em>
          </div>
          <div className="tag">Urban Mobility Ops</div>
        </div>
      </div>

      <div className="nav-section">Workspace</div>
      <NavList items={NAV} view={view} onView={onView} />
      <div className="nav-section">Dashboard</div>
      <NavList items={DASH} view={view} onView={onView} />

      <div className="spacer" />

      <div className="side-foot">
        <div className="row">
          {live ? <span className="pill-live" style={{ padding: "2px 8px" }}>LIVE</span> : <span className="pill-snap" style={{ padding: "2px 8px" }}>SNAPSHOT</span>}
        </div>
        <div className="row">
          City <b>{city}</b>
        </div>
        <div className="row">
          Vehicles <b>{vehicles}</b>
        </div>
        <div className="row">
          Source <b style={{ textTransform: "lowercase" }}>{source}</b>
        </div>
      </div>
    </aside>
  );
}
