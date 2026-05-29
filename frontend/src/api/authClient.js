const BASE = "/api/auth";

async function request(path, options = {}) {
  const token = localStorage.getItem("fil_token");
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export async function register(email, username, password, passwordConfirmation) {
  return request("/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      username,
      password,
      password_confirmation: passwordConfirmation,
    }),
  });
}

export async function login(loginValue, password) {
  return request("/login", {
    method: "POST",
    body: JSON.stringify({ login: loginValue, password }),
  });
}

export async function getMe() {
  return request("/me");
}

export async function updateEmail(currentPassword, newEmail) {
  return request("/me/email", {
    method: "PUT",
    body: JSON.stringify({ current_password: currentPassword, new_email: newEmail }),
  });
}

export async function updateUsername(newUsername) {
  return request("/me/username", {
    method: "PUT",
    body: JSON.stringify({ new_username: newUsername }),
  });
}

export async function updatePassword(currentPassword, newPassword, newPasswordConfirmation) {
  return request("/me/password", {
    method: "PUT",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
      new_password_confirmation: newPasswordConfirmation,
    }),
  });
}

export async function getProfile() {
  return request("/me/profile");
}

export async function updateProfile(profileData) {
  return request("/me/profile", {
    method: "PUT",
    body: JSON.stringify(profileData),
  });
}

export async function getLocations() {
  return request("/me/locations");
}

export async function addLocation(city, state) {
  return request("/me/locations", {
    method: "POST",
    body: JSON.stringify({ city, state }),
  });
}

export async function removeLocation(locationId) {
  return request(`/me/locations/${locationId}`, { method: "DELETE" });
}
