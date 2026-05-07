import { Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "../pages/Dashboard.jsx";
import RepoPage from "../pages/RepoPage.jsx";
import QueryPage from "../pages/QueryPage.jsx";
import TestGenerationPage from "../pages/TestGenerationPage.jsx";
import SettingsPage from "../pages/SettingsPage.jsx";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/repositories" element={<RepoPage />} />
      <Route path="/search" element={<QueryPage />} />
      <Route path="/tests" element={<TestGenerationPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
