import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RfiFollowUpChat } from "./RfiFollowUpChat";
import { requestTicket } from "./requests-test-data";

const conversationTicket = {
  ...requestTicket,
  messages: [
    {
      id: "customer-message",
      author: "user" as const,
      body: "The coverage is too old.",
      createdAt: "2026-08-02T12:00:00Z",
    },
    {
      id: "assistant-message",
      author: "assistant" as const,
      body: "What should the next search cover?",
      createdAt: "2026-08-02T12:01:00Z",
    },
  ],
};

test("records bounded feedback and clears it after success", async () => {
  const onSend = vi.fn((_feedback: string, onSuccess?: () => void) => onSuccess?.());
  render(
    <RfiFollowUpChat
      feedbackPending
      isSending={false}
      onSend={onSend}
      ticket={conversationTicket}
    />,
  );

  expect(screen.getByText("You")).toBeVisible();
  expect(screen.getByText("Istari")).toBeVisible();
  const input = screen.getByLabelText("What was missing?");
  fireEvent.submit(input.closest("form")!);
  expect(onSend).not.toHaveBeenCalled();

  await userEvent.type(input, "Needs reporting from the last 48 hours.");
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));
  expect(onSend).toHaveBeenCalledWith(
    "Needs reporting from the last 48 hours.",
    expect.any(Function),
  );
  expect(input).toHaveValue("");
});

test("locks the feedback action while it is being sent", () => {
  render(
    <RfiFollowUpChat feedbackPending isSending onSend={vi.fn()} ticket={conversationTicket} />,
  );

  expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
});
