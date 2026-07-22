import { screen, within } from "@testing-library/react";

import { AiModelPanel } from "./AiModelPanel";
import { liveRegion, modelState, providers } from "./ai-model.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("shows when the live text provider has a saved key", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          ...modelState,
          providers: providers.map((entry) =>
            entry.name === "gemini_api" ? { ...entry, apiKeyConfigured: true } : entry,
          ),
        }),
    }),
  );

  renderWithProviders(<AiModelPanel csrfToken="test-csrf-token" />, "/admin/overview");

  expect(await screen.findByText("Key saved")).toBeVisible();
  expect(within(liveRegion()).getByText("Saved")).toBeVisible();
});
