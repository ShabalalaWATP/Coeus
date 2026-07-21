import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AnalystProductSubmissionForm } from "./AnalystProductSubmissionForm";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AnalystTask } from "../../lib/api-client/analyst";
import { renderWithProviders } from "../../test/test-utils";

const task: AnalystTask = {
  ticketId: "ticket-1",
  reference: "TCK-1",
  state: "ANALYST_IN_PROGRESS",
  title: "Synthetic collection request",
  description: null,
  operationalQuestion: "What changed?",
  areaOrRegion: null,
  priority: "routine",
  requiredOutputFormat: "assessment",
  chatSummary: [],
  managerNotes: [],
  assignments: [
    {
      id: "assignment-1",
      analystUserId: "analyst-1",
      assignedByUserId: "manager-1",
      route: "cm",
      createdAt: "2026-07-18T00:00:00Z",
      teamId: "team-1",
      teamName: "Collection team",
    },
  ],
  workPackages: [],
  notes: [],
  linkedProducts: [],
  drafts: [],
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("uses collection defaults and fails safe when ACGs cannot load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable" } }),
    }),
  );

  renderWithProviders(<AnalystProductSubmissionForm disabled onUploaded={vi.fn()} task={task} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Access groups could not be loaded.");
  expect(screen.getByLabelText("Owner team")).toHaveValue("Collection");
  expect(screen.getByLabelText("Area or region")).toHaveValue("Not specified");
  expect(screen.getByLabelText("Product file")).toBeDisabled();
});

test("allows an available ACG to be selected and removed", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          acgs: [
            {
              id: "acg-1",
              code: "ACG-SYNTHETIC",
              name: "Synthetic",
              description: "Synthetic access group",
              ownerUserId: "manager-1",
              isActive: true,
              memberUserIds: ["analyst-1"],
            },
          ],
        }),
    }),
  );

  renderWithProviders(
    <AnalystProductSubmissionForm disabled={false} onUploaded={vi.fn()} task={task} />,
  );
  const checkbox = await screen.findByLabelText("ACG-SYNTHETIC");

  await userEvent.click(checkbox);
  expect(checkbox).toBeChecked();
  await userEvent.click(checkbox);
  expect(checkbox).not.toBeChecked();
});

test("fails visibly if a stale form submits without a selected file", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ acgs: [] }) }),
  );
  renderWithProviders(
    <AnalystProductSubmissionForm disabled={false} onUploaded={vi.fn()} task={task} />,
  );
  const fileInput = screen.getByLabelText("Product file");

  fireEvent.change(fileInput, { target: { files: null } });
  fireEvent.submit(fileInput.closest("form")!);

  expect(
    await screen.findByText("The product could not be uploaded. Check the file and metadata."),
  ).toBeVisible();
});
