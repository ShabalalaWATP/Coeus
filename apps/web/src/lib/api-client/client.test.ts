import { ApiClient } from "./client";

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
    headers: { "X-Request-ID": "req-web" },
  });
});

test("throws on non-success API responses", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 }));

  await expect(new ApiClient("http://api.test").getLiveness()).rejects.toThrow(
    "API request failed with status 503",
  );
});
