export default function EmptyState({ title, message }) {
  return (
    <div className="card-muted text-center">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted">{message}</p>
    </div>
  );
}
