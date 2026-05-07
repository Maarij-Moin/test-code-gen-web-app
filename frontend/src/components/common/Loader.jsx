export default function Loader({ label = "Loading" }) {
  return (
    <div className="flex items-center gap-3 text-sm text-muted">
      <span className="h-3 w-3 animate-pulse rounded-full bg-brand" />
      {label}...
    </div>
  );
}
