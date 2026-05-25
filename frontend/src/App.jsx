import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import EventList from "./pages/EventList";
import EventDetail from "./pages/EventDetail";
import AdminIngest from "./pages/AdminIngest";
import AdminReview from "./pages/AdminReview";
import MapView from "./pages/MapView";
import CalendarView from "./pages/CalendarView";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<EventList />} />
        <Route path="/events/:eventId" element={<EventDetail />} />
        <Route path="/map" element={<MapView />} />
        <Route path="/calendar" element={<CalendarView />} />
        <Route path="/admin/ingest" element={<AdminIngest />} />
        <Route path="/admin/review" element={<AdminReview />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

