/**
 * Map API helpers — thin wrappers around the /api/events/map endpoint.
 */
import { fetchEvents } from "./client";

/**
 * Fetch events suitable for map pin rendering (geocoded only).
 * @param {Object} filters - { status, category, startDate, endDate, lat, lon, radiusMiles, limit }
 * @returns {Promise<Array>}
 */
export function fetchMapEvents(filters = {}) {
  const params = new URLSearchParams();
  for (const s of (filters.status || [])) params.append("status", s);
  for (const c of (filters.category || [])) params.append("category", c);
  if (filters.startDate) params.set("start_date", filters.startDate);
  if (filters.endDate) params.set("end_date", filters.endDate);
  if (filters.lat != null) params.set("lat", filters.lat);
  if (filters.lon != null) params.set("lon", filters.lon);
  if (filters.radiusMiles != null) params.set("radius_miles", filters.radiusMiles);
  if (filters.limit != null) params.set("limit", filters.limit);

  const query = params.toString();
  return fetch(`/api/events/map${query ? `?${query}` : ""}`)
    .then((res) => {
      if (!res.ok) throw new Error(`API ${res.status}`);
      return res.json();
    });
}

/**
 * Fetch all events regardless of geocoding status (for calendar).
 * @param {Object} filters - { status, category, startDate, endDate }
 * @returns {Promise<Array>}
 */
export function fetchCalendarEvents(filters = {}) {
  const params = {};
  if (filters.status?.length) params.status = filters.status;
  if (filters.category?.length) params.category = filters.category;
  if (filters.startDate) params.start_date = filters.startDate;
  if (filters.endDate) params.end_date = filters.endDate;
  params.limit = filters.limit ?? 200;
  return fetchEvents(params);
}
