export function formatNumber(value) {
  if (value === null || value === undefined) return "0";
  return new Intl.NumberFormat().format(value);
}

export function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}
