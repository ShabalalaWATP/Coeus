import { fireEvent, render, screen } from "@testing-library/react";

import { CalendarCommitmentActions } from "./CalendarCommitmentActions";
import type { CalendarCommitment } from "../../lib/api-client/workforce-calendar";

const commitment = {
  event: { eventId: "event-1" },
  responseState: "pending",
  responseVersion: 1,
  notifiedAt: "2026-08-04T09:00:00Z",
  respondedAt: null,
} as CalendarCommitment;

test("acknowledges and submits a relevant dispute reason", () => {
  const onRespond = vi.fn();
  const { rerender } = render(
    <CalendarCommitmentActions commitment={commitment} disabled={false} onRespond={onRespond} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
  expect(onRespond).toHaveBeenCalledWith(commitment, "acknowledged");
  fireEvent.click(screen.getByRole("button", { name: "Dispute" }));
  const reason = screen.getByRole("textbox", {
    name: "Why does this commitment need changing?",
  });
  fireEvent.change(reason, { target: { value: "It overlaps approved leave." } });
  fireEvent.click(screen.getByRole("button", { name: "Send dispute" }));
  expect(onRespond).toHaveBeenLastCalledWith(commitment, "disputed", "It overlaps approved leave.");
  rerender(
    <CalendarCommitmentActions
      commitment={{ ...commitment, responseState: "acknowledged" }}
      disabled={false}
      onRespond={onRespond}
    />,
  );
  expect(screen.getByText("Acknowledged")).toBeVisible();
});
