import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";

import StoreProjectsPage from "./StoreProjectsPage";
import { projectDetail, projectSummary } from "./store-organisation.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());

function renderPage(path = "/store/projects") {
  return renderWithProviders(
    <Routes>
      <Route path="/store/projects" element={<StoreProjectsPage />} />
      <Route path="/store/projects/:projectId" element={<StoreProjectsPage />} />
    </Routes>,
    path,
  );
}

test("creates a scoped project and opens its workspace", async () => {
  const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(init?.method === "POST" ? projectDetail : []),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderPage();

  await userEvent.click(screen.getByRole("button", { name: "New project" }));
  await userEvent.type(screen.getByLabelText("Project name"), "Eastern Europe watch");
  await userEvent.type(screen.getByLabelText("Purpose"), "Track regional reporting");
  await userEvent.type(screen.getByLabelText("Region"), "Eastern Europe");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/store/projects",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(await screen.findByRole("heading", { name: "Eastern Europe watch" })).toBeVisible();
});

test("shows project evidence, working notes, members and activity", async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.endsWith("/project-1") ? projectDetail : [projectSummary]),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderPage("/store/projects/project-1");

  expect(await screen.findByRole("heading", { name: "Eastern Europe watch" })).toBeVisible();
  expect(screen.getByRole("link", { name: /Regional Stability Brief/ })).toHaveAttribute(
    "href",
    "/store/products/product-regional",
  );
  expect(screen.getAllByText("Sprint 2 Operator")).toHaveLength(2);
  expect(screen.getByText("Project activity")).toBeVisible();
});

test("shows a clear empty project state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) })),
  );
  renderPage();

  expect(await screen.findByText(/No projects yet\./)).toBeVisible();
});
