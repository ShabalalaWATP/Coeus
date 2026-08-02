import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  TicketWorkspace,
  type TicketWorkspaceActions,
  type TicketWorkspacePending,
} from "./TicketWorkspace";
import { requestTicket, rfiResultsFixture } from "./requests-test-data";
import { renderWithProviders } from "../../test/test-utils";

const actions: TicketWorkspaceActions = {
  onAccept: vi.fn(),
  onAddAttachment: vi.fn(),
  onAddCollaborator: vi.fn(),
  onAddInformation: vi.fn(),
  onCancel: vi.fn(),
  onCollectChoice: vi.fn(),
  onNoMatchConsent: vi.fn(),
  onRefineSearch: vi.fn(),
  onReject: vi.fn(),
  onRfiFeedback: vi.fn(),
  onRemoveCollaborator: vi.fn(),
  onRun: vi.fn(),
  onSave: vi.fn(),
  onSend: vi.fn(),
  onSubmit: vi.fn(),
};

const pending: TicketWorkspacePending = {
  accepting: false,
  collaborating: false,
  cancelling: false,
  choosingCollect: false,
  consenting: false,
  feedback: false,
  adding: false,
  attaching: false,
  rejecting: false,
  refining: false,
  running: false,
  saving: false,
  sending: false,
  submitting: false,
};

test("hands focus from conversation to returned RFI products", async () => {
  const ticket = {
    ...requestTicket,
    state: "RFI_MATCH_OFFERED" as const,
    messages: [
      {
        id: "message-1",
        author: "user" as const,
        body: "What changed?",
        createdAt: "2026-07-05T00:00:00Z",
      },
    ],
  };
  renderWithProviders(
    <TicketWorkspace
      actions={actions}
      actionError={null}
      currentUserId="preview-user"
      journeyOpen={false}
      onClearActionError={vi.fn()}
      onJourneyToggle={vi.fn()}
      pending={pending}
      rfiLoading={false}
      rfiResults={rfiResultsFixture}
      ticket={ticket}
    />,
  );

  expect(screen.getByText("Conversation complete")).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: "Conversation with Istari" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Matching product" })).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Show conversation" }));
  expect(screen.getByRole("heading", { name: "Conversation with Istari" })).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Minimise conversation" }));
  expect(screen.getByText("Conversation complete")).toBeVisible();
});

test("does not collapse conversation while product results are loading", () => {
  renderWithProviders(
    <TicketWorkspace
      actions={actions}
      actionError={null}
      currentUserId="preview-user"
      journeyOpen={false}
      onClearActionError={vi.fn()}
      onJourneyToggle={vi.fn()}
      pending={pending}
      rfiLoading
      ticket={{ ...requestTicket, state: "RFI_SEARCHING" }}
    />,
  );

  expect(screen.getByRole("heading", { name: "Conversation with Istari" })).toBeVisible();
  expect(screen.queryByText("Conversation complete")).not.toBeInTheDocument();
});

test("reopens Istari after all products are rejected and requires short feedback", async () => {
  const onRfiFeedback = vi.fn();
  const ticket = {
    ...requestTicket,
    state: "NEW_TASKING_CONSENT" as const,
    messages: [
      ...requestTicket.messages,
      {
        id: "feedback-prompt",
        author: "assistant" as const,
        body: "Thanks for reviewing those products. What was missing?",
        createdAt: "2026-07-05T00:03:00Z",
      },
    ],
    timeline: [
      ...requestTicket.timeline,
      {
        id: "feedback-requested",
        eventType: "rfi_search_feedback_requested",
        body: "Istari asked what was missing.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:03:00Z",
      },
    ],
  };
  renderWithProviders(
    <TicketWorkspace
      actions={{ ...actions, onRfiFeedback }}
      actionError={null}
      currentUserId="preview-user"
      journeyOpen={false}
      onClearActionError={vi.fn()}
      onJourneyToggle={vi.fn()}
      pending={pending}
      rfiLoading={false}
      rfiResults={{
        ...rfiResultsFixture,
        ticketState: "NEW_TASKING_CONSENT",
        offers: rfiResultsFixture.offers.map((offer) => ({
          ...offer,
          rejectionReason: "Too old.",
          status: "rejected" as const,
        })),
      }}
      ticket={ticket}
    />,
  );

  expect(screen.getByRole("heading", { name: "Conversation with Istari" })).toBeVisible();
  expect(screen.queryByText("Conversation complete")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Continue to the JIOC Agent" }),
  ).not.toBeInTheDocument();

  await userEvent.type(screen.getByLabelText("What was missing?"), "Needs newer reporting.");
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  expect(onRfiFeedback).toHaveBeenCalledWith("Needs newer reporting.", expect.any(Function));
});

