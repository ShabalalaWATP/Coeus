import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatPanel } from "./ChatPanel";
import { IntakePanel } from "./IntakePanel";
import { RequestDashboard } from "./RequestDashboard";
import { TimelinePanel } from "./TimelinePanel";
import { ticketMetrics, upsertTicket } from "./ticket-collection";
import type { Ticket } from "../../lib/api-client/tickets";

const ticket: Ticket = {
  id: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "preview-user",
  state: "DRAFT_INTAKE",
  intake: {
    title: "Regional Brief",
    description: "Assess activity.",
    operationalQuestion: "What changed?",
    areaOrRegion: "Baltic ports",
    timePeriodStart: null,
    timePeriodEnd: null,
    priority: "high",
    deadline: null,
    requiredOutputFormat: "Briefing note",
    knownContext: null,
    restrictionsOrCaveats: null,
    customerSuccessCriteria: "Support watch teams.",
    suggestedProjectName: null,
    suggestedAcgContext: null,
    missingInformation: [],
    confidence: 1,
  },
  isReadyForSubmission: true,
  suggestedProjectName: null,
  visibleProductMatches: [],
  messages: [],
  attachments: [],
  agentRuns: [],
  timeline: [],
  createdAt: "2026-07-05T00:00:00Z",
  updatedAt: "2026-07-05T00:00:00Z",
};

test("upserts existing and new tickets", () => {
  const updated = { ...ticket, reference: "TCK-0002" };
  const secondTicket = { ...ticket, id: "ticket-2", reference: "TCK-0003" };

  expect(upsertTicket(undefined, ticket)).toEqual([ticket]);
  expect(upsertTicket([ticket], updated)).toEqual([updated]);
  expect(upsertTicket([ticket], { ...ticket, id: "ticket-2" })).toHaveLength(2);
  expect(upsertTicket([ticket, secondTicket], { ...secondTicket, reference: "TCK-0004" })).toEqual([
    ticket,
    { ...secondTicket, reference: "TCK-0004" },
  ]);
});

test("calculates ticket metrics for every visible state", () => {
  expect(
    ticketMetrics([
      ticket,
      { ...ticket, id: "ticket-2", state: "INFO_REQUIRED", isReadyForSubmission: false },
      { ...ticket, id: "ticket-3", state: "RFI_SEARCHING" },
    ]),
  ).toEqual({ total: 3, draft: 2, searching: 1, ready: 2 });
});

test("ignores short chat messages", async () => {
  const onSend = vi.fn();
  render(<ChatPanel isSending={false} onSend={onSend} />);

  await userEvent.type(screen.getByLabelText("Message"), "no");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));

  expect(onSend).not.toHaveBeenCalled();
  expect(screen.getByText("No chat transcript")).toBeVisible();
});

test("renders selected and unselected ticket rows", async () => {
  const onSelect = vi.fn();
  render(
    <RequestDashboard
      onSelect={onSelect}
      selectedTicketId="ticket-2"
      tickets={[ticket, { ...ticket, id: "ticket-2", reference: "TCK-0002" }]}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: /TCK-0001/ }));

  expect(onSelect).toHaveBeenCalledWith("ticket-1");
});

test("renders fallback titles for draft tickets", () => {
  render(
    <RequestDashboard
      onSelect={vi.fn()}
      selectedTicketId="ticket-1"
      tickets={[{ ...ticket, intake: { ...ticket.intake, title: null } }]}
    />,
  );

  expect(screen.getByText("Draft intake")).toBeVisible();
});

test("shows empty intake state without attachment controls", () => {
  const onAddAttachment = vi.fn();
  render(
    <IntakePanel
      isSaving={false}
      isSubmitting={false}
      onAddAttachment={onAddAttachment}
      onSave={vi.fn()}
      onSubmit={vi.fn()}
    />,
  );

  expect(screen.getByText("No ticket selected")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Add metadata" })).not.toBeInTheDocument();
});

test("renders blank editable fields when extraction has no value", () => {
  render(
    <IntakePanel
      isSaving={false}
      isSubmitting={false}
      onAddAttachment={vi.fn()}
      onSave={vi.fn()}
      onSubmit={vi.fn()}
      ticket={{
        ...ticket,
        intake: {
          ...ticket.intake,
          title: null,
          description: null,
          operationalQuestion: null,
          areaOrRegion: null,
          priority: null,
          requiredOutputFormat: null,
          customerSuccessCriteria: null,
        },
      }}
    />,
  );

  expect(screen.getByLabelText("Title")).toHaveValue("");
  expect(screen.getAllByLabelText("Description")[0]).toHaveValue("");
  expect(screen.getByText("None")).toBeVisible();
});

test("does not add blank timeline information", async () => {
  const onAddInformation = vi.fn();
  render(<TimelinePanel isAdding={false} onAddInformation={onAddInformation} ticket={ticket} />);

  await userEvent.type(screen.getByLabelText("Additional information"), "no");
  await userEvent.click(screen.getByRole("button", { name: "Add information" }));

  expect(onAddInformation).not.toHaveBeenCalled();
  expect(screen.getByText("No timeline events")).toBeVisible();
});
