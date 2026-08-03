import { screen } from "@testing-library/react";

import StoreLibraryPage from "./StoreLibraryPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());

test("opens the private library workspace by default", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ folders: [], savedProducts: [], unavailableCount: 0 }),
    }),
  );
  renderWithProviders(<StoreLibraryPage />, "/store/library");

  expect(screen.getByRole("heading", { name: "My Library" })).toBeVisible();
  expect(await screen.findByText(/No reports in this folder yet/)).toBeVisible();
  // The library is the page here, so it carries no open or close control.
  expect(screen.queryByRole("button", { name: /my library/i })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "All saved" })).toBeVisible();
});
