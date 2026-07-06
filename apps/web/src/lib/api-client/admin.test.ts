import { getAiModelState, selectAiModel } from "./admin";
import { ApiError } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

test("reads and updates the AI model with CSRF protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({ provider: "mock", activeModel: "gemma-4-31b", availableModels: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await getAiModelState();
  await selectAiModel("gemini-2.5-pro", "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/admin/ai-model", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/admin/ai-model",
    expect.objectContaining({
      body: JSON.stringify({ model: "gemini-2.5-pro" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "PUT",
    }),
  );
});

test("converts AI model API errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: () =>
        Promise.resolve({ error: { code: "model_not_available", message: "Not available." } }),
    }),
  );

  await expect(selectAiModel("bad-model", "csrf")).rejects.toEqual(
    new ApiError(422, "model_not_available", "Not available."),
  );
});
