import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { fetchEvent, fetchEventSources, fetchEventClaims, patchEventStatus } from "../api/client";
import NavBar from "../components/NavBar";

const STATUS_COLORS = {
  candidate: { bg: "#e8f4fd", border: "#90caf9" },
  verified: { bg: "#e9f7ef", border: "#9fd2b2" },
  rejected: { bg: "#fdecea", border: "#ef9a9a" },
  needs_review: { bg: "#fff8e1", border: "#ffe082" },
  merged: { bg: "#f3e5f5", border: "#ce93d8" },
  expired: { bg: "#f5f5f5", border: "#bdbdbd" },
};

function StatusBadge({ status }) {
  const c = STATUS_COLORS[status] || { bg: "#f5f5f5", border: "#ccc" };
  return (
    <span style={{
      display: "inline-block",
      padding: "3px 12px",
      borderRadius: "999px",
      fontSize: "0.8rem",
      background: c.bg,
      border: `1px solid ${c.border}`,
      textTransform: "uppercase",
      letterSpacing: "0.05em",
      fontWeight: 700,
    }}>
      {status}
    </span>
  );
}

function Field({ label, value }) {
  if (value == null || value === "") return null;
  return (
    <div style={styles.field}>
      <dt style={styles.fieldLabel}>{label}</dt>
      <dd style={styles.fieldValue}>{String(value)}</dd>
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric", month: "long", day: "numeric",
    hour: "2-digit", minute: "2-digit", timeZoneName: "short",
  });
}

function formatDateConfidence(event) {
  const conf = event.date_confidence;
  if (!conf || conf === "exact") return null;
  const labels = {
    month: "Month (approximate)",
    season: "Season (approximate)",
    year: "Year only (approximate)",
    unknown: "Unknown",
  };
  return labels[conf] || conf;
}

function formatDateRange(event) {
  if (!event.date_range_start || !event.date_range_end) return null;
  const fmt = (iso) =>
    new Date(iso + "T12:00:00").toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
    });
  return `${fmt(event.date_range_start)} – ${fmt(event.date_range_end)}`;
}

