import { createContext, useContext, useEffect, useState } from "react";
import { getMe, login as apiLogin, register as apiRegister } from "../api/authClient";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem("fil_token");
    if (!token) { setLoading(false); return; }
    getMe()
      .then(setUser)
      .catch(() => localStorage.removeItem("fil_token"))
      .finally(() => setLoading(false));
  }, []);

  async function register(email, username, password, passwordConfirmation) {
    const data = await apiRegister(email, username, password, passwordConfirmation);
    localStorage.setItem("fil_token", data.access_token);
    setUser(data.user);
    return data.user;
  }

  async function login(loginValue, password) {
    const data = await apiLogin(loginValue, password);
    localStorage.setItem("fil_token", data.access_token);
    setUser(data.user);
    return data.user;
  }

  function logout() {
    localStorage.removeItem("fil_token");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
