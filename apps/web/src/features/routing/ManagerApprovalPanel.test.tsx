import { screen, waitFor } from "@testing-library/react";

import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import { ManagerApprovalPanel } from "./ManagerApprovalPanel";
import { ManagerWorkReview } from "./ManagerWorkReview";

const submittedWork = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  state: "MANAGER_APPROVAL",
  title: "Harbour assessment",
  description: "Assess harbour activity.",
  operationalQuestion: "What changed?",
  areaOrRegion: "Baltic",
  priority: "urgent",
  requiredOutputFormat: "assessment report",
  chatSummary: [],
  managerNotes: [],
  assignments: [{ id: "a1", analystUserId: "u1", assignedByUserId: "m1" }],
  workPackages: [{ id: "w1", title: "Review sources", status: "complete", sortOrder: 1 }],
  notes: [{ id: "n1", body: "Validated the source trace.", createdAt: "2026-07-10" }],
  linkedProducts: [
    {
      id: "l1",
      productId: "p1",
      reference: "PRD-0001",
      title: "Harbour baseline",
      summary: "Baseline",
      createdAt: "2026-07-10",
    },
  ],
  drafts: [
    {
      id: "d1",
      versionNumber: 2,
      title: "Harbour activity assessment",
      summary: "Activity increased.",
      productType: "assessment_report",
      content: "The reviewed evidence indicates increased activity.",
      createdAt: "2026-07-10",
      assets: [],
    },
  ],
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("locks the decision until submitted work is loaded and then shows it", async () => {
  let resolveWork: ((value: Response) => void) | undefined;
  const fetchMock = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        resolveWork = resolve;
      }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <ManagerApprovalPanel csrfToken="csrf" onDecided={vi.fn()} route="rfa" ticketId="ticket-1" />,
    "/rfa/queue",
  );

  expect(screen.getByRole("button", { name: "Approve and send to QC" })).toBeDisabled();
  resolveWork?.({ ok: true, json: () => Promise.resolve(submittedWork) } as Response);

  expect(await screen.findByText("Harbour activity assessment")).toBeVisible();
  expect(screen.getByText("The reviewed evidence indicates increased activity.")).toBeVisible();
  expect(screen.getByText("Review sources")).toBeVisible();
  expect(screen.getByRole("button", { name: "Approve and send to QC" })).toBeEnabled();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
});

test("keeps decisions locked and offers retry when work cannot load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })),
  );
  renderWithProviders(
    <ManagerApprovalPanel csrfToken="csrf" onDecided={vi.fn()} route="rfa" ticketId="ticket-1" />,
  );

  await waitFor(
    () => expect(screen.getByRole("alert")).toHaveTextContent("Decisions remain locked"),
    { timeout: 3_000 },
  );
  expect(screen.getByRole("button", { name: "Approve and send to QC" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
  expect(screen.getByLabelText("Rework reason")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Return for rework" })).toBeDisabled();
});

test("explains when submitted work has no reviewable draft or supporting context", () => {
  renderWithProviders(
    <ManagerWorkReview
      task={
        {
          ...submittedWork,
          drafts: [],
          linkedProducts: [],
          notes: [],
          workPackages: [
            { id: "pending", title: "Pending review", status: "pending", sortOrder: 1 },
          ],
        } as never
      }
    />,
  );

  expect(screen.getByText("No draft submitted")).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent("Approval is unavailable");
  expect(screen.queryByText(/Working notes/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Supporting products/)).not.toBeInTheDocument();
  expect(screen.getByText("Pending")).toBeVisible();
});
