import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import JiocOversightPage from "./JiocOversightPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("renders workflow ownership and capacity from the oversight endpoint", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [{ key: "ANALYST_IN_PROGRESS", count: 1 }],
          countsByRoute: [{ key: "rfa", count: 1 }],
          countsByAgentDisposition: [{ key: "auto_applied", count: 1 }],
          teams: [
            {
              teamId: "team-1",
              name: "Assessment Team",
              kind: "rfa",
              activeMembers: 4,
              availableMembers: 2,
              liveTaskCount: 1,
            },
          ],
          analysts: [
            {
              userId: "analyst-1",
              displayName: "Assessment Analyst",
              teamIds: ["team-1"],
              liveTaskCount: 1,
            },
          ],
          tasks: [
            {
              ticketId: "ticket-1",
              reference: "TCK-0001",
              state: "ANALYST_IN_PROGRESS",
              route: "rfa",
              teamId: "team-1",
              teamName: "Assessment Team",
              analystCount: 2,
              workPackageCount: 3,
              completedWorkPackageCount: 1,
              agentDisposition: "auto_applied",
              agentRoute: "rfa",
              agentRationaleCodes: ["existing_information_assessment"],
              agentPolicyVersion: "jioc-routing-policy-v2",
              agentConfidence: 0.76,
              criticVerdict: "challenges",
              criticOutcome: "provider_succeeded",
              criticChallengeCount: 2,
              criticMissingEvidenceCount: 1,
            },
          ],
        }),
    }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByRole("heading", { name: "Area teams" })).toBeVisible();
  expect(screen.getByText("TCK-0001")).toBeVisible();
  expect(screen.getByText("Assessment Analyst")).toBeVisible();
  expect(screen.getByText(/1 of 3 packages/)).toBeVisible();
  expect(screen.getByText("existing information assessment")).toBeVisible();
  expect(screen.getByText("0.76")).toBeVisible();
  const critic = screen.getByLabelText("Routing critic evidence for TCK-0001");
  expect(critic).toHaveTextContent("provider succeeded");
  expect(critic).toHaveTextContent("Challenges2");
  expect(critic).toHaveTextContent("Missing evidence1");
});

test("offers recovery when oversight cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable" } }),
    }),
  );
  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByRole("button", { name: "Retry" })).toBeVisible();
});

test("shows honest empty workload states", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [],
          countsByRoute: [],
          countsByAgentDisposition: [],
          teams: [],
          analysts: [],
          tasks: [],
        }),
    }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByText("No tasks match this view.")).toBeVisible();
  expect(screen.getByText("No analysts are allocated.")).toBeVisible();
});

test("labels unrouted work and plural analyst workloads", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [],
          countsByRoute: [],
          countsByAgentDisposition: [],
          teams: [],
          analysts: [
            {
              userId: "analyst-1",
              displayName: "Shared Analyst",
              teamIds: ["team-1", "team-2"],
              liveTaskCount: 2,
            },
          ],
          tasks: [
            {
              ticketId: "ticket-1",
              reference: "TCK-UNROUTED",
              state: "JIOC_REVIEW",
              route: null,
              teamId: null,
              teamName: null,
              analystCount: 0,
              workPackageCount: 0,
              completedWorkPackageCount: 0,
            },
          ],
        }),
    }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByRole("link", { name: "TCK-UNROUTED" })).toHaveAttribute(
    "href",
    "/jioc/queue?ticket=ticket-1",
  );
  expect(screen.getByText("Unassigned")).toBeVisible();
  expect(screen.getByText("2 live tasks")).toBeVisible();
  expect(screen.getByText("2 teams")).toBeVisible();
});

