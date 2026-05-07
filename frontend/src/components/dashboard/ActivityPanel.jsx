import { formatDate } from "../../utils/formatters.js";

export default function ActivityPanel({ activity }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Recent Activity</h3>
        <span className="badge">Last 8</span>
      </div>
      <div className="mt-4 space-y-3">
        {activity.length === 0 && (
          <p className="text-sm text-muted">No activity recorded yet.</p>
        )}
        {activity.map((item, index) => (
          <div key={index} className="flex items-center justify-between text-sm">
            <span className="text-text">{item.message}</span>
            <span className="text-xs text-muted">{formatDate(item.time || Date.now())}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
