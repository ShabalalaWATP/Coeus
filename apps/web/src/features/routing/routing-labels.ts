export function formatTaggedReason(reason: string) {
  const parts = reason.includes(":") ? reason.split(":").slice(1) : [reason];
  const label = parts.join(" ").replaceAll("-", " ").replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}
