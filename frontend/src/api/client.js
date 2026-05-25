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
    if (Array.isArray(v)) {
      for (const item of v) params.append(k, item);
    } else if (v !== undefined && v !== null && v !== "") {
      params.set(k, v);
    }
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

/**
 * Fetch the admin review queue (candidate and needs_review events).
 * @param {Object} params - { limit, offset }
 * @returns {Promise<Array>}
 */
export function fetchReviewQueue({ limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit, offset });
  return request(`/api/admin/review-queue?${params}`);
}

/**
 * Fetch side-by-side claim conflicts between two events.
 * @param {string} eventId - The candidate event UUID
 * @param {string} otherId - The canonical event UUID
 * @returns {Promise<Object>}
 */
export function fetchConflicts(eventId, otherId) {
  return request(`/api/admin/events/${eventId}/conflicts?other_id=${otherId}`);
}

/**
 * Manually flag (or clear) an event as a possible duplicate.
 * @param {string} eventId - The event to flag
 * @param {string|null} duplicateOfId - Canonical event UUID, or null to clear
 * @returns {Promise<Object>}
 */
export function flagDuplicate(eventId, duplicateOfId) {
  return request(`/api/admin/events/${eventId}/flag-duplicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ duplicate_of_id: duplicateOfId }),
  });
}

/**
 * Merge a source event into a canonical target event.
 * @param {string} sourceId - Event to merge away
 * @param {string} targetId - Canonical event to keep
 * @param {Object} canonicalFields - Optional field overrides for the target
 * @returns {Promise<Object>}
 */
export function mergeEvents(sourceId, targetId, canonicalFields = {}) {
  return request(`/api/admin/events/${sourceId}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_id: targetId, canonical_fields: canonicalFields }),
  });
}

/**
 * Run a retroactive duplicate scan across existing events.
 * @returns {Promise<Object>}
 */
export function runRetroactiveDedup() {
  return request("/api/admin/dedup/retroactive-run", {
    method: "POST",
  });
}

