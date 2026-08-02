import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SaveProductControl } from "./SaveProductControl";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const product = {
  id: "product-1",
  reference: "INT-001",
  title: "Regional report",
  summary: "Summary",
  description: "Description",
  productType: "assessment_report",
  sourceType: "finished_assessment",
  ownerTeam: "RFA",
  areaOrRegion: "Eastern Europe",
  classificationLevel: 2,
  releasability: [],
  handlingCaveats: [],
  tags: [],
  semanticLabels: [],
  acgIds: [],
  status: "published",
  timePeriodStart: null,
  timePeriodEnd: null,
  geojsonRef: null,
  assets: [],
};

beforeEach(() => resetQueryClientForTests());

test("saves a product into a personal folder and then offers removal", async () => {
  let saved = false;
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    if (url.endsWith("/api/v1/store/library") && (!init?.method || init.method === "GET")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            folders: [{ id: "folder-1", name: "Watchlist", createdAt: "2026-08-02T00:00:00Z" }],
            savedProducts: saved
              ? [{ product, folderId: "folder-1", savedAt: "2026-08-02T00:00:00Z" }]
              : [],
            unavailableCount: 0,
          }),
      });
    }
    if (init?.method === "PUT") {
      saved = true;
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ product, folderId: "folder-1", savedAt: "2026-08-02T00:00:00Z" }),
      });
    }
    if (init?.method === "DELETE") {
      saved = false;
      return Promise.resolve({ ok: true });
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<SaveProductControl productId="product-1" />, "/store/products/product-1");
  await userEvent.click(screen.getByRole("button", { name: "Save or organise" }));
  await screen.findByRole("option", { name: "Watchlist" });
  await userEvent.selectOptions(await screen.findByLabelText("Save to"), "folder-1");
  await userEvent.click(screen.getByRole("button", { name: "Save report" }));

  await waitFor(() => expect(screen.getByRole("button", { name: "Remove" })).toBeVisible());
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/library/products/product-1",
    expect.objectContaining({
      body: JSON.stringify({ folderId: "folder-1" }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "test-csrf-token",
      },
      method: "PUT",
    }),
  );

  await userEvent.click(screen.getByRole("button", { name: "Remove" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Save report" })).toBeVisible());
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/library/products/product-1",
    expect.objectContaining({
      headers: { "X-CSRF-Token": "test-csrf-token" },
      method: "DELETE",
    }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("button", { name: "Save or organise" })).toBeVisible();
});
