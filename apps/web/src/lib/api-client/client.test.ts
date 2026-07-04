import { ApiClient, ApiError } from "./client";
import { previewSession } from "../../test/test-utils";

test("sends request id headers and returns typed JSON", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        status: "ok",
        service: "coeus-api",
        environment: "test",
        request_id: "req-web",
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const response = await new ApiClient("http://api.test").getLiveness("req-web");

  expect(response.status).toBe("ok");
  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/health/live", {
    credentials: "include",
    headers: { "X-Request-ID": "req-web" },
    method: "GET",
  });
});

test("posts login payloads with credentials included", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(previewSession),
  });
  vi.stubGlobal("fetch", fetchMock);

  await new ApiClient("http://api.test").login({
    username: "admin@example.test",
    password: "CoeusLocal1!",
  });

  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/auth/login", {
    body: JSON.stringify({ username: "admin@example.test", password: "CoeusLocal1!" }),
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
});

test("sends csrf header for logout", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", fetchMock);

  await new ApiClient("http://api.test").logout("csrf-token");

  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/auth/logout", {
    credentials: "include",
    headers: { "X-CSRF-Token": "csrf-token" },
    method: "POST",
  });
});

test("throws parsed API errors on logout failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () => Promise.resolve({ error: { code: "csrf_failed", message: "CSRF failed." } }),
    }),
  );

  await expect(new ApiClient("http://api.test").logout("bad-csrf")).rejects.toEqual(
    new ApiError(403, "csrf_failed", "CSRF failed."),
  );
});

test("throws parsed API errors on non-success responses", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 423,
      json: () =>
        Promise.resolve({
          error: { code: "account_locked", message: "Authentication temporarily locked." },
        }),
    }),
  );

  await expect(new ApiClient("http://api.test").getCurrentUser()).rejects.toEqual(
    new ApiError(423, "account_locked", "Authentication temporarily locked."),
  );
});

test("uses fallback API error details when the response body is not JSON", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("invalid json")),
    }),
  );

  await expect(new ApiClient("http://api.test").getCurrentUser()).rejects.toEqual(
    new ApiError(500, "request_failed", "API request failed with status 500"),
  );
});
