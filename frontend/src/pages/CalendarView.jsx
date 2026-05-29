/**
 * CalendarView page — shows events grouped by month and day.
 *
 * Renders a month grid for the selected month; each day cell lists
 * event names. Clicking an event name navigates to its detail page.
 * Days with no events are empty. Events without a date appear in a
 * separate "No date set" section below the grid.
 */

import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { fetchCalendarEvents } from "../api/mapClient";
import MultiSelectDropdown from "../components/MultiSelectDropdown";

const CATEGORY_OPTIONS = ["restaurant", "cafe", "food_truck", "brewery", "retail", "other"];
const STATUS_OPTIONS = ["candidate", "verified", "needs_review", "rejected"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const DAY_HEADERS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const STATUS_COLORS = {
  candidate: "#dbeafe",
  verified: "#dcfce7",
  rejected: "#fee2e2",
  needs_review: "#fef9c3",
  expired: "#f3f4f6",
};

function buildMonthGrid(year, month) {
  // Returns an array of 6 weeks × 7 days; null = out-of-month padding.
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

function makeIsoDate(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export default function CalendarView() {
  const navigate = useNavigate();
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ status: [], category: [] });
  const [pending, setPending] = useState({ status: [], category: [] });
  const [openUncertainDay, setOpenUncertainDay] = useState(null);

  // Build date range covering the displayed month.
  const startDate = makeIsoDate(viewYear, viewMonth, 1);
  const lastDay = new Date(viewYear, viewMonth + 1, 0).getDate();
  const endDate = makeIsoDate(viewYear, viewMonth, lastDay);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchCalendarEvents({ ...filters, startDate, endDate, limit: 200 })
      .then(setEvents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters, startDate, endDate]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!openUncertainDay) return;
    function handleOutside() { setOpenUncertainDay(null); }
    document.addEventListener("click", handleOutside);
    return () => document.removeEventListener("click", handleOutside);
  }, [openUncertainDay]);

  function applyFilters(e) {
    e.preventDefault();
    setFilters({ ...pending });
  }

  function clearFilters() {
    const empty = { status: [], category: [] };
    setPending(empty);
    setFilters(empty);
  }

  function prevMonth() {
    if (viewMonth === 0) { setViewYear((y) => y - 1); setViewMonth(11); }
    else setViewMonth((m) => m - 1);
  }

  function nextMonth() {
    if (viewMonth === 11) { setViewYear((y) => y + 1); setViewMonth(0); }
    else setViewMonth((m) => m + 1);
  }

  // Exact events indexed by ISO date; uncertain (range) events grouped separately.
  const byDate = {};
  const uncertainByDate = {};
  const noDate = [];

  for (const event of events) {
    const isUncertain =
      event.date_confidence &&
      event.date_confidence !== "exact" &&
      event.date_range_start &&
      event.date_range_end;

    if (isUncertain) {
      const rangeStart = new Date(event.date_range_start);
      const rangeEnd = new Date(event.date_range_end);
      for (let d = 1; d <= lastDay; d++) {
        const iso = makeIsoDate(viewYear, viewMonth, d);
        const cellDate = new Date(iso);
        if (cellDate >= rangeStart && cellDate <= rangeEnd) {
          if (!uncertainByDate[iso]) uncertainByDate[iso] = [];
          uncertainByDate[iso].push(event);
        }
      }
    } else if (event.event_date) {
      const day = event.event_date.slice(0, 10);
      if (!byDate[day]) byDate[day] = [];
      byDate[day].push(event);
    } else {
      noDate.push(event);
    }
  }

  const weeks = buildMonthGrid(viewYear, viewMonth);
  const todayIso = today.toISOString().slice(0, 10);

  return (
    <div style={styles.container}>
      <NavBar />
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>Calendar View</h1>
          <p style={styles.subtitle}>
            {loading ? "Loading…" : `${events.length} event${events.length !== 1 ? "s" : ""} in view`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/admin/ingest" style={{ ...styles.navLink, background: "#16a34a" }}>+ Ingest URL</Link>
        </div>
      </header>

      {/* Filter bar */}
      <form onSubmit={applyFilters} style={styles.filterBar}>
        <MultiSelectDropdown
          label="Status"
          options={STATUS_OPTIONS}
          selected={pending.status}
          onChange={(v) => setPending((p) => ({ ...p, status: v }))}
        />
        <MultiSelectDropdown
          label="Category"
          options={CATEGORY_OPTIONS}
          selected={pending.category}
          onChange={(v) => setPending((p) => ({ ...p, category: v }))}
        />
        <button type="submit" style={styles.applyBtn}>Apply</button>
        <button type="button" onClick={clearFilters} style={styles.clearBtn}>Clear</button>
      </form>

      {error && <p style={styles.error}>Error: {error}</p>}

      {/* Month navigation */}
      <div style={styles.monthNav}>
        <button onClick={prevMonth} style={styles.navBtn}>◀</button>
        <h2 style={styles.monthLabel}>{MONTH_NAMES[viewMonth]} {viewYear}</h2>
        <button onClick={nextMonth} style={styles.navBtn}>▶</button>
      </div>

      {/* Calendar grid */}
      <div style={styles.calendarWrapper}>
        {/* Day-of-week headers */}
        <div style={styles.dayHeaderRow}>
          {DAY_HEADERS.map((d) => (
            <div key={d} style={styles.dayHeader}>{d}</div>
          ))}
        </div>

        {weeks.map((week, wi) => (
          <div key={wi} style={styles.weekRow}>
            {week.map((day, di) => {
              if (day === null) return <div key={di} style={styles.emptyCell} />;
              const iso = makeIsoDate(viewYear, viewMonth, day);
              const dayEvents = byDate[iso] || [];
              const dayUncertain = uncertainByDate[iso] || [];
              const isToday = iso === todayIso;
              return (
                <div key={di} style={{ ...styles.dayCell, ...(isToday ? styles.todayCell : {}) }}>
                  <div style={{ ...styles.dayNumber, ...(isToday ? styles.todayNumber : {}) }}>{day}</div>
                  {dayEvents.map((ev) => (
                    <div
                      key={ev.id}
                      onClick={() => navigate(`/events/${ev.id}`)}
                      style={{
                        ...styles.eventChip,
                        background: STATUS_COLORS[ev.status] || "#f3f4f6",
                      }}
                      title={`${ev.business_name || "(unnamed)"} — ${ev.status}`}
                    >
                      {ev.business_name || "(unnamed)"}
                    </div>
                  ))}
                  {dayUncertain.length > 0 && (
                    <div style={{ position: "relative" }}>
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenUncertainDay(openUncertainDay === iso ? null : iso);
                        }}
                        style={{
                          ...styles.eventChip,
                          background: "repeating-linear-gradient(45deg, #dbeafe, #dbeafe 4px, #fff 4px, #fff 8px)",
                          fontStyle: "italic",
                          cursor: "pointer",
                          userSelect: "none",
                        }}
                        title={`${dayUncertain.length} event${dayUncertain.length !== 1 ? "s" : ""} with uncertain dates — click to expand`}
                      >
                        ~{dayUncertain.length} uncertain
                      </div>
                      {openUncertainDay === iso && (
                        <div style={styles.uncertainPopover} onClick={(e) => e.stopPropagation()}>
                          <div style={styles.popoverHeader}>
                            Uncertain · {dayUncertain.length} event{dayUncertain.length !== 1 ? "s" : ""}
                          </div>
                          {dayUncertain.map((ev) => (
                            <div
                              key={ev.id}
                              onClick={() => navigate(`/events/${ev.id}`)}
                              style={styles.popoverItem}
                              onMouseEnter={(e) => { e.currentTarget.style.background = "#f0f9ff"; }}
                              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                              title={`${ev.date_confidence}: ${ev.date_range_start} – ${ev.date_range_end}`}
                            >
                              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {ev.business_name || "(unnamed)"}
                              </span>
                              <span style={styles.popoverConf}>{ev.date_confidence}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Events with no date */}
      {noDate.length > 0 && (
        <div style={styles.noDateSection}>
          <h3 style={styles.noDateTitle}>No date set ({noDate.length})</h3>
          {noDate.map((ev) => (
            <div key={ev.id} style={styles.noDateRow}>
              <Link to={`/events/${ev.id}`} style={styles.noDateLink}>
                {ev.business_name || "(unnamed)"}
              </Link>
              <span style={{ color: "#9ca3af", fontSize: "0.82rem", marginLeft: 8 }}>{ev.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: { minHeight: "100vh", background: "#f8fafc", fontFamily: "system-ui, sans-serif" },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, padding: "20px 32px 12px", background: "#fff", borderBottom: "1px solid #e5e7eb" },
  title: { margin: 0, fontSize: "1.6rem", color: "#111827", fontWeight: 700 },
  subtitle: { margin: "4px 0 0", color: "#6b7280", fontSize: "0.92rem" },
  navLink: { textDecoration: "none", padding: "7px 16px", borderRadius: 6, background: "#374151", color: "#fff", fontWeight: 600, fontSize: "0.88rem" },
  filterBar: { display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end", padding: "12px 32px", background: "#fff", borderBottom: "1px solid #e5e7eb" },
  filterLabel: { display: "flex", flexDirection: "column", gap: 3, fontSize: "0.82rem", fontWeight: 600, color: "#374151" },
  select: { padding: "5px 8px", borderRadius: 5, border: "1px solid #d1d5db", fontSize: "0.9rem", minWidth: 130 },
  applyBtn: { padding: "6px 18px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, fontSize: "0.9rem", cursor: "pointer" },
  clearBtn: { padding: "6px 14px", background: "#e5e7eb", color: "#374151", border: "none", borderRadius: 6, fontWeight: 600, fontSize: "0.9rem", cursor: "pointer" },
  monthNav: { display: "flex", alignItems: "center", gap: 16, padding: "14px 32px 8px", background: "#fff" },
  monthLabel: { margin: 0, fontSize: "1.25rem", fontWeight: 700, color: "#111827", minWidth: 200, textAlign: "center" },
  navBtn: { padding: "4px 14px", fontSize: "1rem", border: "1px solid #d1d5db", borderRadius: 6, background: "#f9fafb", cursor: "pointer" },
  calendarWrapper: { padding: "0 24px 24px", maxWidth: 1100, margin: "0 auto" },
  dayHeaderRow: { display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, marginBottom: 4, paddingTop: 8 },
  dayHeader: { textAlign: "center", fontSize: "0.78rem", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", padding: "4px 0" },
  weekRow: { display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, marginBottom: 4 },
  dayCell: { minHeight: 80, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 6, padding: "4px 6px", overflow: "visible" },
  emptyCell: { minHeight: 80, background: "#f9fafb", borderRadius: 6 },
  todayCell: { border: "2px solid #2563eb" },
  dayNumber: { fontSize: "0.82rem", fontWeight: 600, color: "#374151", marginBottom: 2 },
  todayNumber: { color: "#2563eb" },
  eventChip: { fontSize: "0.72rem", borderRadius: 4, padding: "2px 5px", marginBottom: 2, cursor: "pointer", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontWeight: 500 },
  noDateSection: { padding: "16px 32px", borderTop: "1px solid #e5e7eb" },
  noDateTitle: { margin: "0 0 8px", fontSize: "1rem", color: "#374151", fontWeight: 700 },
  noDateRow: { padding: "4px 0" },
  noDateLink: { color: "#2563eb", textDecoration: "none", fontWeight: 500, fontSize: "0.9rem" },
  error: { color: "#dc2626", padding: "8px 32px", margin: 0 },
  uncertainPopover: { position: "absolute", top: "100%", left: 0, zIndex: 200, background: "#fff", border: "1px solid #d1d5db", borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.15)", minWidth: 200, maxWidth: 280, padding: "4px 0" },
  popoverHeader: { fontSize: "0.7rem", fontWeight: 700, color: "#6b7280", padding: "5px 10px 6px", borderBottom: "1px solid #f3f4f6", textTransform: "uppercase", letterSpacing: "0.05em" },
  popoverItem: { padding: "5px 10px", cursor: "pointer", fontSize: "0.78rem", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, background: "transparent" },
  popoverConf: { fontSize: "0.68rem", color: "#9ca3af", fontStyle: "italic", flexShrink: 0 },
};
