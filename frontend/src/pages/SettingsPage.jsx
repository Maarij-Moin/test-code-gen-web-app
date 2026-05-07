export default function SettingsPage() {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold">Environment Settings</h3>
      <p className="mt-2 text-sm text-muted">
        Configure environment variables for API endpoints and authentication.
      </p>
      <div className="mt-4 grid gap-3 text-sm">
        <div className="flex justify-between">
          <span className="text-muted">API Base URL</span>
          <span>{import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">API Key</span>
          <span>{import.meta.env.VITE_API_KEY ? "Configured" : "Not set"}</span>
        </div>
      </div>
    </div>
  );
}
