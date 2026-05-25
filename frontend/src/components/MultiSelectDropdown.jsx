/**
 * MultiSelectDropdown — a checkbox-based multi-select filter widget.
 *
 * Shows a button with the current selection summary (or "All" when nothing
 * is selected). Clicking the button opens a dropdown with one checkbox per
 * option. Clicking outside closes the dropdown.
 */
import { useState, useEffect } from "react";

export default function MultiSelectDropdown({ label, options, selected, onChange }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function handleOutside() { setOpen(false); }
    document.addEventListener("click", handleOutside);
    return () => document.removeEventListener("click", handleOutside);
  }, [open]);

  function toggle(value) {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  }

  const btnLabel =
    selected.length === 0
      ? `${label}: All`
      : selected.length === 1
      ? `${label}: ${selected[0]}`
      : `${label}: ${selected.length} selected`;

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        style={{
          padding: "5px 10px",
          border: "1px solid #d1d5db",
          borderRadius: 5,
          background: selected.length > 0 ? "#dbeafe" : "#f9fafb",
          cursor: "pointer",
          fontSize: "0.9rem",
          fontWeight: selected.length > 0 ? 600 : 400,
          whiteSpace: "nowrap",
          color: "#374151",
        }}
      >
        {btnLabel} ▾
      </button>
      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            zIndex: 10000,
            background: "#fff",
            border: "1px solid #d1d5db",
            borderRadius: 8,
            boxShadow: "0 4px 16px rgba(0,0,0,0.15)",
            minWidth: 180,
            padding: "6px 0",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {options.map((opt) => (
            <label
              key={opt}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "5px 14px",
                cursor: "pointer",
                fontSize: "0.88rem",
                color: "#374151",
                userSelect: "none",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#f0f9ff"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <input
                type="checkbox"
                checked={selected.includes(opt)}
                onChange={() => toggle(opt)}
                style={{ cursor: "pointer", accentColor: "#2563eb" }}
              />
              {opt}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
