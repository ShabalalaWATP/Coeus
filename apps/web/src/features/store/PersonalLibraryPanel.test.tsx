import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PersonalLibraryPanel } from "./PersonalLibraryPanel";
import { productFixture } from "./store-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());

test("opens a personal library and creates an owned folder", async () => {
  const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "folder-2",
            name: "Eastern Europe",
            createdAt: "2026-08-02T00:00:00Z",
          }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          folders: [{ id: "folder-1", name: "Watchlist", createdAt: "2026-08-01T00:00:00Z" }],
          savedProducts: [
            { product: productFixture, folderId: "folder-1", savedAt: "2026-08-01T00:00:00Z" },
          ],
          unavailableCount: 0,
        }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<PersonalLibraryPanel />, "/store");

  expect(fetchMock).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Open my library" }));
  await userEvent.click(await screen.findByRole("button", { name: "Watchlist" }));
  expect(screen.getByRole("link", { name: /Regional Stability Brief/ })).toHaveAttribute(
    "href",
    "/store/products/product-regional",
  );

  await userEvent.type(screen.getByLabelText("New personal folder"), "Eastern Europe");
  await userEvent.click(screen.getByRole("button", { name: "Create folder" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/store/library/folders",
      expect.objectContaining({
        body: JSON.stringify({ name: "Eastern Europe" }),
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": "test-csrf-token",
        },
        method: "POST",
      }),
    ),
  );
});

test("filters saved reports and deletes a folder without hiding the library", async () => {
  const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "DELETE") return Promise.resolve({ ok: true });
    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          folders: [{ id: "folder-1", name: "Watchlist", createdAt: "2026-08-01T00:00:00Z" }],
          savedProducts: [
            { product: productFixture, folderId: null, savedAt: "2026-08-01T00:00:00Z" },
          ],
          unavailableCount: 1,
        }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<PersonalLibraryPanel />, "/store");

  await userEvent.click(screen.getByRole("button", { name: "Open my library" }));
  await screen.findByRole("link", { name: /Regional Stability Brief/ });
  await userEvent.click(screen.getByRole("button", { name: "Unfiled" }));
  await userEvent.click(screen.getByRole("button", { name: "All saved" }));
  await userEvent.click(screen.getByRole("button", { name: "Watchlist" }));
  expect(screen.getByText(/No reports in this folder yet/)).toBeVisible();
  expect(screen.getByText("1 saved report is no longer available to you.")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Delete Watchlist folder" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/store/library/folders/folder-1",
      expect.objectContaining({
        headers: { "X-CSRF-Token": "test-csrf-token" },
        method: "DELETE",
      }),
    ),
  );
  await userEvent.click(screen.getByRole("button", { name: "Close my library" }));
  expect(screen.queryByRole("button", { name: "Unfiled" })).not.toBeInTheDocument();
});
