import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AiModelPanel } from "./AiModelPanel";
import { liveRegion, modelState, providers } from "./ai-model.fixtures";
import { modelInfoFor } from "./model-catalogue";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("describes catalogued models and falls back for unknown ones", () => {
  expect(modelInfoFor("gemini-2.5-pro").tier).toBe("Advanced");
  expect(modelInfoFor("gpt-5-mini").tier).toBe("Fast");
  expect(modelInfoFor("experimental-model").tier).toBe("Custom");
});

test("switches the active model within the live provider", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ...modelState,
          activeModel: "gemini-2.5-pro",
          changedBy: "admin@example.test",
          changedAt: "2026-07-06T09:00:00Z",
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  expect(await screen.findByRole("radio", { name: /gemma-4-31b/ })).toBeChecked();
  expect(screen.getByRole("button", { name: "Apply model" })).toBeDisabled();

  await userEvent.click(screen.getByRole("radio", { name: /gemini-2.5-pro/ }));
  await userEvent.click(screen.getByRole("button", { name: "Apply model" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8001/api/v1/admin/ai-model",
      expect.objectContaining({
        body: JSON.stringify({ model: "gemini-2.5-pro", provider: "gemini_api" }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "PUT",
      }),
    ),
  );
  await waitFor(() => expect(within(liveRegion()).getByText(/admin@example\.test/)).toBeVisible());
  expect(within(liveRegion()).getByText("Embeddings")).toBeVisible();
  expect(within(liveRegion()).getByText("mock")).toBeVisible();
  expect(within(liveRegion()).getByText("3")).toBeVisible();
});

test("stores an API key for the selected provider without rendering it back", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ...modelState,
          providers: providers.map((entry) =>
            entry.name === "openai_api" ? { ...entry, apiKeyConfigured: true } : entry,
          ),
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  await userEvent.type(screen.getByLabelText("OpenAI API key"), "sk-openai-secret");
  await userEvent.click(screen.getByRole("button", { name: "Save key" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8001/api/v1/admin/ai-model/api-key",
      expect.objectContaining({
        body: JSON.stringify({ apiKey: "sk-openai-secret", provider: "openai_api" }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "PUT",
      }),
    ),
  );
  expect(await screen.findByPlaceholderText("API key configured")).toBeVisible();
  expect(screen.queryByDisplayValue("sk-openai-secret")).not.toBeInTheDocument();
});

test("pressing Enter in the provider key field saves that key", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.type(
    await screen.findByLabelText("Gemini API (primary) key"),
    "gemini-secret-key{Enter}",
  );

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/admin/ai-model/api-key",
    expect.objectContaining({ method: "PUT" }),
  );
});

test("tests a provider connection and reports the outcome", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ok: false,
          provider: "openai_api",
          model: "gpt-5-mini",
          message: "No API key is configured for this provider.",
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  await userEvent.click(screen.getByRole("button", { name: "Test connection" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8001/api/v1/admin/ai-model/test",
      expect.objectContaining({
        body: JSON.stringify({ provider: "openai_api" }),
        method: "POST",
      }),
    ),
  );
  expect(await screen.findByText(/Connection failed: No API key is configured/)).toBeVisible();
});

test("reports a successful connection test", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ok: true,
          provider: "gemini_api",
          model: "gemma-4-31b",
          message: "gemma-4-31b answered the test prompt.",
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: "Test connection" }));

  expect(
    await screen.findByText(/Connection OK: gemma-4-31b answered the test prompt/),
  ).toBeVisible();
});

test("activating another provider warns about the app-wide change first", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ...modelState,
          providers: modelState.providers.map((provider) =>
            provider.name === "openai_api" ? { ...provider, apiKeyConfigured: true } : provider,
          ),
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ok: true,
          provider: "openai_api",
          model: "gpt-5-mini",
          message: "Connection verified.",
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ...modelState,
          provider: "openai_api",
          activeModel: "gpt-5-mini",
          changedBy: "admin@example.test",
          changedAt: "2026-07-06T09:00:00Z",
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
  await userEvent.click(screen.getByRole("button", { name: "Make active provider" }));

  // The warning explains the consequence before anything is sent.
  expect(
    await screen.findByText("This changes the AI provider for every user immediately."),
  ).toBeVisible();
  expect(screen.getByText(/all administrators will be notified/i)).toBeVisible();
  expect(fetchMock).toHaveBeenCalledTimes(2);

  await userEvent.click(screen.getByRole("button", { name: "Confirm and activate" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8001/api/v1/admin/ai-model/provider",
      expect.objectContaining({
        body: JSON.stringify({ provider: "openai_api" }),
        method: "PUT",
      }),
    ),
  );
  expect(await within(liveRegion()).findByText(/gpt-5-mini/)).toBeVisible();
});

test("cancelling the activation warning sends nothing", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ok: true,
          provider: "mock",
          model: "mock",
          message: "Connection verified.",
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /Mock \(offline\)/ }));
  expect(screen.getByText(/answers locally with deterministic replies/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
  await userEvent.click(screen.getByRole("button", { name: "Make active provider" }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(
    screen.queryByText("This changes the AI provider for every user immediately."),
  ).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("shows a generic error when the switch fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({ ...modelState, changedBy: "admin@example.test", changedAt: null }),
    })
    .mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("no body")),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("radio", { name: /gemini-2.5-flash/ }));
  await userEvent.click(screen.getByRole("button", { name: "Apply model" }));

  expect(
    await screen.findByText("The model could not be changed. Refresh and try again."),
  ).toBeVisible();
  expect(within(liveRegion()).getByText(/admin@example\.test/)).toBeVisible();
});

test("shows a key-specific error when saving the API key fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("no body")),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.type(
    await screen.findByLabelText("Gemini API (primary) key"),
    "gemini-secret-key",
  );
  await userEvent.click(screen.getByRole("button", { name: "Save key" }));

  expect(
    await screen.findByText("The API key could not be saved. Check the key and try again."),
  ).toBeVisible();
});

test("renders an error state when the model state cannot load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});