test("offers refined search, JIOC hand-off or unfulfilled closure after feedback", () => {
  const ticket = {
    ...requestTicket,
    state: "NEW_TASKING_CONSENT" as const,
    timeline: [
      ...requestTicket.timeline,
      {
        id: "feedback-requested",
        eventType: "rfi_search_feedback_requested",
        body: "Istari asked what was missing.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:03:00Z",
      },
      {
        id: "feedback-recorded",
        eventType: "rfi_search_feedback_recorded",
        body: "Needs newer reporting.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:04:00Z",
      },
    ],
  };
  renderWithProviders(
    <TicketWorkspace
      actions={actions}
      actionError={null}
      currentUserId="preview-user"
      journeyOpen={false}
      onClearActionError={vi.fn()}
      onJourneyToggle={vi.fn()}
      pending={pending}
      rfiLoading={false}
      rfiResults={{
        ...rfiResultsFixture,
        ticketState: "NEW_TASKING_CONSENT",
        offers: rfiResultsFixture.offers.map((offer) => ({
          ...offer,
          rejectionReason: "Too old.",
          status: "rejected" as const,
        })),
      }}
      ticket={ticket}
    />,
  );

  expect(screen.getByRole("button", { name: "Refine and search again" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Continue to the JIOC Agent" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Close as unfulfilled" })).toBeVisible();
  expect(screen.getByText(/JIOC Agent will decide whether RFA, collection/)).toBeVisible();
});

test("keeps required feedback available when the results query fails", () => {
  const ticket = {
    ...requestTicket,
    state: "NEW_TASKING_CONSENT" as const,
    timeline: [
      ...requestTicket.timeline,
      {
        id: "feedback-requested",
        eventType: "rfi_search_feedback_requested",
        body: "Istari asked what was missing.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:03:00Z",
      },
    ],
  };
  renderWithProviders(
    <TicketWorkspace
      actions={actions}
      actionError={null}
      currentUserId="preview-user"
      journeyOpen={false}
      onClearActionError={vi.fn()}
      onJourneyToggle={vi.fn()}
      pending={pending}
      rfiError
      rfiLoading={false}
      ticket={ticket}
    />,
  );

  expect(screen.getByLabelText("What was missing?")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Continue to the JIOC Agent" }),
  ).not.toBeInTheDocument();
});

test("does not replay feedback for a second refined search", () => {
  const ticket = {
    ...requestTicket,
    state: "NEW_TASKING_CONSENT" as const,
    timeline: [
      ...requestTicket.timeline,
      {
        id: "feedback-requested",
        eventType: "rfi_search_feedback_requested",
        body: "Istari asked what was missing.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:03:00Z",
      },
      {
        id: "feedback-recorded",
        eventType: "rfi_search_feedback_recorded",
        body: "Needs newer reporting.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:04:00Z",
      },
      {
        id: "refined-search",
        eventType: "rfi_refined_search_started",
        body: "Refined search started.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:05:00Z",
      },
    ],
  };
  renderWithProviders(
    <TicketWorkspace
      actions={actions}
      actionError={null}
      currentUserId="preview-user"
      journeyOpen={false}
      onClearActionError={vi.fn()}
      onJourneyToggle={vi.fn()}
      pending={pending}
      rfiLoading={false}
      ticket={ticket}
    />,
  );

  expect(screen.queryByRole("button", { name: "Refine and search again" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Continue to the JIOC Agent" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Close as unfulfilled" })).toBeVisible();
});

test("allows only refined retry while partial search assurance is unresolved", () => {
  const ticket = {
    ...requestTicket,
    state: "RFI_SEARCH_INCOMPLETE" as const,
    timeline: [
      ...requestTicket.timeline,
      {
        id: "feedback-requested",
        eventType: "rfi_search_feedback_requested",
        body: "Istari asked what was missing.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:03:00Z",
      },
      {
        id: "feedback-recorded",
        eventType: "rfi_search_feedback_recorded",
        body: "Needs newer reporting.",
        actorUserId: "preview-user",
        createdAt: "2026-07-05T00:04:00Z",
      },
    ],
  };
  renderWithProviders(
    <TicketWorkspace
      actions={actions}
      actionError={null}
      currentUserId="preview-user"
      journeyOpen={false}
      onClearActionError={vi.fn()}
      onJourneyToggle={vi.fn()}
      pending={pending}
      rfiLoading={false}
      ticket={ticket}
    />,
  );

  expect(screen.getByRole("button", { name: "Refine and search again" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Retry search" })).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Continue to the JIOC Agent" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Close as unfulfilled" })).not.toBeInTheDocument();
});
