import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Home from "./pages/Home";
import History from "./pages/History";
import Result from "./pages/Result";
import AdminManuals from "./pages/AdminManuals";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/history" element={<History />} />
        <Route path="/result/:jobId" element={<Result />} />
        <Route path="*" element={<Navigate to="/" replace />} />
          <Route path="/admin/manuals" element={<AdminManuals />} />
      </Routes>
    </BrowserRouter>
  );
}