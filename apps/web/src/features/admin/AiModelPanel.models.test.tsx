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
  const configuredState = {
    ...modelState,
    providers: providers.map((entry) =>
      entry.name === "openai_api" ? { ...entry, apiKeyConfigured: true } : entry,
    ),
  };
  const refreshed = {
    ...configuredState,
    providers: configuredState.providers.map((entry) =>
      entry.name === "openai_api" ? { ...entry, models: [...entry.models, "gpt-6-omni"] } : entry,
    ),
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(configuredState) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(refreshed) });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  await userEvent.click(screen.getByRole("button", { name: "Refresh models from OpenAI API" }));

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

test("hides refresh for unsupported providers and disables it until a key is saved", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(modelState),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  expect(screen.getByRole("button", { name: "Refresh models from OpenAI API" })).toBeDisabled();
  expect(screen.getByText("Save a key before refreshing.")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: /GCP Vertex AI/ }));
  expect(screen.queryByText("Refresh from provider")).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test("adds a custom model ID and surfaces a rejection", async () => {
  const added = {
    ...modelState,
    providers: providers.map((entry) =>
      entry.name === "openai_api" ? { ...entry, models: [...entry.models, "gpt-6-omni"] } : entry,
    ),
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(added) })
    .mockResolvedValue({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ detail: [{ msg: "Value error, Bad model ID." }] }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  const modelInput = screen.getByLabelText("OpenAI API model ID");
  await userEvent.type(modelInput, "gpt-6-omni");
  await userEvent.click(screen.getByRole("button", { name: "Add model ID for OpenAI API" }));

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
  expect(await screen.findByText(/Added gpt-6-omni.*Apply model/)).toBeVisible();
  expect(modelInput).toHaveValue("");
  expect(screen.getByRole("radio", { name: /gpt-6-omni/ })).not.toHaveAccessibleName(/Active/);

  await userEvent.type(modelInput, "junk");
  await userEvent.click(screen.getByRole("button", { name: "Add model ID for OpenAI API" }));
  expect(await screen.findByText("Bad model ID.")).toBeVisible();
  expect(modelInput).toHaveValue("junk");
});

test("Enter adds a custom model instead of applying the selected model", async () => {
  const added = {
    ...modelState,
    providers: providers.map((entry) =>
      entry.name === "openai_api" ? { ...entry, models: [...entry.models, "gpt-6-enter"] } : entry,
    ),
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(modelState) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(added) });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");
  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  await userEvent.click(screen.getByDisplayValue("gpt-5"));
  await userEvent.type(screen.getByLabelText("OpenAI API model ID"), "gpt-6-enter{Enter}");

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/admin/ai-model/custom-model",
    expect.objectContaining({ method: "POST" }),
  );
  const calls = fetchMock.mock.calls as [string, RequestInit?][];
  expect(
    calls.some(
      ([url, init]) =>
        url === "http://127.0.0.1:8001/api/v1/admin/ai-model" && init?.method === "PUT",
    ),
  ).toBe(false);
});

test("switching providers clears an unsubmitted custom model ID", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(modelState) }),
  );
  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  await userEvent.type(screen.getByLabelText("OpenAI API model ID"), "gpt-draft");
  await userEvent.click(screen.getByRole("button", { name: /GCP Vertex AI/ }));

  expect(screen.getByLabelText("GCP Vertex AI model ID")).toHaveValue("");
});

test("locks other configuration controls while refresh is pending", async () => {
  const configuredState = {
    ...modelState,
    providers: providers.map((entry) =>
      entry.name === "openai_api" ? { ...entry, apiKeyConfigured: true } : entry,
    ),
  };
  let finishRefresh!: (value: object) => void;
  const deferredRefresh = new Promise((resolve) => {
    finishRefresh = resolve;
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(configuredState) })
    .mockReturnValueOnce(deferredRefresh);
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: /OpenAI API/ }));
  await userEvent.click(screen.getByRole("button", { name: "Refresh models from OpenAI API" }));

  expect(screen.getByRole("button", { name: /GCP Vertex AI/ })).toBeDisabled();
  expect(screen.getByLabelText("OpenAI API model ID")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Apply model" })).toBeDisabled();

  finishRefresh({ ok: true, json: () => Promise.resolve(configuredState) });
  await waitFor(() => expect(screen.getByRole("button", { name: /GCP Vertex AI/ })).toBeEnabled());
});
