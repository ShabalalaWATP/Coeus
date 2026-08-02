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
  onReject: vi.fn(),
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
  adding: false,
  attaching: false,
  rejecting: false,
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
