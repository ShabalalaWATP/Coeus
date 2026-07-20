import { fireEvent, screen, within } from "@testing-library/react";
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
    { id: "package-1", title: "Review permitted products", status: "pending", sortOrder: 1 },
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

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("works an assigned task through notes, products, upload and QC submission", async () => {
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
        description: "MOCK DATA ONLY draft description.",
        sourceType: "analyst_submission",
        ownerTeam: "RFA",
        areaOrRegion: "Arctic fisheries",
        classificationLevel: 0,
        releasability: ["MOCK"],
        handlingCaveats: ["MOCK DATA ONLY"],
        tags: ["mock"],
        acgIds: ["acg-1"],
        manifestHash: "f".repeat(64),
        createdAt: "2026-07-05T00:03:00Z",
        assets: [
          {
            id: "asset-1",
            name: "assessment-draft.pdf",
            assetType: "pdf",
            mimeType: "application/pdf",
            sizeBytes: 512,
            sha256: "e".repeat(64),
            detectedMimeType: "application/pdf",
            previewKind: "pdf" as const,
            processingStatus: "ready",
            previewAvailable: true,
          },
        ],
      },
    ],
  };
  const submitted = { ...withDraft, state: "MANAGER_APPROVAL" as const };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith("/api/v1/analyst/tasks")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tasks: [baseTask] }) });
    }
    if (url.endsWith("/api/v1/acgs")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(visibleAcgs) });
    }
    if (url.includes("/notes")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(withNote) });
    }
    if (url.includes("/store/products")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            products: [linkedProduct],
            total: 1,
            facets: { productTypes: [], regions: [], tags: [] },
          }),
      });
    }
    if (url.endsWith("/products") && init?.method === "POST") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(withLink) });
    }
    if (url.includes("/work-packages/")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(packageComplete) });
    }
    if (url.includes("/submissions/upload")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(withDraft) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(submitted) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AnalystWorkbenchPage />, "/analyst/workbench");
  expect(await screen.findByRole("link", { name: /TCK-0001/ })).toBeVisible();
  await userEvent.click(screen.getByText(/Working notes/));
  fireEvent.change(screen.getByLabelText("Note"), { target: { value: "Checked sources." } });
  await userEvent.click(screen.getByRole("button", { name: "Add note" }));
  expect(await screen.findByText("Checked sources.")).toBeVisible();

  await userEvent.click(screen.getByText(/Linked products/));
  fireEvent.change(screen.getByLabelText("Product search"), { target: { value: "assessment" } });
  await userEvent.click(screen.getByRole("button", { name: "Search products" }));
  await userEvent.click(await screen.findByRole("button", { name: "Assessment Draft Pack" }));
  expect(await screen.findByText(/PROD-1001/)).toBeVisible();

  await userEvent.click(screen.getByLabelText("Review permitted products"));
  fireEvent.change(screen.getByLabelText("Title"), {
    target: { value: "Arctic assessment draft" },
  });
  fireEvent.change(screen.getByLabelText("Summary"), {
    target: { value: "MOCK DATA ONLY draft." },
  });
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: "MOCK DATA ONLY draft description." },
  });
  await userEvent.click(screen.getByLabelText("ACG-ALPHA-REGIONAL"));
  await userEvent.upload(
    screen.getByLabelText("Product file"),
    new File(["%PDF-1.4 synthetic"], "assessment-draft.pdf", { type: "application/pdf" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Upload product version" }));
  expect(await screen.findByText(/Version 1: Arctic assessment draft/)).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Submit for manager approval" }));
  expect(
    await within(screen.getByLabelText("Analyst task detail")).findByText("Manager approval"),
  ).toBeVisible();
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/submit",
    { credentials: "include", headers: { "X-CSRF-Token": "test-csrf-token" }, method: "POST" },
  );
});
