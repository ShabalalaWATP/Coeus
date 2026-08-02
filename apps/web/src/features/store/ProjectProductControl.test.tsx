import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProjectProductControl } from "./ProjectProductControl";
import { projectDetail, projectSummary } from "./store-organisation.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());

test("adds an authorised product to a selected active project", async () => {
  const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(init?.method === "PUT" ? projectDetail : [projectSummary]),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<ProjectProductControl productId="product/1" />, "/store/products/product-1");

  await userEvent.click(screen.getByRole("button", { name: "Add to project" }));
  await screen.findByRole("option", { name: "Eastern Europe watch" });
  await userEvent.selectOptions(screen.getByRole("combobox"), "project-1");
  await userEvent.click(screen.getByRole("button", { name: "Add" }));

  await waitFor(() => expect(screen.getByRole("button", { name: "Added" })).toBeVisible());
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/projects/project-1/products/product%2F1",
    expect.objectContaining({
      headers: { "X-CSRF-Token": "test-csrf-token" },
      method: "PUT",
    }),
  );
});

test("hides the control when the user has no active projects", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([{ ...projectSummary, archived: true }]),
    }),
  );
  renderWithProviders(<ProjectProductControl productId="product-1" />);
  await userEvent.click(screen.getByRole("button", { name: "Add to project" }));
  expect(await screen.findByText("No active projects are available.")).toBeVisible();
});

test("fails closed when projects cannot be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  renderWithProviders(<ProjectProductControl productId="product-1" />);

  await userEvent.click(screen.getByRole("button", { name: "Add to project" }));
  expect(
    await screen.findByText("Projects are unavailable.", {}, { timeout: 5_000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.getByRole("button", { name: "Add to project" })).toBeVisible();
});

test("shows a bounded error when adding to a project fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([projectSummary]) })
    .mockRejectedValueOnce(new Error("offline"));
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<ProjectProductControl productId="product-1" />);

  await userEvent.click(screen.getByRole("button", { name: "Add to project" }));
  await screen.findByRole("option", { name: "Eastern Europe watch" });
  await userEvent.selectOptions(screen.getByRole("combobox"), "project-1");
  await userEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(await screen.findByText("Could not add this product.")).toBeVisible();
});
