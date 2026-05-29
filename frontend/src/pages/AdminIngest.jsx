import { useState } from "react";
import { Link } from "react-router-dom";
import { ingestUrl } from "../api/client";
import NavBar from "../components/NavBar";

const STATUS_COLORS = {
  candidate: "#6c757d",
  verified: "#198754",
  rejected: "#dc3545",
  needs_review: "#ffc107",
};

export default function AdminIngest() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const data = await ingestUrl(url.trim());
      setResult(data);
    } catch (err) {
      setError(err.message || "Ingestion failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.page}>
      <NavBar />
      <header style={styles.header}>
        <h1 style={styles.title}>Manual URL Ingestion</h1>
      </header>

      <section style={styles.formSection}>
        <p style={styles.description}>
          Paste a URL pointing to a grand opening announcement. The system will
          fetch the page, extract structured data via OpenAI, and create a
          candidate event for review.
        </p>
        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/grand-opening-announcement"
            required
            style={styles.input}
          />
          <button
            type="submit"
            disabled={loading || !url.trim()}
            style={{
              ...styles.submitButton,
              opacity: loading || !url.trim() ? 0.6 : 1,
              cursor: loading || !url.trim() ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Processing…" : "Ingest URL"}
          </button>
        </form>
      </section>

      {error && (
        <div style={styles.errorBox}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {result && <IngestResult result={result} />}
    </div>
  );
}

function IngestResult({ result }) {
  const statusColor = STATUS_COLORS[result.status] || "#6c757d";

  return (
    <section style={styles.resultSection}>
      <h2 style={styles.resultHeading}>Ingestion Result</h2>

      <div style={styles.badgeRow}>
        {result.duplicate && (
          <span style={{ ...styles.badge, background: "#6c757d" }}>Duplicate</span>
        )}
        {result.relevant ? (
          <span style={{ ...styles.badge, background: "#0d6efd" }}>Relevant</span>
        ) : (
          <span style={{ ...styles.badge, background: "#adb5bd" }}>Not Relevant</span>
        )}
        {result.status && (
          <span style={{ ...styles.badge, background: statusColor }}>
            {result.status}
          </span>
        )}
      </div>

      <p style={styles.message}>{result.message}</p>

      {result.event_id && (
        <p>
          <Link to={`/events/${result.event_id}`} style={styles.eventLink}>
            View candidate event →
          </Link>
        </p>
      )}

      {result.relevant && result.business_name && (
        <table style={styles.table}>
          <tbody>
            <TableRow label="Business Name" value={result.business_name} />
            <TableRow label="Event Type" value={result.event_type} />
            <TableRow label="Category" value={result.category} />
            <TableRow
              label="Event Date"
              value={
                result.event_date
                  ? new Date(result.event_date).toLocaleDateString()
                  : "—"
              }
            />
            <TableRow
              label="Location"
              value={
                [result.city, result.state].filter(Boolean).join(", ") || "—"
              }
            />
            <TableRow
              label="Confidence"
              value={
                result.confidence_score != null
                  ? `${Math.round(result.confidence_score * 100)}%`
                  : "—"
              }
            />
            <TableRow label="Claims Extracted" value={result.claims_count} />
            <TableRow label="Fetch Status" value={result.fetch_status} />
          </tbody>
        </table>
      )}

      <details style={styles.rawDetails}>
        <summary style={styles.rawSummary}>Raw API response</summary>
        <pre style={styles.rawPre}>{JSON.stringify(result, null, 2)}</pre>
      </details>
    </section>
  );
}

function TableRow({ label, value }) {
  return (
    <tr>
      <td style={styles.tdLabel}>{label}</td>
      <td style={styles.tdValue}>{value ?? "—"}</td>
    </tr>
  );
}

const styles = {
  page: {
    maxWidth: 760,
    margin: "0 auto",
    padding: "24px 16px",
    fontFamily: "system-ui, sans-serif",
    color: "#212529",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 24,
    gap: 16,
    flexWrap: "wrap",
  },
  title: { margin: 0, fontSize: 24, fontWeight: 700 },
  nav: {},
  navLink: { color: "#0d6efd", textDecoration: "none", fontSize: 14 },
  description: { color: "#495057", marginBottom: 16, lineHeight: 1.5 },
  formSection: {
    background: "#f8f9fa",
    border: "1px solid #dee2e6",
    borderRadius: 8,
    padding: 24,
    marginBottom: 24,
  },
  form: { display: "flex", gap: 10, flexWrap: "wrap" },
  input: {
    flex: 1,
    minWidth: 260,
    padding: "10px 14px",
    border: "1px solid #ced4da",
    borderRadius: 6,
    fontSize: 14,
  },
  submitButton: {
    padding: "10px 22px",
    background: "#0d6efd",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 600,
    transition: "opacity 0.15s",
  },
  errorBox: {
    background: "#f8d7da",
    border: "1px solid #f5c2c7",
    color: "#842029",
    borderRadius: 6,
    padding: "12px 16px",
    marginBottom: 24,
    fontSize: 14,
  },
  resultSection: {
    border: "1px solid #dee2e6",
    borderRadius: 8,
    padding: 24,
  },
  resultHeading: { margin: "0 0 16px", fontSize: 18, fontWeight: 600 },
  badgeRow: { display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 },
  badge: {
    color: "#fff",
    borderRadius: 4,
    padding: "3px 10px",
    fontSize: 12,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  message: { color: "#495057", marginBottom: 16, fontSize: 14 },
  eventLink: { color: "#0d6efd", fontWeight: 600, fontSize: 14 },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 14,
    marginTop: 12,
    marginBottom: 16,
  },
  tdLabel: {
    padding: "6px 12px 6px 0",
    fontWeight: 600,
    color: "#6c757d",
    width: 160,
    verticalAlign: "top",
  },
  tdValue: { padding: "6px 0", verticalAlign: "top" },
  rawDetails: { marginTop: 16 },
  rawSummary: {
    cursor: "pointer",
    fontSize: 13,
    color: "#6c757d",
    userSelect: "none",
  },
  rawPre: {
    background: "#f8f9fa",
    border: "1px solid #dee2e6",
    borderRadius: 4,
    padding: 12,
    fontSize: 12,
    overflow: "auto",
    marginTop: 8,
  },
};
