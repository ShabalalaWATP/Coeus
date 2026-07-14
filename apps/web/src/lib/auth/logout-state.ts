import { ApiError } from "../api-client/client";

export const LOGOUT_MARKER_KEY = "coeus.logout.pending";

export function readLogoutMarker(): string | null {
  try {
    return window.localStorage.getItem(LOGOUT_MARKER_KEY);
  } catch {
    return null;
  }
}

export function writeLogoutMarker(value: "pending" | "unconfirmed" | null) {
  try {
    if (value === null) {
      window.localStorage.removeItem(LOGOUT_MARKER_KEY);
    } else {
      window.localStorage.setItem(LOGOUT_MARKER_KEY, `${value}:${window.crypto.randomUUID()}`);
    }
  } catch {
    // The in-memory state remains fail closed when browser storage is unavailable.
  }
}

export function logoutTransitionError() {
  return new ApiError(
    409,
    "logout_unconfirmed",
    "Sign-out must be confirmed before signing in again.",
  );
}
