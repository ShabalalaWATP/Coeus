import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

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
  releasedProductIds: [],
  collaborators: [],
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

test("shows the assistant typing indicator while a message is sending", () => {
  render(<ChatPanel isSending onSend={vi.fn()} />);

  expect(screen.getByRole("status")).toHaveTextContent("Istari is thinking");
});

test("opens tickets from the dashboard and shows tagged counts", async () => {
  const onOpen = vi.fn();
  render(
    <RequestDashboard
      canCreate
      onOpen={onOpen}
      tickets={[
        ticket,
        {
          ...ticket,
          id: "ticket-2",
          reference: "TCK-0002",
          collaborators: [
            {
              userId: "colleague-1",
              username: "colleague@example.test",
              displayName: "Customer Colleague",
              access: "viewer",
              addedByUserId: "preview-user",
              createdAt: "2026-07-06T00:00:00Z",
            },
          ],
        },
      ]}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: /TCK-0001/ }));

  expect(onOpen).toHaveBeenCalledWith("ticket-1");
  expect(screen.getByText("1 tagged")).toBeVisible();
});

test("links released products from the dashboard", () => {
  render(
    <MemoryRouter>
      <RequestDashboard
        canCreate
        onOpen={vi.fn()}
        tickets={[
          {
            ...ticket,
            state: "DISSEMINATION_READY",
            releasedProductIds: ["product-9"],
          },
        ]}
      />
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: /View released product/ })).toHaveAttribute(
    "href",
    "/store/products/product-9",
  );
});

test("renders fallback titles and an empty dashboard state", () => {
  const { rerender } = render(
    <RequestDashboard
      canCreate
      onOpen={vi.fn()}
      tickets={[{ ...ticket, intake: { ...ticket.intake, title: null } }]}
    />,
  );

  expect(screen.getByText("Draft request")).toBeVisible();

  rerender(<RequestDashboard canCreate={false} onOpen={vi.fn()} tickets={[]} />);
  expect(screen.getByText("No requests yet")).toBeVisible();
  expect(
    screen.getByText("Requests shared with you appear here once you are tagged."),
  ).toBeVisible();
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
