import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { fetchEvents } from "../api/client";

const STATUS_OPTIONS = ["", "candidate", "verified", "rejected", "needs_review", "merged", "expired"];
const CATEGORY_OPTIONS = ["", "restaurant", "cafe", "food_truck", "brewery", "retail", "other"];

const STATUS_COLORS = {
  candidate: "#e8f4fd",
  verified: "#e9f7ef",
  rejected: "#fdecea",
  needs_review: "#fff8e1",
  merged: "#f3e5f5",
  expired: "#f5f5f5",
};

const STATUS_BORDER = {
  candidate: "#90caf9",
  verified: "#9fd2b2",
  rejected: "#ef9a9a",
  needs_review: "#ffe082",
  merged: "#ce93d8",
  expired: "#bdbdbd",
};

function StatusBadge({ status }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: "999px",
        fontSize: "0.78rem",
        background: STATUS_COLORS[status] || "#f5f5f5",
        border: `1px solid ${STATUS_BORDER[status] || "#ccc"}`,
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        fontWeight: 600,
      }}
    >
      {status}
    </span>
  );
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatEventDate(ev) {
  if (!ev.event_date) return "—";
  const conf = ev.date_confidence;
  if (!conf || conf === "exact") return formatDate(ev.event_date);
  const year = ev.event_date.slice(0, 4);
  if (conf === "unknown") return "Unknown";
  if (conf === "year") return `~${year}`;
  if (conf === "month") {
    const [y, m] = ev.event_date.slice(0, 7).split("-");
    return `~${new Date(+y, +m - 1, 1).toLocaleDateString("en-US", { month: "short", year: "numeric" })}`;
  }
  if (conf === "season" && ev.date_range_start) {
    const mo = parseInt(ev.date_range_start.slice(5, 7), 10);
    const season = mo <= 2 || mo === 12 ? "Winter" : mo <= 5 ? "Spring" : mo <= 8 ? "Summer" : "Fall";
    return `~${season} ${year}`;
  }
  return `~${year}`;
}

