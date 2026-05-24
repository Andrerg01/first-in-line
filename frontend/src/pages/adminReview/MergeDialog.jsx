import { useState } from "react";
import { fetchConflicts, mergeEvents } from "../../api/client";
import { btnStyle } from "./styles";

export default function MergeDialog({ event, onClose, onMerged }) {
  const [targetId, setTargetId] = useState(event.duplicate_of_id || "");
  const [conflicts, setConflicts] = useState(null);
  const [loadingConflicts, setLoadingConflicts] = useState(false);
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState(null);

  async function loadConflicts() {
    if (!targetId.trim()) return;
    setLoadingConflicts(true);
    setError(null);
    try {
      const data = await fetchConflicts(event.id, targetId.trim());
      setConflicts(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingConflicts(false);
    }
  }

  async function handleMerge() {
    if (!targetId.trim()) return;
    setMerging(true);
    setError(null);
    try {
      await mergeEvents(event.id, targetId.trim());
      onMerged(event.id);
    } catch (err) {
      setError(err.message);
      setMerging(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 10,
          padding: 28,
          width: "min(560px, 95vw)",
          boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
          fontFamily: "sans-serif",
        }}
      >
        <h2 style={{ marginTop: 0, fontSize: 18 }}>
          Merge: <em>{event.business_name || "Unnamed"}</em>
        </h2>
        <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
          This event will be marked <strong>merged</strong> and its claims and source evidence
          will be moved onto the target canonical event.
        </p>

        <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 600 }}>
          Target (canonical) event UUID
        </label>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <input
            value={targetId}
            onChange={(e) => {
              setTargetId(e.target.value);
              setConflicts(null);
            }}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            style={{ flex: 1, padding: "7px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}
          />
          <button
            onClick={loadConflicts}
            disabled={!targetId.trim() || loadingConflicts}
            style={{ ...btnStyle, background: "#2563eb", color: "#fff", whiteSpace: "nowrap" }}
          >
            {loadingConflicts ? "..." : "Compare"}
          </button>
        </div>

        {error && <p style={{ color: "#dc2626", fontSize: 13 }}>{error}</p>}

        {conflicts && (
          <div style={{ marginBottom: 16 }}>
            <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
              {conflicts.conflicting_claim_types.length === 0
                ? "No conflicting claims found."
                : `Conflicting claim types: ${conflicts.conflicting_claim_types.join(", ")}`}
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {["event_a", "event_b"].map((side, index) => (
                <div
                  key={side}
                  style={{ background: "#f9fafb", borderRadius: 6, padding: 10, fontSize: 12 }}
                >
                  <strong style={{ display: "block", marginBottom: 6 }}>
                    {index === 0 ? "This event (source)" : "Target (canonical)"}
                  </strong>
                  {Object.entries(conflicts[side].claims).map(([type, values]) => (
                    <div
                      key={type}
                      style={{
                        marginBottom: 3,
                        color: conflicts.conflicting_claim_types.includes(type) ? "#b91c1c" : "#374151",
                      }}
                    >
                      <span style={{ fontWeight: 600 }}>{type}:</span>{" "}
                      {values.join(", ")}
                    </div>
                  ))}
                  {Object.keys(conflicts[side].claims).length === 0 && (
                    <span style={{ color: "#9ca3af" }}>No claims</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
          <button onClick={onClose} style={{ ...btnStyle, border: "1px solid #d1d5db" }}>
            Cancel
          </button>
          <button
            onClick={handleMerge}
            disabled={!targetId.trim() || merging}
            style={{ ...btnStyle, background: merging ? "#d1d5db" : "#9333ea", color: "#fff" }}
          >
            {merging ? "Merging..." : "Confirm Merge"}
          </button>
        </div>
      </div>
    </div>
  );
}