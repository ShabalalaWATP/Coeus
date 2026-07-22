import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatPanel } from "./ChatPanel";
import { IntakePanel } from "./IntakePanel";
import { requestTicket as ticket } from "./requests-test-data";
import { TimelinePanel } from "./TimelinePanel";
import { ticketMetrics } from "./ticket-collection";

test("calculates ticket metrics for every visible state", () => {
  expect(
    ticketMetrics([
      ticket,
      { ...ticket, id: "ticket-2", state: "INFO_REQUIRED", isReadyForSubmission: false },
      { ...ticket, id: "ticket-3", state: "RFI_SEARCHING" },
      { ...ticket, id: "ticket-4", state: "RFI_MATCH_OFFERED" },
    ]),
  ).toEqual({ total: 4, draft: 2, awaitingAction: 1, inProgress: 1, completed: 0 });
});

test("disables sending short chat messages and shows a hint", async () => {
  const onSend = vi.fn();
  render(<ChatPanel isSending={false} onSend={onSend} />);

  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Message"), "no");

  expect(screen.getByText("Messages need at least 3 characters.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  expect(onSend).not.toHaveBeenCalled();

  await userEvent.type(screen.getByLabelText("Message"), "w a brief");
  expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(onSend).toHaveBeenCalledWith("now a brief", expect.any(Function));
});

test("greets the customer when a conversation has not started", () => {
  render(<ChatPanel isSending={false} onSend={vi.fn()} />);

  expect(screen.getByText(/Hi, I am Istari/)).toBeVisible();
});

test("shows an empty transcript note for read-only conversations", () => {
  render(<ChatPanel isSending={false} onSend={vi.fn()} readOnly />);

  expect(screen.getByText("No chat transcript")).toBeVisible();
  expect(screen.queryByText(/Hi, I am Istari/)).not.toBeInTheDocument();
});

class FakeSpeechRecognition {
  static instances: FakeSpeechRecognition[] = [];
  continuous = false;
  interimResults = false;
  lang = "";
  onend: (() => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onresult:
    | ((event: {
        resultIndex: number;
        results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }>;
      }) => void)
    | null = null;
  start = vi.fn();
  stop = vi.fn(() => this.onend?.());

  constructor() {
    FakeSpeechRecognition.instances.push(this);
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeSpeechRecognition.instances = [];
});

test("hides the dictate button when the browser has no speech support", () => {
  render(<ChatPanel isSending={false} onSend={vi.fn()} />);

  expect(screen.queryByRole("button", { name: "Dictate" })).not.toBeInTheDocument();
});

test("dictates a message with the microphone", async () => {
  vi.stubGlobal("SpeechRecognition", FakeSpeechRecognition);
  render(<ChatPanel isSending={false} onSend={vi.fn()} />);

  await userEvent.click(screen.getByRole("button", { name: "Dictate" }));
  const recognition = FakeSpeechRecognition.instances.at(-1);
  expect(recognition?.start).toHaveBeenCalled();
  expect(screen.getByText(/Listening/)).toBeVisible();

  act(() => {
    recognition?.onresult?.({
      resultIndex: 0,
      results: [{ 0: { transcript: "need a harbour brief" }, isFinal: true }],
    });
  });
  expect(screen.getByLabelText("Message")).toHaveValue("need a harbour brief");

  act(() => {
    recognition?.onresult?.({
      resultIndex: 0,
      results: [{ 0: { transcript: "with imagery" }, isFinal: true }],
    });
  });
  expect(screen.getByLabelText("Message")).toHaveValue("need a harbour brief with imagery");

  await userEvent.click(screen.getByRole("button", { name: "Stop dictation" }));
  expect(recognition?.stop).toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Dictate" })).toBeVisible();
});

test("explains when microphone access is blocked", async () => {
  vi.stubGlobal("SpeechRecognition", FakeSpeechRecognition);
  render(<ChatPanel isSending={false} onSend={vi.fn()} />);

  await userEvent.click(screen.getByRole("button", { name: "Dictate" }));
  act(() => {
    FakeSpeechRecognition.instances.at(-1)?.onerror?.({ error: "not-allowed" });
  });

  expect(
    screen.getByText("Microphone access was blocked. Allow it in the browser to dictate."),
  ).toBeVisible();
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
      canSubmit
      isAddingAttachment={false}
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
      canSubmit
      isAddingAttachment={false}
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

test("sends explicit null only when a saved intake field is cleared", async () => {
  const onSave = vi.fn();
  render(
    <IntakePanel
      canSubmit
      isAddingAttachment={false}
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

  const intakeForm = screen
    .getByRole("heading", { name: "Extracted Intake" })
    .closest("section")
    ?.querySelector<HTMLFormElement>("form.intake-form");
  expect(intakeForm).not.toBeNull();
  await userEvent.clear(within(intakeForm!).getByLabelText("Description"));
  await userEvent.type(screen.getByLabelText("Priority"), "  ");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(onSave).toHaveBeenCalledWith({ description: null }, expect.any(Function));
});

test("preserves unsaved intake edits when polling refreshes the same ticket", async () => {
  const props = {
    canSubmit: true,
    isAddingAttachment: false,
    isSaving: false,
    isSubmitting: false,
    onAddAttachment: vi.fn(),
    onSave: vi.fn(),
    onSubmit: vi.fn(),
  };
  const rendered = render(<IntakePanel {...props} ticket={ticket} />);
  const title = screen.getByLabelText("Title");
  await userEvent.clear(title);
  await userEvent.type(title, "Unsaved operator title");

  rendered.rerender(
    <IntakePanel
      {...props}
      ticket={{ ...ticket, intake: { ...ticket.intake, title: "Polled server title" } }}
    />,
  );

  expect(screen.getByLabelText("Title")).toHaveValue("Unsaved operator title");
});

test("hints when intake fields are below the minimum length", async () => {
  render(
    <IntakePanel
      canSubmit
      isAddingAttachment={false}
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

  expect(
    screen.getByText("Needs at least 3 characters. Clearing a saved value removes it."),
  ).toBeVisible();
  expect(
    screen.getByText("Needs at least 2 characters. Clearing a saved value removes it."),
  ).toBeVisible();

  await userEvent.type(screen.getByLabelText("Title"), "c");
  expect(
    screen.queryByText("Needs at least 3 characters. Clearing a saved value removes it."),
  ).not.toBeInTheDocument();
});
