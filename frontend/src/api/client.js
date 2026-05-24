/**
 * API client — thin fetch wrappers for all backend endpoints.
 * All paths use relative /api/* so the dev-server proxy and nginx
 * proxy forward them to the backend without hardcoded URLs.
 */

async function request(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

/**
 * Fetch a paginated, filtered list of events.
 * @param {Object} filters - { status, category, city, state, limit, offset }
 * @returns {Promise<Array>}
 */
export function fetchEvents(filters = {}) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, v);
  }
  return request(`/api/events?${params}`);
}

/**
 * Fetch a single event by ID.
 * @param {string} id - Event UUID
 * @returns {Promise<Object>}
 */
export function fetchEvent(id) {
  return request(`/api/events/${id}`);
}

/**
 * Fetch source documents for an event.
 * @param {string} id - Event UUID
 * @returns {Promise<Array>}
 */
export function fetchEventSources(id) {
  return request(`/api/events/${id}/sources`);
}

/**
 * Fetch extracted claims for an event.
 * @param {string} id - Event UUID
 * @returns {Promise<Array>}
 */
export function fetchEventClaims(id) {
  return request(`/api/events/${id}/claims`);
}

/**
 * Update the status of an event.
 * @param {string} id - Event UUID
 * @param {string} status - One of: candidate, verified, rejected, needs_review, merged, expired
 * @returns {Promise<Object>} Updated event
 */
export function patchEventStatus(id, status) {
  return request(`/api/events/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

/**
 * Submit a URL for manual ingestion and candidate event extraction.
 * @param {string} url - The URL to ingest
 * @returns {Promise<Object>} Ingest result
 */
export function ingestUrl(url) {
  return request("/api/ingest/manual-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}
