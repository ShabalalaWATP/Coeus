export function formatTaggedReason(reason: string) {
  const parts = reason.split(":").slice(1);
  const label = parts.join(" ").replaceAll("-", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}
