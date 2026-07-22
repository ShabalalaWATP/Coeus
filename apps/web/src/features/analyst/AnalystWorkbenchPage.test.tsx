import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import AnalystWorkbenchPage from "./AnalystWorkbenchPage";
import { AppProviders } from "../../app/providers";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AnalystTask } from "../../lib/api-client/analyst";
import { previewSession, renderWithProviders } from "../../test/test-utils";

const baseTask: AnalystTask = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  state: "ANALYST_IN_PROGRESS",
  title: "Arctic Fisheries Assessment",
  description: "Assess mock fisheries activity.",
  operationalQuestion: "What activity needs command attention?",
  areaOrRegion: "Arctic fisheries",
  priority: "high",
  requiredOutputFormat: "assessment report",
  chatSummary: ["Need an Arctic fisheries assessment."],
  managerNotes: ["Approved for analyst assignment."],
  assignments: [
    {
      id: "assignment-1",
      analystUserId: "analyst-1",
      assignedByUserId: "manager-1",
      route: "rfa",
      createdAt: "2026-07-05T00:00:00Z",
      teamName: "Maritime Assessment Cell",
      teamId: "team-1",
    },
  ],
  workPackages: [
    {
      id: "package-1",
      title: "Review permitted products",
      status: "pending",
      sortOrder: 1,
    },
  ],
  notes: [],
  linkedProducts: [],
  drafts: [],
};

const linkedProduct = {
  id: "product-1",
  reference: "PROD-1001",
  title: "Assessment Draft Pack",
  summary: "MOCK DATA ONLY draft pack.",
  description: "Synthetic detail",
  productType: "finished_output",
  sourceType: "synthetic",
  ownerTeam: "RFA",
  areaOrRegion: "Arctic fisheries",
  classificationLevel: 3,
  releasability: ["MOCK"],
  handlingCaveats: ["MOCK DATA ONLY"],
  tags: ["mock"],
  acgIds: ["acg-1"],
  status: "draft",
  timePeriodStart: null,
  timePeriodEnd: null,
  geojsonRef: null,
  assets: [],
  matchScore: 1,
  matchReasons: ["visible"],
};

const visibleAcgs = {
  acgs: [
    {
      id: "acg-1",
      code: "ACG-ALPHA-REGIONAL",
      name: "Alpha Regional",
      description: "Synthetic regional group.",
      ownerUserId: "manager-1",
      isActive: true,
      memberUserIds: ["analyst-1"],
    },
  ],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders an empty analyst workbench", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tasks: [] }),
    }),
  );

  renderWithProviders(<AnalystWorkbenchPage />, "/analyst/workbench");

  expect(await screen.findByText("No assigned tasks.")).toBeVisible();
  expect(screen.getByText("No assigned task selected.")).toBeVisible();
});

test("renders an analyst tasks error state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<AnalystWorkbenchPage />, "/analyst/workbench");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

test("does not show a missing-task notice when a direct task link fails to load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  window.history.pushState({}, "Test page", "/analyst/tasks/ticket-1");
  render(
    <AppProviders initialAuthSession={previewSession}>
      <MemoryRouter initialEntries={["/analyst/tasks/ticket-1"]}>
        <Routes>
          <Route path="/analyst/tasks/:taskId" element={<AnalystWorkbenchPage />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  expect(
    screen.queryByText("The requested task was not found or is no longer assigned to you.", {
      exact: false,
    }),
  ).not.toBeInTheDocument();
});

test("notes when the requested task is not assigned to the analyst", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tasks: [baseTask] }),
    }),
  );

  window.history.pushState({}, "Test page", "/analyst/tasks/ticket-404");
  render(
    <AppProviders initialAuthSession={previewSession}>
      <MemoryRouter initialEntries={["/analyst/tasks/ticket-404"]}>
        <Routes>
          <Route path="/analyst/tasks/:taskId" element={<AnalystWorkbenchPage />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(
    await screen.findByText("The requested task was not found or is no longer assigned to you."),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "Back to your task list" })).toHaveAttribute(
    "href",
    "/analyst/workbench",
  );
  expect(
    within(screen.getByLabelText("Analyst task detail")).getByText("No assigned task selected."),
  ).toBeVisible();
  expect(screen.getAllByText("Arctic Fisheries Assessment")).toHaveLength(1);
});

test("shows analyst mutation failures inline", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/api/v1/analyst/tasks")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tasks: [baseTask] }) });
    }
    if (url.endsWith("/api/v1/acgs")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(visibleAcgs) });
    }
    return Promise.resolve({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({ error: { code: "invalid_state", message: "Task is no longer active." } }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AnalystWorkbenchPage />, "/analyst/workbench");

  await screen.findByRole("link", { name: /TCK-0001/ });
  await userEvent.click(screen.getByLabelText("Review permitted products"));

  expect(await screen.findByText("Task is no longer active.")).toBeVisible();
});

test("shows a retryable analyst product search failure", async () => {
  let searchAttempts = 0;
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/api/v1/analyst/tasks")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tasks: [baseTask] }) });
    }
    if (url.endsWith("/api/v1/acgs")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(visibleAcgs) });
    }
    searchAttempts += 1;
    if (searchAttempts === 1) {
      return Promise.resolve({
        ok: false,
        status: 503,
        json: () =>
          Promise.resolve({ error: { code: "store_unavailable", message: "Store unavailable." } }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [linkedProduct],
          total: 1,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AnalystWorkbenchPage />, "/analyst/workbench");

  expect(await screen.findByRole("link", { name: /TCK-0001/ })).toBeVisible();
  await userEvent.click(screen.getByText(/Linked products/));
  fireEvent.change(screen.getByLabelText("Product search"), { target: { value: "assessment" } });
  await userEvent.click(screen.getByRole("button", { name: "Search products" }));

  expect(await screen.findByText("Product search could not be loaded.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Assessment Draft Pack" })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Retry product search" }));

  expect(await screen.findByRole("button", { name: "Assessment Draft Pack" })).toBeVisible();
});
