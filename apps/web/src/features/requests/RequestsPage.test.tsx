import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RequestsPage from "./RequestsPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import type { Ticket } from "../../lib/api-client/tickets";

const baseTicket: Ticket = {
  id: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "preview-user",
  state: "INFO_REQUIRED",
  intake: {
    title: "Baltic Ports Brief",
    description: "Assess mock port activity.",
    operationalQuestion: "What activity needs attention?",
    areaOrRegion: "Baltic ports",
    timePeriodStart: null,
    timePeriodEnd: null,
    priority: null,
    deadline: null,
    requiredOutputFormat: "Briefing note",
    knownContext: null,
    restrictionsOrCaveats: null,
    customerSuccessCriteria: null,
    suggestedProjectName: null,
    suggestedAcgContext: null,
    missingInformation: ["priority", "customer_success_criteria"],
    confidence: 0.71,
  },
  isReadyForSubmission: false,
  suggestedProjectName: null,
  visibleProductMatches: [],
  messages: [
    {
      id: "message-1",
      author: "user",
      body: "Need a Baltic ports brief.",
      createdAt: "2026-07-05T00:00:00Z",
    },
    {
      id: "message-2",
      author: "assistant",
      body: "I need priority and success criteria.",
      createdAt: "2026-07-05T00:00:01Z",
    },
  ],
  attachments: [],
  agentRuns: [],
  timeline: [
    {
      id: "timeline-1",
      eventType: "ticket_created",
      body: "Draft intake started.",
      actorUserId: "preview-user",
      createdAt: "2026-07-05T00:00:00Z",
    },
  ],
  createdAt: "2026-07-05T00:00:00Z",
  updatedAt: "2026-07-05T00:00:01Z",
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("creates a ticket from chat and renders the extracted intake", async () => {
  const createdTicket = { ...baseTicket, messages: baseTicket.messages.slice(0, 2) };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ tickets: [] }) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(createdTicket) });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<RequestsPage />);

  await screen.findByText("No tickets yet");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  await userEvent.type(screen.getByLabelText("Message"), "Need a Baltic ports brief.");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));

  expect(await screen.findByRole("button", { name: /TCK-0001/ })).toBeVisible();
  expect(screen.getByDisplayValue("Baltic Ports Brief")).toBeVisible();
  expect(fetchMock).toHaveBeenLastCalledWith("http://127.0.0.1:8001/api/v1/chat/messages", {
    body: JSON.stringify({ message: "Need a Baltic ports brief." }),
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
    method: "POST",
  });
});

test("saves edited intake before enabling submission", async () => {
  const readyTicket: Ticket = {
    ...baseTicket,
    state: "DRAFT_INTAKE",
    isReadyForSubmission: true,
    intake: {
      ...baseTicket.intake,
      priority: "high",
      customerSuccessCriteria: "Identify watch-team actions.",
      missingInformation: [],
      confidence: 1,
    },
  };
  const submittedTicket: Ticket = {
    ...readyTicket,
    state: "RFI_SEARCHING",
    suggestedProjectName: "Baltic Ports Brief Workspace",
    timeline: [
      ...readyTicket.timeline,
      {
        id: "timeline-2",
        eventType: "search_started",
        body: "Search queued.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:01:00Z",
      },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ tickets: [baseTicket] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(readyTicket) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(submittedTicket) }),
  );

  renderWithProviders(<RequestsPage />);

  const submit = await screen.findByRole("button", { name: "Submit" });
  expect(submit).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Priority"), "high");
  await userEvent.type(screen.getByLabelText("Success criteria"), "Identify watch-team actions.");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));

  expect(await screen.findByText("search started")).toBeVisible();
});

test("adds attachment metadata and later timeline information", async () => {
  const attachedTicket = {
    ...baseTicket,
    attachments: [
      {
        id: "attachment-1",
        name: "prior-tasking.csv",
        description: "Synthetic reference.",
        sourceType: "metadata-only",
        createdAt: "2026-07-05T00:02:00Z",
      },
    ],
  };
  const informationTicket = {
    ...attachedTicket,
    timeline: [
      ...attachedTicket.timeline,
      {
        id: "timeline-3",
        eventType: "information_added",
        body: "Deadline moved earlier.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:03:00Z",
      },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ tickets: [baseTicket] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(attachedTicket) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(informationTicket) }),
  );

  renderWithProviders(<RequestsPage />);

  await screen.findByText("Baltic Ports Brief");
  await userEvent.type(screen.getByLabelText("Name"), "prior-tasking.csv");
  await userEvent.type(screen.getAllByLabelText("Description")[1], "Synthetic reference.");
  await userEvent.click(screen.getByRole("button", { name: "Add metadata" }));
  await userEvent.type(screen.getByLabelText("Additional information"), "Deadline moved earlier.");
  await userEvent.click(screen.getByRole("button", { name: "Add information" }));

  expect(await screen.findByText("Deadline moved earlier.")).toBeVisible();
});
