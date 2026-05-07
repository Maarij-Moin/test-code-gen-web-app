export default function ErrorAlert({ message, onClear }) {
  if (!message) return null;
  return (
    <div className="card border border-danger/50 bg-danger/10">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-danger">{message}</p>
        {onClear && (
          <button className="text-xs text-muted" onClick={onClear}>
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}