function ClaimsSection({ eventId }) {
  const [claims, setClaims] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEventClaims(eventId)
      .then(setClaims)
      .catch((e) => setError(e.message));
  }, [eventId]);

  if (error) return <p style={styles.errorText}>Failed to load claims: {error}</p>;
  if (!claims) return <p style={styles.muted}>Loading claims…</p>;
  if (claims.length === 0) return <p style={styles.muted}>No claims recorded for this event.</p>;

  return (
    <table style={styles.innerTable}>
      <thead>
        <tr>
          {["Type", "Value", "Evidence", "Confidence"].map((h) => (
            <th key={h} style={styles.th}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {claims.map((c, i) => (
          <tr key={c.id} style={{ background: i % 2 === 0 ? "#fff" : "#fafafa" }}>
            <td style={styles.td}>{c.claim_type}</td>
            <td style={styles.td}>{c.claim_value || "—"}</td>
            <td style={{ ...styles.td, maxWidth: "320px", fontStyle: "italic", color: "#555" }}>
              {c.claim_text ? `"${c.claim_text}"` : "—"}
            </td>
            <td style={{ ...styles.td, textAlign: "right" }}>
              {c.confidence_score != null ? `${(c.confidence_score * 100).toFixed(0)}%` : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SourcesSection({ eventId }) {
  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEventSources(eventId)
      .then(setSources)
      .catch((e) => setError(e.message));
  }, [eventId]);

  if (error) return <p style={styles.errorText}>Failed to load sources: {error}</p>;
  if (!sources) return <p style={styles.muted}>Loading sources…</p>;
  if (sources.length === 0) return <p style={styles.muted}>No source documents linked to this event.</p>;

  return (
    <div>
      {sources.map((s) => {
        const doc = s.source_document;
        return (
          <div key={s.id} style={styles.sourceCard}>
            <div style={styles.sourceTitle}>
              <a href={doc.url} target="_blank" rel="noopener noreferrer" style={styles.sourceLink}>
                {doc.title || doc.url}
              </a>
              <span style={styles.sourceBadge}>{s.relationship_type}</span>
            </div>
            <div style={styles.sourceMeta}>
              <span>{doc.domain || "unknown domain"}</span>
              {doc.fetched_at && <span> · fetched {new Date(doc.fetched_at).toLocaleDateString()}</span>}
              {doc.http_status && <span> · HTTP {doc.http_status}</span>}
            </div>
            {doc.canonical_url && doc.canonical_url !== doc.url && (
              <div style={styles.sourceMeta}>
                Canonical: <a href={doc.canonical_url} target="_blank" rel="noopener noreferrer" style={styles.sourceLink}>{doc.canonical_url}</a>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function EventDetail() {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("claims");
  const [statusMsg, setStatusMsg] = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchEvent(eventId)
      .then(setEvent)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [eventId]);

  async function handleStatusChange(newStatus) {
    setStatusLoading(true);
    setStatusMsg(null);
    try {
      const updated = await patchEventStatus(eventId, newStatus);
      setEvent(updated);
      setStatusMsg(`Status updated to "${newStatus}".`);
    } catch (e) {
      setStatusMsg(`Error: ${e.message}`);
    } finally {
      setStatusLoading(false);
    }
  }

  if (loading) return <div style={styles.container}><p style={styles.muted}>Loading event…</p></div>;
  if (error) return (
    <div style={styles.container}>
      <p style={styles.errorText}>Failed to load event: {error}</p>
      <Link to="/" style={styles.backLink}>← Back to list</Link>
    </div>
  );
  if (!event) return null;

  return (
    <div style={styles.container}>
      <NavBar />
      <Link to="/" style={styles.backLink}>← Back to list</Link>

      <header style={styles.eventHeader}>
        <div>
          <h1 style={styles.eventTitle}>{event.business_name || event.event_name || "Unnamed Event"}</h1>
          {event.event_name && event.business_name && (
            <p style={styles.eventSubtitle}>{event.event_name}</p>
          )}
        </div>
        <StatusBadge status={event.status} />
      </header>

      {/* Details */}
      <section style={styles.section}>
        <h2 style={styles.sectionHeading}>Event Details</h2>
        <dl style={styles.fieldGrid}>
          <Field label="Type" value={event.event_type} />
          <Field label="Category" value={event.category} />
          {(!event.date_confidence || event.date_confidence === "exact") ? (
            <Field label="Event Date" value={
              event.event_date
                ? new Date(event.event_date + "T12:00:00").toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })
                : null
            } />
          ) : (
            <>
              <Field label="Date Confidence" value={formatDateConfidence(event)} />
              <Field label="Estimated Range" value={formatDateRange(event)} />
            </>
          )}
          <Field label="Address" value={event.address} />
          <Field label="City" value={event.city} />
          <Field label="State" value={event.state} />
          <Field label="Country" value={event.country} />
          <Field label="Coordinates" value={event.lat != null ? `${event.lat}, ${event.lon}` : null} />
          <Field label="Confidence" value={event.confidence_score != null ? `${(event.confidence_score * 100).toFixed(0)}%` : null} />
          <Field label="Created" value={formatDate(event.created_at)} />
          <Field label="Updated" value={formatDate(event.updated_at)} />
        </dl>
        {event.promotion_text && (
          <div style={styles.promoBox}>
            <strong>Promotion:</strong> {event.promotion_text}
          </div>
        )}
        {event.notes && (
          <div style={styles.notesBox}>
            <strong>Notes:</strong> {event.notes}
          </div>
        )}
      </section>

      {/* Admin Actions */}
      <section style={styles.section}>
        <h2 style={styles.sectionHeading}>Admin Actions</h2>
        <div style={styles.adminBar}>
          <button
            style={{ ...styles.adminBtn, ...styles.verifyBtn }}
            onClick={() => handleStatusChange("verified")}
            disabled={statusLoading || event.status === "verified"}
          >
            ✓ Verify
          </button>
          <button
            style={{ ...styles.adminBtn, ...styles.rejectBtn }}
            onClick={() => handleStatusChange("rejected")}
            disabled={statusLoading || event.status === "rejected"}
          >
            ✗ Reject
          </button>
          <button
            style={{ ...styles.adminBtn, ...styles.reviewBtn }}
            onClick={() => handleStatusChange("needs_review")}
            disabled={statusLoading || event.status === "needs_review"}
          >
            ⚑ Flag for Review
          </button>
        </div>
        {statusMsg && (
          <p style={statusMsg.startsWith("Error") ? styles.errorText : styles.successText}>
            {statusMsg}
          </p>
        )}
      </section>

      {/* Tabs: Claims / Sources */}
      <section style={styles.section}>
        <div style={styles.tabBar}>
          <button
            style={{ ...styles.tab, ...(activeTab === "claims" ? styles.tabActive : {}) }}
            onClick={() => setActiveTab("claims")}
          >
            Claims
          </button>
          <button
            style={{ ...styles.tab, ...(activeTab === "sources" ? styles.tabActive : {}) }}
            onClick={() => setActiveTab("sources")}
          >
            Sources
          </button>
        </div>
        <div style={styles.tabPanel}>
          {activeTab === "claims" && <ClaimsSection eventId={eventId} />}
          {activeTab === "sources" && <SourcesSection eventId={eventId} />}
        </div>
      </section>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: "960px",
    margin: "0 auto",
    padding: "32px 24px",
    fontFamily: "Georgia, 'Times New Roman', serif",
    color: "#222",
  },
  backLink: {
    display: "inline-block",
    marginBottom: "20px",
    color: "#1a6b3a",
    textDecoration: "none",
    fontSize: "0.9rem",
    fontFamily: "system-ui, sans-serif",
  },
  eventHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "16px",
    borderBottom: "2px solid #e0e0e0",
    paddingBottom: "16px",
    marginBottom: "28px",
  },
  eventTitle: { margin: 0, fontSize: "1.8rem", fontWeight: 700 },
  eventSubtitle: { margin: "4px 0 0", color: "#666", fontSize: "1rem" },
  section: {
    marginBottom: "36px",
  },
  sectionHeading: {
    fontSize: "1rem",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "#444",
    marginBottom: "12px",
    fontFamily: "system-ui, sans-serif",
    borderBottom: "1px solid #eee",
    paddingBottom: "6px",
  },
  fieldGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
    gap: "12px",
    margin: 0,
    padding: 0,
  },
  field: { listStyle: "none" },
  fieldLabel: {
    fontSize: "0.75rem",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "#888",
    fontFamily: "system-ui, sans-serif",
    fontWeight: 600,
    marginBottom: "2px",
  },
  fieldValue: {
    margin: 0,
    fontSize: "0.95rem",
    fontFamily: "system-ui, sans-serif",
  },
  promoBox: {
    marginTop: "14px",
    padding: "12px 16px",
    background: "#f0faf4",
    border: "1px solid #9fd2b2",
    borderRadius: "6px",
    fontSize: "0.9rem",
    fontFamily: "system-ui, sans-serif",
  },
  notesBox: {
    marginTop: "10px",
    padding: "12px 16px",
    background: "#fafafa",
    border: "1px solid #e0e0e0",
    borderRadius: "6px",
    fontSize: "0.9rem",
    fontFamily: "system-ui, sans-serif",
    color: "#555",
  },
  adminBar: {
    display: "flex",
    gap: "12px",
    flexWrap: "wrap",
  },
  adminBtn: {
    padding: "8px 20px",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "0.9rem",
    fontWeight: 600,
    fontFamily: "system-ui, sans-serif",
    transition: "opacity 0.15s",
  },
  verifyBtn: { background: "#1a6b3a", color: "#fff" },
  rejectBtn: { background: "#c62828", color: "#fff" },
  reviewBtn: { background: "#e65100", color: "#fff" },
  tabBar: {
    display: "flex",
    gap: "0",
    borderBottom: "2px solid #e0e0e0",
    marginBottom: "0",
  },
  tab: {
    padding: "8px 24px",
    background: "none",
    border: "none",
    borderBottom: "3px solid transparent",
    cursor: "pointer",
    fontSize: "0.9rem",
    fontWeight: 600,
    fontFamily: "system-ui, sans-serif",
    color: "#888",
    marginBottom: "-2px",
  },
  tabActive: {
    color: "#1a6b3a",
    borderBottomColor: "#1a6b3a",
  },
  tabPanel: {
    padding: "16px 0",
  },
  innerTable: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "0.88rem",
    fontFamily: "system-ui, sans-serif",
  },
  th: {
    textAlign: "left",
    padding: "8px 12px",
    borderBottom: "2px solid #d0d0d0",
    fontWeight: 700,
    color: "#444",
    background: "#f5f5f5",
    fontSize: "0.78rem",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  td: {
    padding: "9px 12px",
    borderBottom: "1px solid #eee",
    verticalAlign: "top",
  },
  sourceCard: {
    padding: "12px 16px",
    border: "1px solid #e0e0e0",
    borderRadius: "6px",
    marginBottom: "10px",
    background: "#fafafa",
  },
  sourceTitle: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "4px",
  },
  sourceLink: {
    color: "#1a6b3a",
    textDecoration: "none",
    fontSize: "0.9rem",
    fontFamily: "system-ui, sans-serif",
    fontWeight: 600,
    wordBreak: "break-all",
  },
  sourceBadge: {
    padding: "1px 8px",
    background: "#e8f4fd",
    border: "1px solid #90caf9",
    borderRadius: "999px",
    fontSize: "0.75rem",
    fontFamily: "system-ui, sans-serif",
    whiteSpace: "nowrap",
  },
  sourceMeta: {
    fontSize: "0.8rem",
    color: "#777",
    fontFamily: "system-ui, sans-serif",
  },
  muted: { color: "#999", fontStyle: "italic", fontFamily: "system-ui, sans-serif" },
  errorText: { color: "#c62828", fontFamily: "system-ui, sans-serif" },
  successText: { color: "#1a6b3a", fontFamily: "system-ui, sans-serif" },
};
