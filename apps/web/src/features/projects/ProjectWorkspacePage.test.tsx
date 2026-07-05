import { screen } from "@testing-library/react";

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
  vi.stubGlobal(
    "fetch",
    vi
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
      }),
  );

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
