import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProductOffersPanel } from "./ProductOffersPanel";
import { requestTicket as ticket, rfiResultsFixture as rfiResults } from "./requests-test-data";

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

test("surfaces offer loading failures instead of an empty offers message", () => {
  render(
    <ProductOffersPanel
      isAccepting={false}
      isError
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onRun={vi.fn()}
      ticket={{ ...ticket, state: "RFI_MATCH_OFFERED" }}
    />,
  );

  expect(screen.getByRole("alert")).toHaveTextContent(
    "Product offers could not be loaded. Refresh and try again.",
  );
  expect(screen.queryByText("No product offers")).not.toBeInTheDocument();
});
