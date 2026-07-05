import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatPanel } from "./ChatPanel";
import { IntakePanel } from "./IntakePanel";
import { ProductOffersPanel } from "./ProductOffersPanel";
import { RequestDashboard } from "./RequestDashboard";
import { TimelinePanel } from "./TimelinePanel";
import { ticketMetrics, upsertTicket } from "./ticket-collection";
import type { RfiSearchResults } from "../../lib/api-client/rfi-search";
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

const rfiResults: RfiSearchResults = {
  ticketId: "ticket-1",
  ticketState: "RFI_MATCH_OFFERED",
  metrics: {
    runId: "run-1",
    query: "Regional Stability Brief Baltic ports assessment report",
    candidateCount: 1,
    offeredCount: 1,
    rejectedCount: 0,
    acceptedProductId: null,
    createdAt: "2026-07-05T00:01:00Z",
  },
  offers: [
    {
      productId: "product-1",
      title: "Regional Stability Brief",
      summary: "MOCK DATA ONLY assessment summary.",
      productType: "assessment_report",
      matchScore: 0.86,
      matchReasons: ["full-text:regional", "metadata:region"],
      classificationLevel: 2,
      releasability: ["MOCK"],
      region: "Baltic ports",
      timePeriodStart: null,
      timePeriodEnd: null,
      assetTypes: ["pdf"],
      offerableToUser: true,
      status: "offered",
      rejectionReason: null,
    },
  ],
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
      { ...ticket, id: "ticket-4", state: "RFI_MATCH_OFFERED" },
    ]),
  ).toEqual({ total: 4, draft: 2, searching: 2, ready: 3 });
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

test("runs RFI search from the product offer panel", async () => {
  const onRun = vi.fn();
  render(
    <ProductOffersPanel
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onRun={onRun}
      ticket={{ ...ticket, state: "RFI_SEARCHING" }}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "Run search" }));

  expect(onRun).toHaveBeenCalledTimes(1);
  expect(screen.getByText("No product offers")).toBeVisible();
});

test("accepts and rejects RFI product offers", async () => {
  const onAccept = vi.fn();
  const onReject = vi.fn();
  render(
    <ProductOffersPanel
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={onAccept}
      onReject={onReject}
      onRun={vi.fn()}
      results={rfiResults}
      ticket={{ ...ticket, state: "RFI_MATCH_OFFERED" }}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "Accept" }));
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Too old.");
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));

  expect(screen.getByText("86%")).toBeVisible();
  expect(onAccept).toHaveBeenCalledWith("product-1");
  expect(onReject).toHaveBeenCalledWith("product-1", "Too old.");
});

test("does not render RFI metrics when metrics are unavailable", () => {
  render(
    <ProductOffersPanel
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onRun={vi.fn()}
      results={{ ...rfiResults, metrics: null, offers: [] }}
      ticket={{ ...ticket, state: "ROUTE_ASSESSMENT" }}
    />,
  );

  expect(screen.queryByLabelText("RFI search metrics")).not.toBeInTheDocument();
});
