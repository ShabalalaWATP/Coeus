export function backNavigationFor(from: string | undefined) {
  if (from === undefined || from === "/store") {
    return { path: "/store", label: "Back to store" };
  }
  return { path: from, label: "Back to products" };
}
