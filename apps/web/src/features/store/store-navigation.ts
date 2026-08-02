import { readStoreSearch, writeStoreSearch } from "./store-search-params";

export type StoreNavigationState = {
  from?: string;
  origin?: "rfi" | "store" | "library";
  search?: string;
};

const TEAM_PRODUCT_PATHS = ["/rfa/products", "/collection/products"];
const STORE_LIST_PATHS = ["/store", "/store/my-products"];

export function storeNavigationState(value: unknown): StoreNavigationState {
  if (value === null || typeof value !== "object") return {};
  const candidate = value as Record<string, unknown>;
  return {
    from: typeof candidate.from === "string" ? candidate.from : undefined,
    origin:
      candidate.origin === "rfi" || candidate.origin === "store" || candidate.origin === "library"
        ? candidate.origin
        : undefined,
    search: typeof candidate.search === "string" ? candidate.search : undefined,
  };
}

export function backNavigationFor(
  from: string | undefined,
  origin?: StoreNavigationState["origin"],
  search?: string,
) {
  if (origin === "rfi" && from !== undefined && isRequestPath(from)) {
    return { path: from, label: "Back to request" };
  }
  if (from !== undefined && TEAM_PRODUCT_PATHS.includes(from)) {
    return { path: `${from}${safeSearch(search)}`, label: "Back to products" };
  }
  if (from !== undefined && STORE_LIST_PATHS.includes(from)) {
    return { path: `${from}${safeSearch(search)}`, label: "Back to store" };
  }
  return { path: "/store", label: "Back to store" };
}

/**
 * Rebuild the return query from known store parameters only.
 *
 * Navigation state is presentation-only and never authority, so it is treated
 * as untrusted: reading it back through the store search parser means only
 * recognised keys and bounded values can ever reach the return link.
 */
function safeSearch(search: string | undefined): string {
  if (search === undefined || search === "") return "";
  const params = writeStoreSearch(readStoreSearch(new URLSearchParams(search))).toString();
  return params === "" ? "" : `?${params}`;
}

function isRequestPath(path: string) {
  return /^\/app\/requests\/[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(path);
}
