/**
 * MapView page — renders geocoded events as Leaflet pins.
 *
 * Only shows events that have both lat and lon set. Non-geocoded
 * events are silently excluded (they cannot be placed on the map).
 */

import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { fetchMapEvents } from "../api/mapClient";

// Leaflet default marker icons are broken in bundled environments;
// point them at the CDN copies so they always resolve.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1/dist/images/marker-shadow.png",
});

const STATUS_OPTIONS = ["", "candidate", "verified", "needs_review", "rejected"];
const CATEGORY_OPTIONS = ["", "restaurant", "cafe", "food_truck", "brewery", "retail", "other"];

const STATUS_COLORS = {
  candidate: "#e8f4fd",
  verified: "#e9f7ef",
  rejected: "#fdecea",
  needs_review: "#fff8e1",
  expired: "#f5f5f5",
};

const STATUS_BORDER = {
  candidate: "#90caf9",
  verified: "#9fd2b2",
  rejected: "#ef9a9a",
  needs_review: "#ffe082",
  expired: "#bdbdbd",
};

function StatusBadge({ status }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 10px",
      borderRadius: "999px",
      fontSize: "0.78rem",
      background: STATUS_COLORS[status] || "#f5f5f5",
      border: `1px solid ${STATUS_BORDER[status] || "#ccc"}`,
      textTransform: "uppercase",
      letterSpacing: "0.04em",
      fontWeight: 600,
    }}>
      {status}
    </span>
  );
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

function todayIso() {
  return new Date().toISOString().split("T")[0];
}

function oneMonthFromNowIso() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  return d.toISOString().split("T")[0];
}

const DEFAULT_FILTERS = { status: "", category: "", startDate: todayIso(), endDate: oneMonthFromNowIso() };

export default function MapView() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [pending, setPending] = useState(DEFAULT_FILTERS);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchMapEvents(filters)
      .then(setEvents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  function applyFilters(e) {
    e.preventDefault();
    setFilters({ ...pending });
  }

  function clearFilters() {
    const reset = { ...DEFAULT_FILTERS };
    setPending(reset);
    setFilters(reset);
  }

  // Default center: Greenville, SC
  const defaultCenter = [34.8526, -82.394];
  const defaultZoom = 12;

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>Map View</h1>
          <p style={styles.subtitle}>
            {loading ? "Loading pins…" : `${events.length} geocoded event${events.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/" style={styles.navLink}>Event List</Link>
          <Link to="/calendar" style={styles.navLink}>Calendar</Link>
          <Link to="/admin/ingest" style={{ ...styles.navLink, background: "#16a34a" }}>+ Ingest URL</Link>
        </div>
      </header>

      <form onSubmit={applyFilters} style={styles.filterBar}>
        <label style={styles.filterLabel}>
          Status
          <select value={pending.status} onChange={(e) => setPending((p) => ({ ...p, status: e.target.value }))} style={styles.select}>
            {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s || "All"}</option>)}
          </select>
        </label>
        <label style={styles.filterLabel}>
          Category
          <select value={pending.category} onChange={(e) => setPending((p) => ({ ...p, category: e.target.value }))} style={styles.select}>
            {CATEGORY_OPTIONS.map((c) => <option key={c} value={c}>{c || "All"}</option>)}
          </select>
        </label>
        <label style={styles.filterLabel}>
          From
          <input type="date" value={pending.startDate} onChange={(e) => setPending((p) => ({ ...p, startDate: e.target.value }))} style={styles.select} />
        </label>
        <label style={styles.filterLabel}>
          To
          <input type="date" value={pending.endDate} onChange={(e) => setPending((p) => ({ ...p, endDate: e.target.value }))} style={styles.select} />
        </label>
        <button type="submit" style={styles.applyBtn}>Apply</button>
        <button type="button" onClick={clearFilters} style={styles.clearBtn}>Clear</button>
      </form>

      {error && <p style={styles.error}>Error: {error}</p>}

      <div style={styles.mapWrapper}>
        <MapContainer
          center={defaultCenter}
          zoom={defaultZoom}
          style={{ height: "520px", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {events.map((event) => (
            <Marker key={event.id} position={[event.lat, event.lon]}>
              <Popup>
                <div style={{ minWidth: 180 }}>
                  <strong style={{ fontSize: "0.95rem" }}>{event.business_name || "(unnamed)"}</strong>
                  <div style={{ marginTop: 4 }}>
                    <StatusBadge status={event.status} />
                  </div>
                  {event.event_date && (
                    <div style={{ marginTop: 4, fontSize: "0.85rem", color: "#555" }}>
                      {formatDate(event.event_date)}
                    </div>
                  )}
                  {event.address && (
                    <div style={{ marginTop: 2, fontSize: "0.82rem", color: "#666" }}>{event.address}</div>
                  )}
                  <div style={{ marginTop: 8 }}>
                    <a href={`/events/${event.id}`} style={{ color: "#2563eb", fontSize: "0.85rem" }}>
                      View detail →
                    </a>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {!loading && events.length === 0 && !error && (
        <p style={styles.empty}>No geocoded events match your filters. Geocode events to see them on the map.</p>
      )}
    </div>
  );
}

const styles = {
  container: { minHeight: "100vh", background: "#f8fafc", fontFamily: "system-ui, sans-serif", display: "flex", flexDirection: "column" },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, padding: "20px 32px 12px", background: "#fff", borderBottom: "1px solid #e5e7eb" },
  title: { margin: 0, fontSize: "1.6rem", color: "#111827", fontWeight: 700 },
  subtitle: { margin: "4px 0 0", color: "#6b7280", fontSize: "0.92rem" },
  navLink: { textDecoration: "none", padding: "7px 16px", borderRadius: 6, background: "#374151", color: "#fff", fontWeight: 600, fontSize: "0.88rem" },
  filterBar: { display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end", padding: "12px 32px", background: "#fff", borderBottom: "1px solid #e5e7eb" },
  filterLabel: { display: "flex", flexDirection: "column", gap: 3, fontSize: "0.82rem", fontWeight: 600, color: "#374151" },
  select: { padding: "5px 8px", borderRadius: 5, border: "1px solid #d1d5db", fontSize: "0.9rem", minWidth: 130 },
  applyBtn: { padding: "6px 18px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, fontSize: "0.9rem", cursor: "pointer" },
  clearBtn: { padding: "6px 14px", background: "#e5e7eb", color: "#374151", border: "none", borderRadius: 6, fontWeight: 600, fontSize: "0.9rem", cursor: "pointer" },
  mapWrapper: { flex: 1, minHeight: 520, padding: "16px 32px" },
  error: { color: "#dc2626", padding: "8px 32px", margin: 0 },
  empty: { textAlign: "center", color: "#9ca3af", padding: 32, fontSize: "0.95rem" },
};
