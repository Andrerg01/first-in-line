import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import EventList from "./pages/EventList";
import EventDetail from "./pages/EventDetail";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<EventList />} />
        <Route path="/events/:eventId" element={<EventDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

