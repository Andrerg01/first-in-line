import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function AuthModal({ onClose }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [fields, setFields] = useState({
    login: "", email: "", username: "", password: "", passwordConfirmation: "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const backdropRef = useRef(null);

  // Close on Escape
  useEffect(() => {
    function handler(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  function set(key, val) {
    setFields(f => ({ ...f, [key]: val }));
    setError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      if (mode === "login") {
        await login(fields.login, fields.password);
      } else {
        await register(fields.email, fields.username, fields.password, fields.passwordConfirmation);
      }
      onClose();
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      ref={backdropRef}
      style={styles.backdrop}
      onClick={e => { if (e.target === backdropRef.current) onClose(); }}
    >
      <div style={styles.modal} role="dialog" aria-modal="true">
        {/* Header */}
        <div style={styles.header}>
          <h2 style={styles.title}>
            {mode === "login" ? "Sign In" : "Create Account"}
          </h2>
          <button style={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Mode toggle */}
        <div style={styles.toggle}>
          <button
            style={{ ...styles.toggleBtn, ...(mode === "login" ? styles.activeToggle : {}) }}
            onClick={() => { setMode("login"); setError(""); }}
          >
            Sign In
          </button>
          <button
            style={{ ...styles.toggleBtn, ...(mode === "register" ? styles.activeToggle : {}) }}
            onClick={() => { setMode("register"); setError(""); }}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          {mode === "login" ? (
            <Field
              label="Email or Username"
              value={fields.login}
              onChange={v => set("login", v)}
              autoFocus
            />
          ) : (
            <>
              <Field
                label="Email"
                type="email"
                value={fields.email}
                onChange={v => set("email", v)}
                autoFocus
              />
              <Field
                label="Username"
                value={fields.username}
                onChange={v => set("username", v)}
                hint="3–50 chars, letters/digits/underscore only"
              />
            </>
          )}

          <Field
            label="Password"
            type="password"
            value={fields.password}
            onChange={v => set("password", v)}
            hint={mode === "register" ? "Minimum 8 characters" : undefined}
          />

          {mode === "register" && (
            <Field
              label="Confirm Password"
              type="password"
              value={fields.passwordConfirmation}
              onChange={v => set("passwordConfirmation", v)}
            />
          )}

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" style={styles.submitBtn} disabled={submitting}>
            {submitting ? "…" : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Field({ label, type = "text", value, onChange, hint, autoFocus }) {
  return (
    <label style={styles.field}>
      <span style={styles.label}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={styles.input}
        autoFocus={autoFocus}
        required
      />
      {hint && <span style={styles.hint}>{hint}</span>}
    </label>
  );
}

const styles = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "#fff",
    borderRadius: 12,
    boxShadow: "0 8px 40px rgba(0,0,0,0.22)",
    width: 380,
    maxWidth: "92vw",
    padding: "28px 32px",
  },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  title: { margin: 0, fontSize: "1.25rem", fontWeight: 700 },
  closeBtn: {
    background: "none", border: "none", fontSize: "1.1rem",
    cursor: "pointer", color: "#666", lineHeight: 1,
  },
  toggle: {
    display: "flex",
    borderBottom: "2px solid #e0e0e0",
    marginBottom: 20,
  },
  toggleBtn: {
    flex: 1,
    background: "none",
    border: "none",
    padding: "8px 0",
    cursor: "pointer",
    fontSize: "0.95rem",
    color: "#666",
    fontWeight: 500,
    transition: "color 0.15s",
  },
  activeToggle: {
    color: "#4f8ef7",
    borderBottom: "2px solid #4f8ef7",
    marginBottom: -2,
    fontWeight: 700,
  },
  form: { display: "flex", flexDirection: "column", gap: 14 },
  field: { display: "flex", flexDirection: "column", gap: 4 },
  label: { fontSize: "0.85rem", fontWeight: 600, color: "#444" },
  input: {
    padding: "9px 12px",
    borderRadius: 7,
    border: "1px solid #ccc",
    fontSize: "0.95rem",
    outline: "none",
    transition: "border 0.15s",
  },
  hint: { fontSize: "0.75rem", color: "#888" },
  error: {
    margin: 0,
    padding: "8px 12px",
    background: "#fdecea",
    border: "1px solid #ef9a9a",
    borderRadius: 6,
    color: "#c62828",
    fontSize: "0.88rem",
  },
  submitBtn: {
    marginTop: 4,
    background: "#4f8ef7",
    color: "#fff",
    border: "none",
    borderRadius: 7,
    padding: "11px 0",
    fontWeight: 700,
    fontSize: "1rem",
    cursor: "pointer",
    transition: "background 0.15s",
  },
};
