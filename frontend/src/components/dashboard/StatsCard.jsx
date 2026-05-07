import { formatNumber } from "../../utils/formatters.js";

export default function StatsCard({ label, value, icon: Icon }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <p className="label">{label}</p>
        {Icon && <Icon size={18} className="text-brand" />}
      </div>
      <p className="mt-4 text-3xl font-semibold">{formatNumber(value)}</p>
    </div>
  );
}