test("lets the manager hold work or send it to human review with a reason", async () => {
  const oversight = {
    countsByState: [],
    countsByRoute: [],
    countsByAgentDisposition: [{ key: "manager_review", count: 1 }],
    teams: [],
    analysts: [],
    tasks: [
      {
        ticketId: "ticket-action",
        reference: "TCK-ACTION",
        state: "JIOC_ROUTING_PENDING",
        updatedAt: "2026-07-23T09:00:00Z",
        route: "cm",
        teamId: null,
        teamName: null,
        analystCount: 0,
        workPackageCount: 0,
        completedWorkPackageCount: 0,
        agentDisposition: "manager_review",
        agentConfidence: 0.42,
        agentRoute: "rfa",
        agentRationaleCodes: ["risk_review_required"],
        agentPolicyVersion: "jioc-routing-policy-v2",
      },
    ],
  };
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.endsWith("/oversight") ? oversight : {}),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByText("Human JIOC review")).toBeVisible();
  expect(screen.getByText("CM")).toBeVisible();
  expect(screen.getByText("RFA")).toBeVisible();
  expect(screen.getByText("risk review required")).toBeVisible();
  expect(screen.getByText("0.42")).toBeVisible();
  expect(screen.getByText("Not a probability")).toBeVisible();
  expect(screen.queryByText("42%")).not.toBeInTheDocument();
  const reason = screen.getByRole("textbox", { name: /Intervention reason/ });
  const hold = screen.getByRole("button", { name: "Hold" });
  expect(hold).toBeDisabled();
  await userEvent.type(reason, "Manager check");
  await userEvent.click(hold);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/routing/ticket-action/intervene"),
      expect.objectContaining({
        body: JSON.stringify({
          action: "hold",
          reason: "Manager check",
          expectedUpdatedAt: "2026-07-23T09:00:00Z",
        }),
        method: "POST",
      }),
    ),
  );
  await userEvent.click(screen.getByRole("button", { name: "Send to review" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/routing/ticket-action/intervene"),
      expect.objectContaining({
        body: JSON.stringify({
          action: "send_to_review",
          reason: "Manager check",
          expectedUpdatedAt: "2026-07-23T09:00:00Z",
        }),
      }),
    ),
  );
});

test("lets the manager resume held work and suppresses actions for terminal work", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [],
          countsByRoute: [],
          countsByAgentDisposition: [],
          teams: [],
          analysts: [],
          tasks: [
            {
              ticketId: "ticket-held",
              reference: "TCK-HELD",
              state: "JIOC_INTERVENTION_HOLD",
              route: "rfa",
              teamId: null,
              teamName: null,
              analystCount: 0,
              workPackageCount: 0,
              completedWorkPackageCount: 0,
            },
            {
              ticketId: "ticket-done",
              reference: "TCK-DONE",
              state: "CLOSED_DELIVERED",
              route: "rfa",
              teamId: null,
              teamName: null,
              analystCount: 1,
              workPackageCount: 1,
              completedWorkPackageCount: 1,
            },
          ],
        }),
    }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  await userEvent.selectOptions(
    await screen.findByRole("combobox", { name: "Filter oversight tasks" }),
    "all",
  );
  expect(await screen.findByText("No action available")).toBeVisible();
  await userEvent.type(
    screen.getByRole("textbox", { name: /Intervention reason/ }),
    "Checks complete",
  );
  await userEvent.click(screen.getByRole("button", { name: "Resume" }));
});

test("shows missing Agent rationale and reports a rejected intervention", async () => {
  const task = {
    ticketId: "ticket-error",
    reference: "TCK-ERROR",
    state: "JIOC_ROUTING_PENDING",
    route: null,
    teamId: null,
    teamName: null,
    analystCount: 0,
    workPackageCount: 0,
    completedWorkPackageCount: 0,
    agentDisposition: "manager_review",
    agentRoute: null,
    agentRationaleCodes: [],
    agentPolicyVersion: null,
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            countsByState: [],
            countsByRoute: [],
            countsByAgentDisposition: [],
            teams: [],
            analysts: [],
            tasks: [task],
          }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: () => Promise.resolve({ error: { code: "ticket_changed", message: "Changed" } }),
      }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByText("None recorded")).toBeVisible();
  expect(screen.getAllByText("Unknown")).toHaveLength(2);
  await userEvent.type(
    screen.getByRole("textbox", { name: /Intervention reason/ }),
    "Review changed work",
  );
  await userEvent.click(screen.getByRole("button", { name: "Hold" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The intervention could not be applied",
  );
});
