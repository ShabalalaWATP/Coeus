import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ReanalysisDecisionPanel } from "./ReanalysisDecisionPanel";
import { baseTicket } from "./routing-test-fixtures";

test("fails safe when the re-analysis decision context is absent", () => {
  render(
    <MemoryRouter>
      <ReanalysisDecisionPanel
        isJioc={false}
        onDecide={vi.fn()}
        onRationaleChange={vi.fn()}
        pending={false}
        rationale="Valid rationale"
        ticket={{ ...baseTicket, reanalysisContext: null }}
      />
    </MemoryRouter>,
  );

  expect(screen.getByText("Decision context is unavailable. Do not proceed.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Agree and return to analysis" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Disagree and refer to JIOC" })).toBeDisabled();
});

test("shows JIOC context and sends both final decisions", async () => {
  const decide = vi.fn();
  const change = vi.fn();
  render(
    <MemoryRouter>
      <ReanalysisDecisionPanel
        isJioc
        onDecide={decide}
        onRationaleChange={change}
        pending={false}
        rationale="Independent final rationale"
        ticket={{
          ...baseTicket,
          reanalysisContext: {
            productId: "product/1",
            customerReason: "The answer omitted a required indicator.",
            unmetCriteria: [],
            managerRationale: "The manager considers the original scope complete.",
          },
        }}
      />
    </MemoryRouter>,
  );

  expect(screen.queryByText("Unmet criteria")).not.toBeInTheDocument();
  expect(screen.getByText(/original scope complete/)).toBeVisible();
  expect(screen.getByRole("link", { name: "Review the released product" })).toHaveAttribute(
    "href",
    "/store/products/product%2F1",
  );
  await userEvent.type(screen.getByLabelText("Decision rationale"), " updated");
  await userEvent.click(screen.getByRole("button", { name: "Order re-analysis" }));
  await userEvent.click(screen.getByRole("button", { name: "Close without re-analysis" }));

  expect(change).toHaveBeenCalled();
  expect(decide).toHaveBeenNthCalledWith(1, "reanalyse");
  expect(decide).toHaveBeenNthCalledWith(2, "close");
});
