import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  addLocation,
  getLocations,
  getProfile,
  removeLocation,
  updateEmail,
  updatePassword,
  updateProfile,
  updateUsername,
} from "../api/authClient";
import { useAuth } from "../context/AuthContext";
import NavBar from "../components/NavBar";

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY",
  "LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND",
  "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
];

export default function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Redirect if not logged in
  useEffect(() => {
    if (!user) navigate("/");
  }, [user, navigate]);

  if (!user) return null;

  return (
    <div style={{ minHeight: "100vh", background: "#f7f8fa" }}>
      <NavBar />
      <div style={styles.page}>
        <h1 style={styles.pageTitle}>My Account</h1>
        <div style={styles.grid}>
          <ProfileSection user={user} />
          <CredentialsSection user={user} />
          <LocationsSection />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Profile section (name, phone)
// ---------------------------------------------------------------------------
function ProfileSection({ user }) {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({ first_name: "", middle_initial: "", last_name: "", phone_number: "" });
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    getProfile().then(p => {
      setProfile(p);
      setForm({
        first_name: p.first_name || "",
        middle_initial: p.middle_initial || "",
        last_name: p.last_name || "",
        phone_number: p.phone_number || "",
      });
    }).catch(() => {});
  }, []);

  async function handleSave(e) {
    e.preventDefault();
    setMsg(""); setErr("");
    try {
      const p = await updateProfile({
        first_name: form.first_name || null,
        middle_initial: form.middle_initial || null,
        last_name: form.last_name || null,
        phone_number: form.phone_number || null,
      });
      setProfile(p);
      setMsg("Profile saved.");
    } catch (ex) { setErr(ex.message); }
  }

  return (
    <Card title="Profile">
      <p style={styles.meta}>
        <strong>@{user.username}</strong> &nbsp;·&nbsp; {user.email}<br />
        <span style={styles.pill}>{user.tier}</span>
        <span style={{ ...styles.pill, background: "#e8f5e9", color: "#2e7d32" }}>{user.role}</span>
      </p>
      <form onSubmit={handleSave} style={styles.form}>
        <div style={styles.row}>
          <Inp label="First Name" value={form.first_name} onChange={v => setForm(f => ({ ...f, first_name: v }))} />
          <Inp label="M.I." value={form.middle_initial} onChange={v => setForm(f => ({ ...f, middle_initial: v }))} style={{ maxWidth: 64 }} />
          <Inp label="Last Name" value={form.last_name} onChange={v => setForm(f => ({ ...f, last_name: v }))} />
        </div>
        <Inp label="Phone Number" value={form.phone_number} onChange={v => setForm(f => ({ ...f, phone_number: v }))} />
        {msg && <p style={styles.ok}>{msg}</p>}
        {err && <p style={styles.err}>{err}</p>}
        <button type="submit" style={styles.btn}>Save Profile</button>
      </form>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Credentials section (email, username, password)
// ---------------------------------------------------------------------------
function CredentialsSection({ user }) {
  const [emailForm, setEmailForm] = useState({ currentPassword: "", newEmail: "" });
  const [usernameForm, setUsernameForm] = useState({ newUsername: "" });
  const [pwForm, setPwForm] = useState({ currentPassword: "", newPassword: "", newPasswordConfirmation: "" });
  const [msgs, setMsgs] = useState({});
  const [errs, setErrs] = useState({});

  function feedback(key, isOk, text) {
    if (isOk) setMsgs(m => ({ ...m, [key]: text }));
    else setErrs(e => ({ ...e, [key]: text }));
  }

  async function handleEmail(e) {
    e.preventDefault();
    setMsgs({}); setErrs({});
    try {
      await updateEmail(emailForm.currentPassword, emailForm.newEmail);
      feedback("email", true, "Email updated.");
      setEmailForm({ currentPassword: "", newEmail: "" });
    } catch (ex) { feedback("email", false, ex.message); }
  }

  async function handleUsername(e) {
    e.preventDefault();
    setMsgs({}); setErrs({});
    try {
      await updateUsername(usernameForm.newUsername);
      feedback("username", true, "Username updated.");
      setUsernameForm({ newUsername: "" });
    } catch (ex) { feedback("username", false, ex.message); }
  }

  async function handlePassword(e) {
    e.preventDefault();
    setMsgs({}); setErrs({});
    try {
      await updatePassword(pwForm.currentPassword, pwForm.newPassword, pwForm.newPasswordConfirmation);
      feedback("password", true, "Password updated.");
      setPwForm({ currentPassword: "", newPassword: "", newPasswordConfirmation: "" });
    } catch (ex) { feedback("password", false, ex.message); }
  }

  return (
    <Card title="Account Credentials">
      <section style={styles.credSection}>
        <h4 style={styles.subhead}>Change Email</h4>
        <form onSubmit={handleEmail} style={styles.form}>
          <Inp label="Current Password" type="password" value={emailForm.currentPassword} onChange={v => setEmailForm(f => ({ ...f, currentPassword: v }))} required />
          <Inp label="New Email" type="email" value={emailForm.newEmail} onChange={v => setEmailForm(f => ({ ...f, newEmail: v }))} required />
          {msgs.email && <p style={styles.ok}>{msgs.email}</p>}
          {errs.email && <p style={styles.err}>{errs.email}</p>}
          <button type="submit" style={styles.btn}>Update Email</button>
        </form>
      </section>

      <section style={styles.credSection}>
        <h4 style={styles.subhead}>Change Username</h4>
        <form onSubmit={handleUsername} style={styles.form}>
          <Inp label="New Username" value={usernameForm.newUsername} onChange={v => setUsernameForm({ newUsername: v })} required />
          {msgs.username && <p style={styles.ok}>{msgs.username}</p>}
          {errs.username && <p style={styles.err}>{errs.username}</p>}
          <button type="submit" style={styles.btn}>Update Username</button>
        </form>
      </section>

      <section style={styles.credSection}>
        <h4 style={styles.subhead}>Change Password</h4>
        <form onSubmit={handlePassword} style={styles.form}>
          <Inp label="Current Password" type="password" value={pwForm.currentPassword} onChange={v => setPwForm(f => ({ ...f, currentPassword: v }))} required />
          <Inp label="New Password" type="password" value={pwForm.newPassword} onChange={v => setPwForm(f => ({ ...f, newPassword: v }))} required />
          <Inp label="Confirm New Password" type="password" value={pwForm.newPasswordConfirmation} onChange={v => setPwForm(f => ({ ...f, newPasswordConfirmation: v }))} required />
          {msgs.password && <p style={styles.ok}>{msgs.password}</p>}
          {errs.password && <p style={styles.err}>{errs.password}</p>}
          <button type="submit" style={styles.btn}>Update Password</button>
        </form>
      </section>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Preferred locations section
// ---------------------------------------------------------------------------
function LocationsSection() {
  const [locations, setLocations] = useState([]);
  const [city, setCity] = useState("");
  const [state, setState] = useState("SC");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => { getLocations().then(setLocations).catch(() => {}); }, []);

  async function handleAdd(e) {
    e.preventDefault();
    setErr(""); setMsg("");
    try {
      const loc = await addLocation(city.trim(), state);
      setLocations(l => {
        const exists = l.some(x => x.id === loc.id);
        return exists ? l : [...l, loc];
      });
      setMsg(`Added ${loc.city}, ${loc.state}.`);
      setCity("");
    } catch (ex) { setErr(ex.message); }
  }

  async function handleRemove(id) {
    setErr(""); setMsg("");
    try {
      await removeLocation(id);
      setLocations(l => l.filter(x => x.id !== id));
    } catch (ex) { setErr(ex.message); }
  }

  return (
    <Card title="Preferred Locations">
      <p style={{ fontSize: "0.85rem", color: "#666", marginTop: 0 }}>
        Cities you add here are included in the search pool.
      </p>

      {locations.length > 0 && (
        <ul style={styles.locList}>
          {locations.map(loc => (
            <li key={loc.id} style={styles.locItem}>
              <span>{loc.city}, {loc.state}</span>
              <button style={styles.removeBtn} onClick={() => handleRemove(loc.id)} aria-label="Remove">✕</button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleAdd} style={{ ...styles.form, marginTop: 12 }}>
        <div style={styles.row}>
          <Inp label="City" value={city} onChange={setCity} required style={{ flex: 2 }} />
          <label style={{ ...styles.field, flex: 1 }}>
            <span style={styles.label}>State</span>
            <select value={state} onChange={e => setState(e.target.value)} style={styles.input}>
              {US_STATES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>
        {msg && <p style={styles.ok}>{msg}</p>}
        {err && <p style={styles.err}>{err}</p>}
        <button type="submit" style={styles.btn}>Add Location</button>
      </form>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function Card({ title, children }) {
  return (
    <div style={styles.card}>
      <h3 style={styles.cardTitle}>{title}</h3>
      {children}
    </div>
  );
}

function Inp({ label, type = "text", value, onChange, hint, required, style: extra }) {
  return (
    <label style={{ ...styles.field, ...extra }}>
      <span style={styles.label}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={styles.input}
        required={required}
      />
      {hint && <span style={styles.hint}>{hint}</span>}
    </label>
  );
}

const styles = {
  page: { maxWidth: 960, margin: "0 auto", padding: "32px 20px" },
  pageTitle: { fontSize: "1.6rem", fontWeight: 700, marginBottom: 24 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 20 },
  card: { background: "#fff", borderRadius: 12, boxShadow: "0 2px 10px rgba(0,0,0,0.07)", padding: 24 },
  cardTitle: { margin: "0 0 16px", fontSize: "1.05rem", fontWeight: 700, color: "#1a1a2e" },
  meta: { fontSize: "0.88rem", color: "#555", marginTop: 0 },
  pill: {
    display: "inline-block", background: "#e8f4fd", color: "#1976d2",
    borderRadius: 4, padding: "1px 8px", fontSize: "0.75rem", fontWeight: 600, marginRight: 4,
  },
  form: { display: "flex", flexDirection: "column", gap: 10 },
  row: { display: "flex", gap: 10 },
  field: { display: "flex", flexDirection: "column", gap: 3, flex: 1 },
  label: { fontSize: "0.82rem", fontWeight: 600, color: "#555" },
  input: { padding: "8px 10px", borderRadius: 6, border: "1px solid #ccc", fontSize: "0.92rem" },
  hint: { fontSize: "0.73rem", color: "#999" },
  btn: {
    alignSelf: "flex-start", background: "#4f8ef7", color: "#fff",
    border: "none", borderRadius: 6, padding: "8px 18px", fontWeight: 600,
    fontSize: "0.88rem", cursor: "pointer", marginTop: 4,
  },
  ok: { margin: 0, fontSize: "0.83rem", color: "#2e7d32" },
  err: { margin: 0, fontSize: "0.83rem", color: "#c62828" },
  credSection: { borderTop: "1px solid #f0f0f0", paddingTop: 14, marginTop: 10 },
  subhead: { margin: "0 0 10px", fontSize: "0.9rem", color: "#444" },
  locList: { listStyle: "none", margin: "0 0 4px", padding: 0, display: "flex", flexDirection: "column", gap: 6 },
  locItem: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    background: "#f5f5f5", borderRadius: 6, padding: "6px 10px", fontSize: "0.88rem",
  },
  removeBtn: {
    background: "none", border: "none", cursor: "pointer", color: "#999",
    fontSize: "0.8rem", lineHeight: 1, padding: "0 2px",
  },
};
