import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchReviewQueue, patchEventStatus, runRetroactiveDedup } from "../api/client";
import MergeDialog from "./adminReview/MergeDialog";
import ReviewQueueTable from "./adminReview/ReviewQueueTable";
import { btnStyle, pageStyle } from "./adminReview/styles";

export default function AdminReview() {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retroMessage, setRetroMessage] = useState(null);
  const [runningRetroScan, setRunningRetroScan] = useState(false);
  const [actionState, setActionState] = useState({});
  const [mergeTarget, setMergeTarget] = useState(null);

  async function loadQueue() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReviewQueue({ limit: 100 });
      setEvents(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadQueue();
  }, []);

  async function handleAction(id, newStatus) {
    setActionState((state) => ({ ...state, [id]: newStatus === "verified" ? "verifying" : "rejecting" }));
    try {
      await patchEventStatus(id, newStatus);
      setEvents((current) => current.filter((event) => event.id !== id));
    } catch (err) {
      alert(`Failed to update event: ${err.message}`);
    } finally {
      setActionState((state) => ({ ...state, [id]: "done" }));
    }
  }

  async function handleRetroactiveScan() {
    setRunningRetroScan(true);
    setRetroMessage(null);
    setError(null);
    try {
      const result = await runRetroactiveDedup();
      setRetroMessage(`${result.message} Scanned ${result.scanned}, flagged ${result.flagged}, cleared ${result.cleared}.`);
      await loadQueue();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningRetroScan(false);
    }
  }

  function handleMerged(sourceId) {
    setMergeTarget(null);
    setEvents((current) => current.filter((event) => event.id !== sourceId));
  }

  return (
    <div style={pageStyle}>
      {mergeTarget && (
        <MergeDialog event={mergeTarget} onClose={() => setMergeTarget(null)} onMerged={handleMerged} />
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
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
        <div style={{ marginLeft: "auto" }}>
          <button
            onClick={handleRetroactiveScan}
            disabled={runningRetroScan}
            style={{ ...btnStyle, background: runningRetroScan ? "#d1d5db" : "#0f766e", color: "#fff" }}
          >
            {runningRetroScan ? "Running Scan..." : "Run Retroactive Dedup"}
          </button>
        </div>
      </div>

      {retroMessage && <p style={{ color: "#065f46", marginBottom: 12 }}>{retroMessage}</p>}
      {loading && <p style={{ color: "#6b7280" }}>Loading...</p>}
      {error && <p style={{ color: "#dc2626" }}>Error: {error}</p>}

      {!loading && !error && events.length === 0 && (
        <div style={{ textAlign: "center", padding: "48px 0", color: "#6b7280" }}>
          <p style={{ fontSize: 18 }}>Queue is empty - nothing to review.</p>
          <Link to="/admin/ingest" style={{ color: "#2563eb" }}>
            + Ingest a URL
          </Link>
        </div>
      )}

      {!loading && events.length > 0 && (
        <ReviewQueueTable
          events={events}
          actionState={actionState}
          onAction={handleAction}
          onMerge={setMergeTarget}
        />
      )}
    </div>
  );
}