import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatPanel } from "./ChatPanel";
import { IntakePanel } from "./IntakePanel";
import { requestTicket as ticket } from "./requests-test-data";
import { TimelinePanel } from "./TimelinePanel";
import { ticketMetrics, upsertTicket } from "./ticket-collection";

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

test("disables sending short chat messages and shows a hint", async () => {
  const onSend = vi.fn();
  render(<ChatPanel isSending={false} onSend={onSend} />);

  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Message"), "no");

  expect(screen.getByText("Messages need at least 3 characters.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  expect(onSend).not.toHaveBeenCalled();
  expect(screen.getByText("No chat transcript")).toBeVisible();

  await userEvent.type(screen.getByLabelText("Message"), "w a brief");
  expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(onSend).toHaveBeenCalledWith("now a brief");
});

test("shows the assistant typing indicator while a message is sending", () => {
  render(<ChatPanel isSending onSend={vi.fn()} />);

  expect(screen.getByRole("status")).toHaveTextContent("Istari is thinking");
});

test("surfaces manager clarification questions in the chat", () => {
  render(
    <ChatPanel
      isSending={false}
      onSend={vi.fn()}
      ticket={{
        ...ticket,
        state: "INFO_REQUIRED",
        clarificationRequests: [
          {
            id: "clarification-1",
            route: "rfa",
            reason: "Scope needs tightening.",
            questions: ["Which region matters most?", "What deadline should be used?"],
            createdAt: "2026-07-06T00:00:00Z",
          },
        ],
      }}
    />,
  );

  expect(
    screen.getByText("Manager clarification requested: Scope needs tightening."),
  ).toBeVisible();
  expect(screen.getByText("Which region matters most?")).toBeVisible();
  expect(screen.getByText("What deadline should be used?")).toBeVisible();
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

test("disables short timeline information and shows a hint", async () => {
  const onAddInformation = vi.fn();
  render(<TimelinePanel isAdding={false} onAddInformation={onAddInformation} ticket={ticket} />);

  expect(screen.getByRole("button", { name: "Add information" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Additional information"), "no");

  expect(screen.getByText("Entries need at least 3 characters.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Add information" })).toBeDisabled();
  expect(onAddInformation).not.toHaveBeenCalled();
  expect(screen.getByText("No timeline events")).toBeVisible();

  await userEvent.type(screen.getByLabelText("Additional information"), "tes added");
  await userEvent.click(screen.getByRole("button", { name: "Add information" }));
  expect(onAddInformation).toHaveBeenCalledWith("notes added");
});

test("renders the timeline as read-only when the viewer cannot write", () => {
  render(<TimelinePanel isAdding={false} onAddInformation={vi.fn()} readOnly ticket={ticket} />);

  expect(screen.getByText("The timeline is read-only for this request.")).toBeVisible();
  expect(screen.queryByLabelText("Additional information")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Add information" })).not.toBeInTheDocument();
});

test("omits blank intake fields from the saved payload", async () => {
  const onSave = vi.fn();
  render(
    <IntakePanel
      isSaving={false}
      isSubmitting={false}
      onAddAttachment={vi.fn()}
      onSave={onSave}
      onSubmit={vi.fn()}
      ticket={{
        ...ticket,
        intake: {
          ...ticket.intake,
          priority: null,
          requiredOutputFormat: null,
          customerSuccessCriteria: null,
        },
      }}
    />,
  );

  await userEvent.type(screen.getByLabelText("Priority"), "  ");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(onSave).toHaveBeenCalledWith({
    title: "Regional Brief",
    description: "Assess activity.",
    operationalQuestion: "What changed?",
    areaOrRegion: "Baltic ports",
  });
});

test("hints when intake fields are below the minimum length", async () => {
  render(
    <IntakePanel
      isSaving={false}
      isSubmitting={false}
      onAddAttachment={vi.fn()}
      onSave={vi.fn()}
      onSubmit={vi.fn()}
      ticket={{
        ...ticket,
        intake: { ...ticket.intake, title: null, priority: null },
      }}
    />,
  );

  await userEvent.type(screen.getByLabelText("Title"), "ab");
  await userEvent.type(screen.getByLabelText("Priority"), "a");

  expect(screen.getByText("Needs at least 3 characters or leave it blank.")).toBeVisible();
  expect(screen.getByText("Needs at least 2 characters or leave it blank.")).toBeVisible();

  await userEvent.type(screen.getByLabelText("Title"), "c");
  expect(
    screen.queryByText("Needs at least 3 characters or leave it blank."),
  ).not.toBeInTheDocument();
});
