import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AiModelPanel } from "./AiModelPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const modelState = {
  provider: "mock",
  activeModel: "gemma-4-31b",
  availableModels: ["gemma-4-31b", "gemini-2.5-flash", "gemini-2.5-pro"],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("switches the active Gemini model", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...modelState, activeModel: "gemini-2.5-pro" }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  const select = await screen.findByLabelText("Active model");
  expect(screen.getByRole("button", { name: "Apply model" })).toBeDisabled();

  await userEvent.selectOptions(select, "gemini-2.5-pro");
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
  expect(await screen.findByText(/local mock/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Apply model" })).toBeDisabled();
});

test("shows a generic error when the switch fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...modelState, provider: "gemma_vertex" }),
    })
    .mockResolvedValue({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ error: { code: "model_not_available", message: "No." } }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.selectOptions(await screen.findByLabelText("Active model"), "gemini-2.5-flash");
  await userEvent.click(screen.getByRole("button", { name: "Apply model" }));

  expect(
    await screen.findByText("The model could not be changed. Refresh and try again."),
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
