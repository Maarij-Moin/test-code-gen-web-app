import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AuthLayout } from "@/layouts/AuthLayout";
import { AppLayout } from "@/layouts/AppLayout";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { Dashboard } from "@/pages/Dashboard";
import { GeneratedTestsViewer } from "@/pages/GeneratedTestsViewer";
import { JobMonitoring } from "@/pages/JobMonitoring";
import { Login } from "@/pages/Login";
import { PullRequestMonitor } from "@/pages/PullRequestMonitor";
import { Register } from "@/pages/Register";
import { RepositoryDetails } from "@/pages/RepositoryDetails";
import { RepoActivity } from "@/pages/RepoActivity";
import { Settings } from "@/pages/Settings";
import { useUiStore } from "@/stores/uiStore";

export default function App() {
  const theme = useUiStore((state) => state.theme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="/repositories/:repoId" element={<RepositoryDetails />} />
          <Route path="/jobs" element={<JobMonitoring />} />
          <Route path="/tests" element={<GeneratedTestsViewer />} />
          <Route path="/pull-requests" element={<PullRequestMonitor />} />
          <Route path="/activity" element={<RepoActivity />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
