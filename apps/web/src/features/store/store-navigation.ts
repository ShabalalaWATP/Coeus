export type StoreNavigationState = {
  from?: string;
  origin?: "rfi" | "store" | "library";
};

export function storeNavigationState(value: unknown): StoreNavigationState {
  if (value === null || typeof value !== "object") return {};
  const candidate = value as Record<string, unknown>;
  return {
    from: typeof candidate.from === "string" ? candidate.from : undefined,
    origin:
      candidate.origin === "rfi" || candidate.origin === "store" || candidate.origin === "library"
        ? candidate.origin
        : undefined,
  };
}

export function backNavigationFor(
  from: string | undefined,
  origin?: StoreNavigationState["origin"],
) {
  if (origin === "rfi" && from !== undefined && isRequestPath(from)) {
    return { path: from, label: "Back to request" };
  }
  if (from === undefined || from === "/store") {
    return { path: "/store", label: "Back to store" };
  }
  if (from === "/rfa/products" || from === "/collection/products") {
    return { path: from, label: "Back to products" };
  }
  return { path: "/store", label: "Back to store" };
}

function isRequestPath(path: string) {
  return /^\/app\/requests\/[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(path);
}
