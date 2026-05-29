import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import AuthModal from "./AuthModal";

const NAV_LINKS = [
  { to: "/", label: "List" },
  { to: "/map", label: "Map" },
  { to: "/calendar", label: "Calendar" },
];

const ROLE_BADGE = {
  admin: { bg: "#fdecea", color: "#c62828", label: "Admin" },
  developer: { bg: "#e8f5e9", color: "#2e7d32", label: "Dev" },
};

export default function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  function handleLogout() {
    setMenuOpen(false);
    logout();
    navigate("/");
  }

  const badge = user ? ROLE_BADGE[user.role] : null;

  return (
    <>
      <nav style={styles.nav}>
        <Link to="/" style={styles.brand}>First In Line</Link>

        <div style={styles.links}>
          {NAV_LINKS.map(({ to, label }) => (
            <Link key={to} to={to} style={styles.link}>{label}</Link>
          ))}
        </div>

        <div style={styles.authArea}>
          {user ? (
            <div style={{ position: "relative" }}>
              <button
                style={styles.userBtn}
                onClick={() => setMenuOpen(o => !o)}
              >
                {badge && (
                  <span style={{ ...styles.roleBadge, background: badge.bg, color: badge.color }}>
                    {badge.label}
                  </span>
                )}
                @{user.username}
                <span style={{ marginLeft: 6, opacity: 0.6 }}>▾</span>
              </button>

              {menuOpen && (
                <div style={styles.dropdown}>
                  <button
                    style={styles.dropItem}
                    onClick={() => { setMenuOpen(false); navigate("/profile"); }}
                  >
                    My Profile
                  </button>
                  <hr style={{ margin: "4px 0", border: "none", borderTop: "1px solid #eee" }} />
                  <button style={{ ...styles.dropItem, color: "#c62828" }} onClick={handleLogout}>
                    Log out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button style={styles.loginBtn} onClick={() => setShowModal(true)}>
              Sign In / Register
            </button>
          )}
        </div>
      </nav>

      {showModal && <AuthModal onClose={() => setShowModal(false)} />}
    </>
  );
}

const styles = {
  nav: {
    display: "flex",
    alignItems: "center",
    gap: 24,
    padding: "0 24px",
    height: 52,
    background: "#1a1a2e",
    color: "#fff",
    boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
    position: "sticky",
    top: 0,
    zIndex: 100,
  },
  brand: {
    fontWeight: 700,
    fontSize: "1.1rem",
    color: "#fff",
    textDecoration: "none",
    letterSpacing: "0.02em",
    marginRight: 8,
  },
  links: { display: "flex", gap: 4, flex: 1 },
  link: {
    color: "rgba(255,255,255,0.78)",
    textDecoration: "none",
    padding: "6px 12px",
    borderRadius: 6,
    fontSize: "0.92rem",
    transition: "background 0.15s",
  },
  authArea: { marginLeft: "auto" },
  loginBtn: {
    background: "#4f8ef7",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "7px 16px",
    fontWeight: 600,
    fontSize: "0.88rem",
    cursor: "pointer",
  },
  userBtn: {
    background: "rgba(255,255,255,0.08)",
    color: "#fff",
    border: "1px solid rgba(255,255,255,0.18)",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: "0.9rem",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  roleBadge: {
    fontSize: "0.7rem",
    fontWeight: 700,
    borderRadius: 4,
    padding: "1px 6px",
  },
  dropdown: {
    position: "absolute",
    right: 0,
    top: "calc(100% + 6px)",
    background: "#fff",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
    minWidth: 160,
    zIndex: 200,
    overflow: "hidden",
  },
  dropItem: {
    display: "block",
    width: "100%",
    textAlign: "left",
    padding: "10px 16px",
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: "0.9rem",
    color: "#333",
  },
};
