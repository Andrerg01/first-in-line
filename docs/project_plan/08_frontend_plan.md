# Frontend Plan

## Framework

React.

Recommended stack:

```text
Vite
React Router
TanStack Query
Map library: Mapbox, Leaflet, or Azure Maps
Calendar library: FullCalendar or similar
````

## Main Pages

## Home / Event List

Route:

```text
/
```

Features:

* list upcoming events
* filter by date
* filter by category
* filter by status
* filter by distance/location
* sort by date or confidence

## Map View

Route:

```text
/map
```

Features:

* show events as pins
* click pin to open event preview
* filter by date/category/status
* open event detail page

## Calendar View

Route:

```text
/calendar
```

Features:

* show events by date
* click event to open detail page

## Event Detail

Route:

```text
/events/:eventId
```

Shows:

* business name
* event date
* address
* promotion
* notes
* confidence score
* status
* source links
* extracted evidence quotes
* extracted claims
* admin actions if admin mode enabled

## Manual Ingestion Page

Route:

```text
/admin/ingest
```

Features:

* paste URL
* submit for extraction
* view candidate result
* approve/reject/edit

## Admin Review Queue

Route:

```text
/admin/review
```

Features:

* list candidate events
* show possible duplicates
* verify/reject/merge
* show conflicts

## UI Status Labels

Use clear labels:

```text
Candidate
Verified
Needs Review
Rejected
Expired
Possible Duplicate
```

## First MVP Screens

Build only these first:

1. Event list.
2. Event detail.
3. Manual URL ingestion.
4. Admin review buttons.

Map and calendar can come after the data model is stable.

## Frontend API Access

Preferred:

```text
fetch("/api/events")
```

The ingress should route `/api/*` to the backend.

Avoid hardcoding pod or service names in browser-side code.