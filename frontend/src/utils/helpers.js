export function classNames(...classes) {
  return classes.filter(Boolean).join(" ");
}

export function truncate(text, max = 120) {
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

export function safeCopy(text) {
  if (!navigator?.clipboard) return Promise.reject(new Error("Clipboard not available"));
  return navigator.clipboard.writeText(text);
}
