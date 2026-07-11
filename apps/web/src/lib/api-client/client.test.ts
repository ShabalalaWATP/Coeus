import { ApiError, apiRequest, getLiveness, pathSegment, resolveApiBaseUrl } from "./client";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

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

  const response = await getLiveness("req-web", "http://api.test");

  expect(response.status).toBe("ok");
  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/health/live", {
    credentials: "include",
    headers: { "X-Request-ID": "req-web" },
    method: "GET",
  });
});

test("omits request id headers when none are provided", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  vi.stubGlobal("fetch", fetchMock);

  await getLiveness(undefined, "http://api.test");

  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/health/live", {
    credentials: "include",
    headers: undefined,
    method: "GET",
  });
});

test("returns checked raw responses", async () => {
  const response = { ok: true } as Response;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

  await expect(apiRequest("/blob", { cache: "no-store" }, "http://api.test")).resolves.toBe(
    response,
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

  await expect(apiRequest("/api/v1/profile", { method: "GET" }, "http://api.test")).rejects.toEqual(
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

  await expect(apiRequest("/api/v1/profile", { method: "GET" }, "http://api.test")).rejects.toEqual(
    new ApiError(500, "request_failed", "API request failed with status 500"),
  );
});

test("resolves configured and fallback API base URLs", () => {
  expect(resolveApiBaseUrl()).toBe("http://127.0.0.1:8001");
  vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test");
  expect(resolveApiBaseUrl()).toBe("https://api.example.test");
});

test("encodes reserved characters in path segments", () => {
  expect(pathSegment("product/one two")).toBe("product%2Fone%20two");
});
