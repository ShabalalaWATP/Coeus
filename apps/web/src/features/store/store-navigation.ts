export function backNavigationFor(from: string | undefined) {
  if (from === undefined || from === "/store") {
    return { path: "/store", label: "Back to store" };
  }
  if (from.startsWith("/projects")) {
    return { path: from, label: "Back to project" };
  }
  return { path: from, label: "Back to products" };
}
