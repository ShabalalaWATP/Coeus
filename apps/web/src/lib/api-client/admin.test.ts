import {
  addCustomAiModel,
  configureAiApiKey,
  getAiModelState,
  listAdminUsers,
  refreshAiModels,
  resetAdminUserCredential,
  selectAiModel,
  selectAiProvider,
  testAiConnection,
  updateAdminUserClearance,
  updateAdminUserRoles,
  updateAdminUserStatus,
} from "./admin";
import { ApiError } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

test("reads and updates the AI provider and model with CSRF protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        provider: "mock",
        activeModel: "gemma-4-31b",
        availableModels: [],
        apiKeyConfigured: false,
        providers: [],
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await getAiModelState();
  await selectAiModel("gemini-2.5-pro", "gemini_api", "csrf");
  await configureAiApiKey("gemini-key-value", "gemini_api", "csrf");
  await selectAiProvider("gemini_api", "csrf");
  await testAiConnection("gemini_api", "csrf");
  await refreshAiModels("gemini_api", "csrf");
  await addCustomAiModel("gemini_api", "gemini-4-pro", "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/admin/ai-model", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/admin/ai-model",
    expect.objectContaining({
      body: JSON.stringify({ model: "gemini-2.5-pro", provider: "gemini_api" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "PUT",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/admin/ai-model/api-key",
    expect.objectContaining({
      body: JSON.stringify({ apiKey: "gemini-key-value", provider: "gemini_api" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "PUT",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8001/api/v1/admin/ai-model/provider",
    expect.objectContaining({
      body: JSON.stringify({ provider: "gemini_api" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "PUT",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    5,
    "http://127.0.0.1:8001/api/v1/admin/ai-model/test",
    expect.objectContaining({
      body: JSON.stringify({ provider: "gemini_api" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    6,
    "http://127.0.0.1:8001/api/v1/admin/ai-model/refresh",
    expect.objectContaining({
      body: JSON.stringify({ provider: "gemini_api" }),
      method: "POST",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    7,
    "http://127.0.0.1:8001/api/v1/admin/ai-model/custom-model",
    expect.objectContaining({
      body: JSON.stringify({ provider: "gemini_api", model: "gemini-4-pro" }),
      method: "POST",
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

  await expect(selectAiModel("bad-model", "gemini_api", "csrf")).rejects.toEqual(
    new ApiError(422, "model_not_available", "Not available."),
  );
});

test("calls user management endpoints with CSRF protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        users: [
          {
            id: "user-1",
            username: "analyst@example.test",
            displayName: "Analyst",
            roles: ["Intelligence Analyst"],
            clearanceLevel: 3,
            isActive: true,
          },
        ],
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listAdminUsers();
  await updateAdminUserRoles("user-1", ["User"], "csrf");
  await updateAdminUserClearance("user-1", 4, "csrf");
  await updateAdminUserStatus("user-1", false, "csrf");
  await resetAdminUserCredential("user-1", "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/admin/users",
    expect.objectContaining({ method: "GET" }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/admin/users/user-1/roles",
    expect.objectContaining({
      body: JSON.stringify({ roles: ["User"] }),
      method: "PUT",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/admin/users/user-1/clearance",
    expect.objectContaining({
      body: JSON.stringify({ clearanceLevel: 4 }),
      method: "PUT",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8001/api/v1/admin/users/user-1/status",
    expect.objectContaining({
      body: JSON.stringify({ isActive: false }),
      method: "PUT",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    5,
    "http://127.0.0.1:8001/api/v1/admin/users/user-1/credential-reset",
    expect.objectContaining({
      headers: { "X-CSRF-Token": "csrf" },
      method: "POST",
    }),
  );
});
