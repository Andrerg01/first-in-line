import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchReviewQueue, patchEventStatus } from "../api/client";

const STATUS_BADGE = {
  candidate: { bg: "#fffbeb", color: "#92400e", label: "Candidate" },
  needs_review: { bg: "#fef3c7", color: "#b45309", label: "Needs Review" },
};

function StatusBadge({ status }) {
  const cfg = STATUS_BADGE[status] || { bg: "#f3f4f6", color: "#374151", label: status };
  return (
    <span
      style={{
        background: cfg.bg,
        color: cfg.color,
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {cfg.label}
    </span>
  );
}

export default function AdminReview() {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionState, setActionState] = useState({}); // { [id]: 'verifying' | 'rejecting' | 'done' }

  useEffect(() => {
    setLoading(true);
    fetchReviewQueue({ limit: 100 })
      .then((data) => {
        setEvents(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  async function handleAction(id, newStatus) {
    setActionState((s) => ({ ...s, [id]: newStatus === "verified" ? "verifying" : "rejecting" }));
    try {
      await patchEventStatus(id, newStatus);
      setEvents((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      alert(`Failed to update event: ${err.message}`);
    } finally {
      setActionState((s) => ({ ...s, [id]: "done" }));
    }
  }

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <button
          onClick={() => navigate("/")}
          style={{ background: "none", border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 14px", cursor: "pointer" }}
        >
          ← Events
        </button>
        <h1 style={{ margin: 0, fontSize: 22 }}>Admin Review Queue</h1>
        {!loading && (
          <span style={{ fontSize: 14, color: "#6b7280" }}>
            {events.length} event{events.length !== 1 ? "s" : ""} awaiting review
          </span>
        )}
      </div>

      {loading && <p style={{ color: "#6b7280" }}>Loading…</p>}
      {error && <p style={{ color: "#dc2626" }}>Error: {error}</p>}

      {!loading && !error && events.length === 0 && (
        <div style={{ textAlign: "center", padding: "48px 0", color: "#6b7280" }}>
          <p style={{ fontSize: 18 }}>Queue is empty — nothing to review.</p>
          <Link to="/admin/ingest" style={{ color: "#2563eb" }}>
            + Ingest a URL
          </Link>
        </div>
      )}

      {!loading && events.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "#f9fafb", textAlign: "left" }}>
              <th style={thStyle}>Business</th>
              <th style={thStyle}>Category</th>
              <th style={thStyle}>City</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Created</th>
              <th style={thStyle}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {events.map((ev) => {
              const busy = actionState[ev.id] && actionState[ev.id] !== "done";
              return (
                <tr key={ev.id} style={{ borderBottom: "1px solid #e5e7eb" }}>
                  <td style={tdStyle}>
                    <Link
                      to={`/events/${ev.id}`}
                      style={{ color: "#2563eb", textDecoration: "none", fontWeight: 500 }}
                    >
                      {ev.business_name || ev.event_name || "Unnamed"}
                    </Link>
                  </td>
                  <td style={tdStyle}>{ev.category || "—"}</td>
                  <td style={tdStyle}>{ev.city || "—"}</td>
                  <td style={tdStyle}>
                    <StatusBadge status={ev.status} />
                  </td>
                  <td style={tdStyle}>
                    {ev.created_at ? new Date(ev.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td style={{ ...tdStyle, whiteSpace: "nowrap" }}>
                    <button
                      disabled={busy}
                      onClick={() => handleAction(ev.id, "verified")}
                      style={{
                        ...btnStyle,
                        background: busy ? "#d1d5db" : "#16a34a",
                        color: "#fff",
                        marginRight: 6,
                      }}
                    >
                      {actionState[ev.id] === "verifying" ? "…" : "Verify"}
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => handleAction(ev.id, "rejected")}
                      style={{
                        ...btnStyle,
                        background: busy ? "#d1d5db" : "#dc2626",
                        color: "#fff",
                      }}
                    >
                      {actionState[ev.id] === "rejecting" ? "…" : "Reject"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

const thStyle = {
  padding: "10px 12px",
  fontWeight: 600,
  color: "#374151",
  borderBottom: "2px solid #e5e7eb",
};

const tdStyle = {
  padding: "10px 12px",
  color: "#374151",
  verticalAlign: "middle",
};

const btnStyle = {
  border: "none",
  borderRadius: 5,
  padding: "5px 12px",
  fontSize: 13,
  cursor: "pointer",
  fontWeight: 500,
};
