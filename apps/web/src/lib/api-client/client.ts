import { toApiError } from "./client-errors";

export { ApiError, setAuthEventHandlers } from "./client-errors";

export async function apiRequest(
  path: string,
  init: RequestInit,
  baseUrl = resolveApiBaseUrl(),
): Promise<Response> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    credentials: "include",
  });
  if (!response.ok) {
    throw await toApiError(response, path);
  }
  return response;
}

export async function apiRequestJson<TResponse>(
  path: string,
  init: RequestInit,
  baseUrl?: string,
): Promise<TResponse> {
  const response = await apiRequest(path, init, baseUrl);
  return (await response.json()) as TResponse;
}

export async function apiRequestNoContent(
  path: string,
  init: RequestInit,
  baseUrl?: string,
): Promise<void> {
  await apiRequest(path, init, baseUrl);
}

export function resolveApiBaseUrl(): string {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return configuredUrl ?? "http://127.0.0.1:8001";
}

export function pathSegment(value: string): string {
  return encodeURIComponent(value);
}
