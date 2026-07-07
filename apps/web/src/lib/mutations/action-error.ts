import { useCallback, useState } from "react";

import { ApiError } from "../api-client/client";

/**
 * Maps a failed mutation to a user-visible message. API error bodies carry a
 * human-readable message when the backend rejected the request deliberately;
 * generic transport failures fall back to the caller-supplied message.
 */
export function actionErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.code !== "request_failed") {
    return error.message;
  }
  return fallback;
}

/**
 * Small shared state holder for inline mutation errors. Use
 * `failActionWith(fallback)` as a mutation `onError` handler and
 * `clearActionError` in `onMutate` or `onSuccess`.
 */
export function useActionError() {
  const [actionError, setActionError] = useState<string | null>(null);
  const clearActionError = useCallback(() => setActionError(null), []);
  const failActionWith = useCallback(
    (fallback: string) => (error: unknown) => setActionError(actionErrorMessage(error, fallback)),
    [],
  );
  return { actionError, clearActionError, failActionWith };
}
