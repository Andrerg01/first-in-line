const STATUS_BADGE = {
  candidate: { bg: "#fffbeb", color: "#92400e", label: "Candidate" },
  needs_review: { bg: "#fef3c7", color: "#b45309", label: "Needs Review" },
  merged: { bg: "#ede9fe", color: "#6d28d9", label: "Merged" },
};

export function StatusBadge({ status }) {
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

export function DuplicateBadge() {
  return (
    <span
      style={{
        background: "#fce7f3",
        color: "#9d174d",
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 11,
        fontWeight: 600,
        marginLeft: 6,
      }}
    >
      Possible Dup
    </span>
  );
}