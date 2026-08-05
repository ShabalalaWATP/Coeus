import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import { AssignmentRecommendationPanel } from "./AssignmentRecommendationPanel";

const preview = {
  recommendationId: "recommendation-1",
  estimateId: "estimate-1",
  estimateVersion: 3,
  holdId: "hold-1",
  previewHash: "a".repeat(64),
  expiresAt: "2026-08-04T12:30:00Z",
  candidates: [
    {
      unitId: "team-1",
      analystUserId: "analyst-1",
      displayName: "Morgan Reid",
      rank: 1,
      assignableMinutes: 960,
      activeWip: 1,
      explanationCodes: ["capacity_available"],
    },
    {
      unitId: "team-1",
      analystUserId: "analyst-2",
      displayName: "Avery Shah",
      rank: 2,
      assignableMinutes: 840,
      activeWip: 2,
      explanationCodes: ["capacity_available"],
    },
  ],
  exclusionCounts: { capacity_unavailable: 1 },
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("previews and accepts the recommended analyst as a human manager", async () => {
  const onAssigned = vi.fn();
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.endsWith("/preview") ? preview : { ticketId: "ticket-1" }),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <AssignmentRecommendationPanel
      csrfToken="csrf"
      onAssigned={onAssigned}
      teamId="team-1"
      ticketId="ticket-1"
    />,
  );

  await userEvent.click(screen.getByText("Get capacity-aware advice"));
  await userEvent.type(screen.getByLabelText("Required capability codes"), "RFA-REGIONAL");
  await userEvent.click(screen.getByRole("button", { name: "Review recommendation" }));
  expect(await screen.findByLabelText(/Morgan Reid \(recommended\)/)).toBeChecked();
  await userEvent.click(screen.getByRole("button", { name: "Accept and assign" }));

  await waitFor(() => expect(onAssigned).toHaveBeenCalledWith({ ticketId: "ticket-1" }));
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/assignment-recommendations/accept",
    expect.objectContaining({
      body: JSON.stringify({
        recommendationId: "recommendation-1",
        previewHash: "a".repeat(64),
        selectedUnitId: "team-1",
        selectedAnalystUserId: "analyst-1",
        overrideReason: "",
        workPackages: [],
      }),
    }),
  );
});

test("requires and sends a reason for a soft ranking override", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    void init;
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.endsWith("/preview") ? preview : { ticketId: "ticket-1" }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <AssignmentRecommendationPanel
      csrfToken="csrf"
      onAssigned={vi.fn()}
      teamId="team-1"
      ticketId="ticket-1"
    />,
  );
  await userEvent.click(screen.getByText("Get capacity-aware advice"));
  await userEvent.type(screen.getByLabelText("Required capability codes"), "RFA-REGIONAL");
  await userEvent.click(screen.getByRole("button", { name: "Review recommendation" }));
  await userEvent.click(await screen.findByLabelText(/Avery Shah/));
  const accept = screen.getByRole("button", { name: "Accept and assign" });
  expect(accept).toBeDisabled();
  await userEvent.type(
    screen.getByLabelText("Reason for choosing another eligible analyst"),
    "Related regional experience.",
  );
  await userEvent.click(accept);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const acceptanceBody = fetchMock.mock.calls[1]?.[1]?.body;
  expect(typeof acceptanceBody).toBe("string");
  expect(JSON.parse(acceptanceBody as string)).toMatchObject({
    selectedAnalystUserId: "analyst-2",
    overrideReason: "Related regional experience.",
  });
});

test("shows a plain-language unavailable state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({
          error: {
            code: "assignment_recommendation_unavailable",
            message: "Unavailable.",
          },
        }),
    }),
  );
  renderWithProviders(
    <AssignmentRecommendationPanel
      csrfToken="csrf"
      onAssigned={vi.fn()}
      teamId="team-1"
      ticketId="ticket-1"
    />,
  );
  await userEvent.click(screen.getByText("Get capacity-aware advice"));
  await userEvent.type(screen.getByLabelText("Required capability codes"), "RFA-REGIONAL");
  await userEvent.click(screen.getByRole("button", { name: "Review recommendation" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No safe recommendation is available for this demand.",
  );
});
