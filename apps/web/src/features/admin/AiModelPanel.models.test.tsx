import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AiModelPanel } from "./AiModelPanel";
import { modelState, providers } from "./ai-model.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("refreshes the model list from the provider and reports the count", async () => {
  const refreshed = {
    ...modelState,
    providers: providers.map((entry) =>
      entry.name === "openai_api" ? { ...entry, models: [...entry.models, "gpt-6-omni"] } : entry,
    ),
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(refreshed) });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("tab", { name: /OpenAI API/ }));
  await userEvent.click(screen.getByRole("button", { name: "Refresh from provider" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8001/api/v1/admin/ai-model/refresh",
      expect.objectContaining({
        body: JSON.stringify({ provider: "openai_api" }),
        method: "POST",
      }),
    ),
  );
  expect(await screen.findByText(/3 models available for OpenAI API/)).toBeVisible();
  expect(screen.getByRole("radio", { name: /gpt-6-omni/ })).toBeInTheDocument();
});

test("surfaces a refresh error from a provider without live listing", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValue({
      ok: false,
      status: 422,
      json: () =>
        Promise.resolve({
          error: { code: "refresh_not_supported", message: "Add model ids by hand instead." },
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("tab", { name: /OpenAI API/ }));
  await userEvent.click(screen.getByRole("button", { name: "Refresh from provider" }));

  expect(await screen.findByText("Add model ids by hand instead.")).toBeVisible();
});

test("adds a custom model id and surfaces a rejection", async () => {
  const added = {
    ...modelState,
    providers: providers.map((entry) =>
      entry.name === "openai_api"
        ? { ...entry, models: [...entry.models, "gpt-6-omni"], activeModel: "gpt-6-omni" }
        : entry,
    ),
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(added) })
    .mockResolvedValue({
      ok: false,
      status: 422,
      json: () =>
        Promise.resolve({ error: { code: "validation_error", message: "Bad model id." } }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("tab", { name: /OpenAI API/ }));
  await userEvent.type(screen.getByLabelText("Add a model id"), "gpt-6-omni");
  await userEvent.click(screen.getByRole("button", { name: "Add" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8001/api/v1/admin/ai-model/custom-model",
      expect.objectContaining({
        body: JSON.stringify({ provider: "openai_api", model: "gpt-6-omni" }),
        method: "POST",
      }),
    ),
  );
  expect(await screen.findByText(/Added gpt-6-omni and selected it/)).toBeVisible();

  await userEvent.type(screen.getByLabelText("Add a model id"), "junk");
  await userEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(await screen.findByText("Bad model id.")).toBeVisible();
});
