import { Link } from "react-router-dom";
import { DuplicateBadge, StatusBadge } from "./StatusBadge";
import { btnStyle, tdStyle, thStyle } from "./styles";

export default function ReviewQueueTable({ events, actionState, onAction, onMerge }) {
  return (
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
        {events.map((event) => {
          const busy = actionState[event.id] && actionState[event.id] !== "done";
          return (
            <tr key={event.id} style={{ borderBottom: "1px solid #e5e7eb" }}>
              <td style={tdStyle}>
                <Link
                  to={`/events/${event.id}`}
                  style={{ color: "#2563eb", textDecoration: "none", fontWeight: 500 }}
                >
                  {event.business_name || event.event_name || "Unnamed"}
                </Link>
                {event.possible_duplicate && <DuplicateBadge />}
              </td>
              <td style={tdStyle}>{event.category || "-"}</td>
              <td style={tdStyle}>{event.city || "-"}</td>
              <td style={tdStyle}>
                <StatusBadge status={event.status} />
              </td>
              <td style={tdStyle}>
                {event.created_at ? new Date(event.created_at).toLocaleDateString() : "-"}
              </td>
              <td style={{ ...tdStyle, whiteSpace: "nowrap" }}>
                <button
                  disabled={busy}
                  onClick={() => onAction(event.id, "verified")}
                  style={{ ...btnStyle, background: busy ? "#d1d5db" : "#16a34a", color: "#fff", marginRight: 6 }}
                >
                  {actionState[event.id] === "verifying" ? "..." : "Verify"}
                </button>
                <button
                  disabled={busy}
                  onClick={() => onAction(event.id, "rejected")}
                  style={{ ...btnStyle, background: busy ? "#d1d5db" : "#dc2626", color: "#fff", marginRight: 6 }}
                >
                  {actionState[event.id] === "rejecting" ? "..." : "Reject"}
                </button>
                {event.possible_duplicate && (
                  <button
                    disabled={busy}
                    onClick={() => onMerge(event)}
                    style={{ ...btnStyle, background: busy ? "#d1d5db" : "#9333ea", color: "#fff" }}
                  >
                    Merge
                  </button>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}