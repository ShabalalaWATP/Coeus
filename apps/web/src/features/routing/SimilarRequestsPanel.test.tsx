import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SimilarRequestsPanel } from "./SimilarRequestsPanel";

const match = {
  ticketId: "ticket-2",
  reference: "TCK-0002",
  title: "Synthetic related request",
  state: "RFI_SEARCHING",
  score: 0.734,
  reasons: [],
  alreadyLinked: false,
  alreadyMarkedDuplicate: false,
  requestKind: "RFI",
  approvedRoute: null,
  assignedTeam: null,
  requestingUnit: null,
  supportedOperation: null,
  timePeriodStart: null,
  timePeriodEnd: null,
};

test("renders loading, failed and empty similar-request states", async () => {
  const onRetry = vi.fn<() => void>();
  const { rerender } = render(
    <SimilarRequestsPanel
      isLoading
      isMutating={false}
      isQueryError={false}
      onLink={vi.fn()}
      onMarkDuplicate={vi.fn()}
      onRetry={onRetry}
    />,
  );
  expect(screen.getByText("Checking open requests")).toBeVisible();

  rerender(
    <SimilarRequestsPanel
      isLoading={false}
      isMutating={false}
      isQueryError
      onLink={vi.fn()}
      onMarkDuplicate={vi.fn()}
      onRetry={onRetry}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(onRetry.mock.calls).toHaveLength(1);

  rerender(
    <SimilarRequestsPanel
      isLoading={false}
      isMutating={false}
      isQueryError={false}
      matches={{ matches: [] }}
      onLink={vi.fn()}
      onMarkDuplicate={vi.fn()}
      onRetry={onRetry}
    />,
  );
  expect(screen.getByText("No similar open requests.")).toBeVisible();
});

test("renders an unbounded match and confirms source withdrawal", async () => {
  const onLink = vi.fn();
  const onMarkDuplicate = vi.fn();
  const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
  render(
    <SimilarRequestsPanel
      isLoading={false}
      isMutating={false}
      isQueryError={false}
      matches={{ matches: [match] }}
      onLink={onLink}
      onMarkDuplicate={onMarkDuplicate}
      onRetry={vi.fn()}
    />,
  );

  expect(screen.getByText("73%")).toBeVisible();
  expect(screen.queryByText(/^Route:/)).not.toBeInTheDocument();
  const withdraw = screen.getByRole("button", { name: /Mark & withdraw source/ });
  await userEvent.click(withdraw);
  expect(onMarkDuplicate).not.toHaveBeenCalled();
  await userEvent.click(withdraw);
  expect(confirm).toHaveBeenCalledTimes(2);
  expect(onMarkDuplicate).toHaveBeenCalledWith("ticket-2", true);
});

test("disables all consolidation controls for an already marked match", () => {
  render(
    <SimilarRequestsPanel
      isLoading={false}
      isMutating
      isQueryError={false}
      matches={{
        matches: [{ ...match, alreadyLinked: true, alreadyMarkedDuplicate: true }],
      }}
      onLink={vi.fn()}
      onMarkDuplicate={vi.fn()}
      onRetry={vi.fn()}
    />,
  );

  expect(screen.getByRole("button", { name: "Linked" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Duplicate marked" })).toBeDisabled();
  expect(screen.getByRole("button", { name: /Mark & withdraw source/ })).toBeDisabled();
});
