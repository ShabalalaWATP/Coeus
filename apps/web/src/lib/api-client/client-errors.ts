type ErrorPayload = {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: Array<{ msg?: string }>;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type AuthEventHandlers = {
  onUnauthorized?: () => void;
  onPasswordChangeRequired?: () => void;
};

let authEventHandlers: AuthEventHandlers = {};

/**
 * Registers global listeners for authentication failures raised by any API
 * call. The auth provider uses these to move the app to the session-expired
 * screen (401) or the forced password-change screen (403 with the
 * password_change_required code). Auth endpoints themselves are excluded so
 * login and password-change failures stay local to their forms.
 */
export function setAuthEventHandlers(handlers: AuthEventHandlers) {
  authEventHandlers = handlers;
}

function notifyAuthFailure(error: ApiError, path: string) {
  if (path.startsWith("/api/v1/auth/")) {
    return;
  }
  if (error.status === 401) {
    authEventHandlers.onUnauthorized?.();
  }
  if (error.status === 403 && error.code === "password_change_required") {
    authEventHandlers.onPasswordChangeRequired?.();
  }
}

export async function toApiError(response: Response, path: string): Promise<ApiError> {
  let payload: ErrorPayload = {};
  try {
    payload = (await response.json()) as ErrorPayload;
  } catch {
    payload = {};
  }
  const validationMessage = payload.detail
    ?.find((detail) => detail.msg)
    ?.msg?.replace(/^Value error,\s*/, "");
  const error = new ApiError(
    response.status,
    payload.error?.code ?? (validationMessage ? "request_validation_failed" : "request_failed"),
    payload.error?.message ??
      validationMessage ??
      `API request failed with status ${response.status}`,
  );
  notifyAuthFailure(error, path);
  return error;
}