export default function EventList() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ status: "", category: "" });
  const [pending, setPending] = useState({ status: "", category: "" });

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchEvents(filters)
      .then(setEvents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  function applyFilters(e) {
    e.preventDefault();
    setFilters({ ...pending });
  }

  function clearFilters() {
    const empty = { status: "", category: "" };
    setPending(empty);
    setFilters(empty);
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>First In Line</h1>
          <p style={styles.subtitle}>Upcoming grand openings in Greenville, SC and beyond</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Link to="/map" style={{ ...styles.ingestLink, background: "#374151" }}>Map</Link>
          <Link to="/calendar" style={{ ...styles.ingestLink, background: "#374151" }}>Calendar</Link>
          <Link to="/admin/ingest" style={styles.ingestLink}>+ Ingest URL</Link>
          <Link to="/admin/review" style={{ ...styles.ingestLink, background: "#2563eb" }}>Review Queue</Link>
        </div>
      </header>

      {/* Filters */}
      <form onSubmit={applyFilters} style={styles.filterBar}>
        <label style={styles.filterLabel}>
          Status
          <select
            value={pending.status}
            onChange={(e) => setPending((p) => ({ ...p, status: e.target.value }))}
            style={styles.select}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s || "All statuses"}</option>
            ))}
          </select>
        </label>

        <label style={styles.filterLabel}>
          Category
          <select
            value={pending.category}
            onChange={(e) => setPending((p) => ({ ...p, category: e.target.value }))}
            style={styles.select}
          >
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c} value={c}>{c || "All categories"}</option>
            ))}
          </select>
        </label>

        <button type="submit" style={styles.btnPrimary}>Apply</button>
        <button type="button" onClick={clearFilters} style={styles.btnSecondary}>Clear</button>
      </form>

      {/* List */}
      {loading && <p style={styles.info}>Loading events…</p>}
      {error && <p style={styles.errorText}>Error: {error}</p>}
      {!loading && !error && events.length === 0 && (
        <p style={styles.info}>No events found for the current filters.</p>
      )}

      {!loading && !error && events.length > 0 && (
        <table style={styles.table}>
          <thead>
            <tr>
              {["Business", "Category", "Type", "Event Date", "Location", "Status", "Confidence"].map(
                (h) => <th key={h} style={styles.th}>{h}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {events.map((ev, i) => (
              <tr key={ev.id} style={{ background: i % 2 === 0 ? "#fff" : "#fafafa" }}>
                <td style={styles.td}>
                  <Link to={`/events/${ev.id}`} style={styles.link}>
                    {ev.business_name || ev.event_name || "Unnamed"}
                  </Link>
                </td>
                <td style={styles.td}>{ev.category || "—"}</td>
                <td style={styles.td}>{ev.event_type}</td>
                <td style={styles.td}>{formatEventDate(ev)}</td>
                <td style={styles.td}>{ev.city && ev.state ? `${ev.city}, ${ev.state}` : ev.city || ev.state || "—"}</td>
                <td style={styles.td}><StatusBadge status={ev.status} /></td>
                <td style={{ ...styles.td, textAlign: "right" }}>
                  {ev.confidence_score != null ? `${(ev.confidence_score * 100).toFixed(0)}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const styles = {
  container: {
    maxWidth: "1100px",
    margin: "0 auto",
    padding: "32px 24px",
    fontFamily: "Georgia, 'Times New Roman', serif",
    color: "#222",
  },
  header: {
    marginBottom: "28px",
    borderBottom: "2px solid #e0e0e0",
    paddingBottom: "16px",
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 16,
    flexWrap: "wrap",
  },
  title: { margin: 0, fontSize: "2rem", fontWeight: 700 },
  subtitle: { margin: "6px 0 0", color: "#666", fontSize: "1rem" },
  ingestLink: {
    display: "inline-block",
    padding: "8px 16px",
    background: "#0d6efd",
    color: "#fff",
    borderRadius: 6,
    textDecoration: "none",
    fontSize: 14,
    fontWeight: 600,
    whiteSpace: "nowrap",
    alignSelf: "center",
  },
  filterBar: {
    display: "flex",
    alignItems: "flex-end",
    gap: "16px",
    flexWrap: "wrap",
    marginBottom: "24px",
    padding: "16px",
    background: "#f9f9f9",
    border: "1px solid #e0e0e0",
    borderRadius: "8px",
  },
  filterLabel: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    fontSize: "0.85rem",
    fontWeight: 600,
    color: "#444",
    fontFamily: "system-ui, sans-serif",
  },
  select: {
    padding: "6px 10px",
    border: "1px solid #ccc",
    borderRadius: "4px",
    fontSize: "0.9rem",
    fontFamily: "system-ui, sans-serif",
    minWidth: "160px",
  },
  btnPrimary: {
    padding: "7px 18px",
    background: "#1a6b3a",
    color: "#fff",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "0.9rem",
    fontFamily: "system-ui, sans-serif",
    alignSelf: "flex-end",
  },
  btnSecondary: {
    padding: "7px 18px",
    background: "#fff",
    color: "#444",
    border: "1px solid #ccc",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "0.9rem",
    fontFamily: "system-ui, sans-serif",
    alignSelf: "flex-end",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "0.9rem",
    fontFamily: "system-ui, sans-serif",
  },
  th: {
    textAlign: "left",
    padding: "10px 12px",
    borderBottom: "2px solid #d0d0d0",
    fontWeight: 700,
    color: "#444",
    background: "#f5f5f5",
    fontSize: "0.8rem",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  td: {
    padding: "10px 12px",
    borderBottom: "1px solid #eee",
    verticalAlign: "middle",
  },
  link: { color: "#1a6b3a", textDecoration: "none", fontWeight: 600 },
  info: { color: "#888", fontStyle: "italic", fontFamily: "system-ui, sans-serif" },
  errorText: { color: "#c62828", fontFamily: "system-ui, sans-serif" },
};
