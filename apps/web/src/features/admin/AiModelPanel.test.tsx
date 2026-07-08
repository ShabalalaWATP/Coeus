import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AiModelPanel } from "./AiModelPanel";
import { modelInfoFor } from "./model-catalogue";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const modelState = {
  provider: "mock",
  activeModel: "gemma-4-31b",
  availableModels: ["gemma-4-31b", "gemini-2.5-flash", "gemini-2.5-pro"],
  apiKeyConfigured: false,
  embeddingProvider: "mock",
  embeddedProductCount: 3,
  changedBy: null,
  changedAt: null,
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("describes catalogued models and falls back for unknown ones", () => {
  expect(modelInfoFor("gemini-2.5-pro").tier).toBe("Advanced");
  expect(modelInfoFor("gemini-3-flash").tier).toBe("Fast");
  expect(modelInfoFor("experimental-model").tier).toBe("Custom");
});

test("switches the active Gemini model from the card catalogue", async () => {
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
  expect(screen.getByText("Active")).toBeVisible();
  expect(screen.getByRole("button", { name: "Apply model" })).toBeDisabled();

  await userEvent.click(screen.getByRole("radio", { name: /gemini-2.5-pro/ }));
  await userEvent.click(screen.getByRole("button", { name: "Apply model" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8001/api/v1/admin/ai-model",
      expect.objectContaining({
        body: JSON.stringify({ model: "gemini-2.5-pro" }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "PUT",
      }),
    ),
  );
  expect(await screen.findByText(/mock provider active/)).toBeVisible();
  expect(screen.getByText(/embeddings: mock/)).toBeVisible();
  expect(screen.getByText(/embedded products: 3/)).toBeVisible();
  expect(screen.getByText(/last changed by admin@example.test/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Apply model" })).toBeDisabled();
});

test("stores a Gemini API key without rendering the key back", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ...modelState,
          apiKeyConfigured: true,
          changedBy: "admin@example.test",
          changedAt: "2026-07-06T09:00:00Z",
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.type(await screen.findByLabelText("Gemini API key"), "gemini-secret-key");
  await userEvent.click(screen.getByRole("button", { name: "Save key" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8001/api/v1/admin/ai-model/api-key",
      expect.objectContaining({
        body: JSON.stringify({ apiKey: "gemini-secret-key" }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "PUT",
      }),
    ),
  );
  expect(await screen.findByText(/Gemini API key configured/)).toBeVisible();
  expect(screen.queryByDisplayValue("gemini-secret-key")).not.toBeInTheDocument();
});

test("shows a generic error when the switch fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ...modelState,
          provider: "gemma_vertex",
          changedBy: "admin@example.test",
          changedAt: null,
        }),
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
  expect(screen.getByText(/last changed by admin@example.test/)).toBeVisible();
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

  await userEvent.type(await screen.findByLabelText("Gemini API key"), "gemini-secret-key");
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
