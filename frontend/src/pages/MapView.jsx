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
import MultiSelectDropdown from "../components/MultiSelectDropdown";

// Leaflet default marker icons are broken in bundled environments;
// point them at the CDN copies so they always resolve.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1/dist/images/marker-shadow.png",
});

const STATUS_OPTIONS = ["candidate", "verified", "needs_review", "rejected"];
const CATEGORY_OPTIONS = ["restaurant", "cafe", "food_truck", "brewery", "retail", "other"];

const PIN_COLORS = {
  verified: "#16a34a",
  candidate: "#2563eb",
  needs_review: "#d97706",
  rejected: "#dc2626",
};

const PIN_LABEL = {
  verified: "Verified",
  candidate: "Candidate",
  needs_review: "Needs Review",
  rejected: "Rejected",
};

function makePinIcon(status) {
  const color = PIN_COLORS[status] || "#6b7280";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 25 41" width="25" height="41">
    <path d="M12.5 0C5.6 0 0 5.6 0 12.5 0 21.9 12.5 41 12.5 41S25 21.9 25 12.5C25 5.6 19.4 0 12.5 0z" fill="${color}" stroke="white" stroke-width="1.5"/>
    <circle cx="12.5" cy="12.5" r="5" fill="white"/>
  </svg>`;
  return L.divIcon({
    html: svg,
    className: "",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -38],
  });
}

function formatPopupDate(event) {
  const confidence = event.date_confidence;
  if (!confidence || confidence === "exact") {
    if (!event.event_date) return null;
    const d = new Date(event.event_date + "T12:00:00");
    return { label: "Event Date", value: d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }) };
  }
  const start = event.date_range_start;
  const end = event.date_range_end;
  if (!start && !end) return null;
  const fmt = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  if (start && end && start === end) {
    return { label: "Event Date", value: fmt(start) };
  }
  const parts = [];
  if (start) parts.push(fmt(start));
  if (end) parts.push(fmt(end));
  const rangeStr = parts.length === 2 ? `${parts[0]} – ${parts[1]}` : parts[0];
  const confLabel = confidence === "month" ? "±month" : confidence === "year" ? "±year" : confidence === "season" ? "±season" : "~";
  return { label: "Est. Range", value: `${confLabel}  ${rangeStr}` };
}

function MapLegend() {
  return (
    <div style={{
      position: "absolute", bottom: 28, right: 12, zIndex: 1000,
      background: "rgba(255,255,255,0.95)", borderRadius: 8,
      padding: "10px 14px", boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
      fontSize: "0.8rem", lineHeight: 1.8, pointerEvents: "none",
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4, color: "#111" }}>Status</div>
      {Object.entries(PIN_COLORS).map(([status, color]) => (
        <div key={status} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%", background: color, flexShrink: 0 }} />
          <span style={{ color: "#374151" }}>{PIN_LABEL[status]}</span>
        </div>
      ))}
    </div>
  );
}

function todayIso() {
  return new Date().toISOString().split("T")[0];
}

function oneMonthFromNowIso() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  return d.toISOString().split("T")[0];
}

const DEFAULT_FILTERS = { status: [], category: [], startDate: todayIso(), endDate: oneMonthFromNowIso() };

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
        <MultiSelectDropdown
          label="Status"
          options={STATUS_OPTIONS}
          selected={pending.status}
          onChange={(v) => setPending((p) => ({ ...p, status: v }))}
        />
        <MultiSelectDropdown
          label="Category"
          options={CATEGORY_OPTIONS}
          selected={pending.category}
          onChange={(v) => setPending((p) => ({ ...p, category: v }))}
        />
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
            <Marker key={event.id} position={[event.lat, event.lon]} icon={makePinIcon(event.status)}>
              <Popup>
                <div style={{ minWidth: 180 }}>
                  <strong style={{ fontSize: "0.95rem" }}>{event.business_name || "(unnamed)"}</strong>
                  {event.category && (
                    <div style={{ marginTop: 2, fontSize: "0.78rem", color: "#6b7280", textTransform: "capitalize" }}>{event.category.replace("_", " ")}</div>
                  )}
                  <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: PIN_COLORS[event.status] || "#6b7280", display: "inline-block", flexShrink: 0 }} />
                    <span style={{ fontSize: "0.8rem", color: "#374151", textTransform: "capitalize" }}>{PIN_LABEL[event.status] || event.status}</span>
                  </div>
                  {(() => {
                    const d = formatPopupDate(event);
                    return d ? (
                      <div style={{ marginTop: 4, fontSize: "0.85rem", color: "#555" }}>
                        <span style={{ fontWeight: 600 }}>{d.label}:</span> {d.value}
                      </div>
                    ) : null;
                  })()}
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
        <MapLegend />
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
