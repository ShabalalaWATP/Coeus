import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";

import ProjectWorkspacePage from "./ProjectWorkspacePage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const project = {
  id: "project-northstar",
  reference: "PRJ-NORTHSTAR",
  name: "Northstar RFI Workspace",
  summary: "Workspace summary",
  requesterUserId: "user-customer",
  acgIds: ["acg-alpha"],
  ticketIds: ["ticket-alpha"],
  members: [{ userId: "user-customer", role: "Requester" }],
  milestones: [{ id: "milestone-one", title: "Discovery", status: "Open" }],
  planItems: [
    {
      id: "plan-one",
      title: "Validate requirement and access groups",
      ownerRole: "RFA Manager",
      status: "Open",
    },
  ],
  visibleProducts: [
    {
      id: "product-alpha",
      title: "Regional Stability Brief",
      summary: "Regional product",
      productType: "Assessment",
      status: "published",
      classificationLevel: 2,
      handlingCaveats: [],
      acgIds: ["acg-alpha"],
      ownerTeam: "RFA",
    },
  ],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders a visible project workspace with filtered products", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ projects: [project] }) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          allowed: true,
          reason: "Access granted",
          checks: [{ name: "acg_membership", passed: true, reason: "Shared ACG" }],
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProjectWorkspacePage />, "/projects/project-northstar");

  expect(await screen.findByRole("heading", { name: "Northstar RFI Workspace" })).toBeVisible();
  expect(screen.getByText("Regional Stability Brief")).toBeVisible();
  expect(screen.getByRole("link", { name: "Plan" })).toHaveAttribute(
    "href",
    "/projects/project-northstar/plan",
  );
  expect(screen.getByRole("link", { name: /Regional Stability Brief/ })).toHaveAttribute(
    "href",
    "/store/products/product-alpha",
  );
  expect(await screen.findByRole("heading", { name: "Access Diagnostics" })).toBeVisible();
  expect(screen.getByText("Shared ACG")).toBeVisible();
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/store/products/product-alpha/access-diagnostics",
    {
      body: JSON.stringify({ userId: "preview-user" }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    },
  );
});

test("lists the user's projects as a picker with the active project marked", async () => {
  const secondProject = {
    ...project,
    id: "project-aurora",
    reference: "PRJ-AURORA",
    name: "Aurora Collection Workspace",
    visibleProducts: [],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ projects: [project, secondProject] }),
    }),
  );

  renderWithProviders(<ProjectWorkspacePage />, "/projects");

  const picker = await screen.findByRole("navigation", { name: "Your projects" });
  const activeLink = screen.getByRole("link", { name: /Northstar RFI Workspace/ });
  expect(activeLink).toHaveAttribute("href", "/projects/project-northstar");
  expect(activeLink).toHaveAttribute("aria-current", "page");
  const otherLink = screen.getByRole("link", { name: /Aurora Collection Workspace/ });
  expect(otherLink).toHaveAttribute("href", "/projects/project-aurora");
  expect(otherLink).not.toHaveAttribute("aria-current");
  expect(picker).toBeVisible();
});

test("renders an empty state when no projects are visible", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ projects: [] }) }),
  );

  renderWithProviders(<ProjectWorkspacePage />, "/projects");

  expect(await screen.findByText("No visible projects")).toBeVisible();
});

test("does not fall back to another project when a requested project is not visible", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ projects: [project] }) }),
  );

  renderWithProviders(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectWorkspacePage />} />
    </Routes>,
    "/projects/project-missing",
  );

  expect(await screen.findByText("Project not found")).toBeVisible();
  expect(
    screen.getByText("This project is not visible to your account or no longer exists."),
  ).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: "Northstar RFI Workspace" }),
  ).not.toBeInTheDocument();
});

test("renders a projects error state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<ProjectWorkspacePage />, "/projects");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

test("supports focused project plan route rendering", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ projects: [project] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ allowed: true, reason: "Access granted", checks: [] }),
      }),
  );

  renderWithProviders(<ProjectWorkspacePage view="plan" />, "/projects/project-northstar/plan");

  expect(await screen.findByText("Validate requirement and access groups")).toBeVisible();
  expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
    "href",
    "/projects/project-northstar",
  );
  expect(screen.queryByRole("heading", { name: "Members" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Products" })).not.toBeInTheDocument();
});
