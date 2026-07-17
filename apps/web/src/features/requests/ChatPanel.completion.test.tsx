import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatPanel } from "./ChatPanel";
import { requestTicket as ticket } from "./requests-test-data";

test("replaces the message form with a prominent submit action once complete", async () => {
  const onReopen = vi.fn();
  const onSubmit = vi.fn();
  render(
    <ChatPanel
      canSubmit
      isSending={false}
      onReopen={onReopen}
      onSend={vi.fn()}
      onSubmit={onSubmit}
      ticket={{ ...ticket, conversationStatus: "closed" }}
    />,
  );

  expect(
    screen.getByText("The conversation is complete. Review the details and press Submit."),
  ).toBeVisible();
  expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add more information" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();

  await userEvent.click(screen.getByRole("button", { name: "Add more information" }));
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));
  expect(onReopen).toHaveBeenCalledTimes(1);
  expect(onSubmit).toHaveBeenCalledTimes(1);
});

test("keeps the completion submit disabled while required details are missing", () => {
  render(
    <ChatPanel
      canSubmit
      isReopening
      isSending={false}
      isSubmitting
      onSend={vi.fn()}
      onReopen={vi.fn()}
      onSubmit={vi.fn()}
      ticket={{
        ...ticket,
        conversationStatus: "closed",
        isReadyForSubmission: false,
      }}
    />,
  );

  expect(
    screen.getByText("The conversation is complete. Review the missing details before submitting."),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "Reopening..." })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Submitting..." })).toBeDisabled();
});

test("does not offer completion submission without a submit action", () => {
  render(
    <ChatPanel
      canSubmit
      isSending={false}
      onSend={vi.fn()}
      ticket={{ ...ticket, conversationStatus: "closed" }}
    />,
  );

  expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
});
