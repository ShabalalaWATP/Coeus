import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AnalystWorkbenchPage from "./AnalystWorkbenchPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AnalystTask } from "../../lib/api-client/analyst";
import { renderWithProviders } from "../../test/test-utils";

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
  assignment: {
    id: "assignment-1",
    analystUserId: "analyst-1",
    assignedByUserId: "manager-1",
    route: "rfa",
    createdAt: "2026-07-05T00:00:00Z",
  },
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
  projectId: null,
  status: "draft",
  timePeriodStart: null,
  timePeriodEnd: null,
  geojsonRef: null,
  assets: [],
  matchScore: 1,
  matchReasons: ["visible"],
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

test("works an assigned task through notes, products, draft and QC submission", async () => {
  const withNote = {
    ...baseTask,
    notes: [
      {
        id: "note-1",
        body: "Checked sources.",
        createdByUserId: "analyst-1",
        createdAt: "2026-07-05T00:01:00Z",
      },
    ],
  };
  const withLink = {
    ...withNote,
    linkedProducts: [
      {
        id: "link-1",
        productId: "product-1",
        reference: "PROD-1001",
        title: "Assessment Draft Pack",
        summary: "MOCK DATA ONLY draft pack.",
        createdAt: "2026-07-05T00:02:00Z",
      },
    ],
  };
  const packageComplete = {
    ...withLink,
    workPackages: [{ ...baseTask.workPackages[0], status: "complete" as const }],
  };
  const withDraft = {
    ...packageComplete,
    drafts: [
      {
        id: "draft-1",
        versionNumber: 1,
        title: "Arctic assessment draft",
        summary: "MOCK DATA ONLY draft.",
        productType: "finished_output",
        content: "MOCK DATA ONLY draft content.",
        createdAt: "2026-07-05T00:03:00Z",
        assets: [
          {
            id: "asset-1",
            name: "assessment-draft.pdf",
            assetType: "pdf",
            mimeType: "application/pdf",
            sizeBytes: 512,
            sha256: "e".repeat(64),
          },
        ],
      },
    ],
  };
  const submitted = { ...withDraft, state: "QC_REVIEW" as const };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ tasks: [baseTask] }) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(withNote) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [linkedProduct],
          total: 1,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(withLink) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(packageComplete) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(withDraft) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(submitted) });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AnalystWorkbenchPage />, "/analyst/workbench");

  expect(await screen.findByRole("link", { name: /TCK-0001/ })).toBeVisible();
  await userEvent.type(screen.getByLabelText("Note"), "Checked sources.");
  await userEvent.click(screen.getByRole("button", { name: "Add note" }));
  expect(await screen.findByText("Checked sources.")).toBeVisible();

  await userEvent.type(screen.getByLabelText("Product search"), "assessment");
  await userEvent.click(screen.getByRole("button", { name: "Search products" }));
  await userEvent.click(await screen.findByRole("button", { name: "Assessment Draft Pack" }));
  expect(await screen.findByText(/PROD-1001/)).toBeVisible();

  await userEvent.click(screen.getByLabelText("Review permitted products"));
  await userEvent.type(screen.getByLabelText("Title"), "Arctic assessment draft");
  await userEvent.type(screen.getByLabelText("Summary"), "MOCK DATA ONLY draft.");
  await userEvent.type(screen.getByLabelText("Content"), "MOCK DATA ONLY draft content.");
  await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
  expect(await screen.findByText("v1: Arctic assessment draft")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Submit to QC" }));
  expect(
    await within(screen.getByLabelText("Analyst task detail")).findByText("QC REVIEW"),
  ).toBeVisible();
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/submit-qc",
    { credentials: "include", headers: { "X-CSRF-Token": "test-csrf-token" }, method: "POST" },
  );
});
