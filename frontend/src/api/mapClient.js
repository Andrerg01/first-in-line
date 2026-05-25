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
  const params = {};
  if (filters.status) params.status = filters.status;
  if (filters.category) params.category = filters.category;
  if (filters.startDate) params.start_date = filters.startDate;
  if (filters.endDate) params.end_date = filters.endDate;
  if (filters.lat != null) params.lat = filters.lat;
  if (filters.lon != null) params.lon = filters.lon;
  if (filters.radiusMiles != null) params.radius_miles = filters.radiusMiles;
  if (filters.limit != null) params.limit = filters.limit;

  const query = new URLSearchParams(params).toString();
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
  if (filters.status) params.status = filters.status;
  if (filters.category) params.category = filters.category;
  if (filters.startDate) params.start_date = filters.startDate;
  if (filters.endDate) params.end_date = filters.endDate;
  params.limit = filters.limit ?? 200;
  return fetchEvents(params);
}
