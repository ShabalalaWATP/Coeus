import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

import { ProductOffersPanel } from "./ProductOffersPanel";
import { requestTicket as ticket, rfiResultsFixture as rfiResults } from "./requests-test-data";

function renderPanel(panel: ReactNode) {
  return render(panel, { wrapper: MemoryRouter });
}

test("only offers a retry after automatic RFI search is incomplete", async () => {
  const onRun = vi.fn();
  renderPanel(
    <ProductOffersPanel
      canManageOffers
      canRunSearch
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onRun={onRun}
      ticket={{ ...ticket, state: "RFI_SEARCH_INCOMPLETE" }}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "Retry search" }));

  expect(onRun).toHaveBeenCalledTimes(1);
  expect(screen.getByText("No product offers")).toBeVisible();
});

test("labels multiple returned products without exposing their details", () => {
  const secondOffer = {
    ...rfiResults.offers[0],
    productId: "product-2",
    title: "Second authorised product",
  };
  renderPanel(
    <ProductOffersPanel
      canManageOffers={false}
      canRunSearch={false}
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onRun={vi.fn()}
      results={{ ...rfiResults, offers: [...rfiResults.offers, secondOffer] }}
      ticket={{ ...ticket, state: "RFI_MATCH_OFFERED" }}
    />,
  );

  expect(screen.getByRole("heading", { name: "Matching products" })).toBeVisible();
  expect(screen.getAllByText("Product details")).toHaveLength(2);
});

test("accepts and rejects RFI product offers", async () => {
  const onAccept = vi.fn();
  const onReject = vi.fn();
  renderPanel(
    <ProductOffersPanel
      canManageOffers
      canRunSearch
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

  expect(screen.getByRole("heading", { name: "Matching product" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Regional Stability Brief" })).toHaveAttribute(
    "href",
    "/store/products/product-1",
  );
  expect(screen.getByText("MOCK DATA ONLY assessment summary.")).toBeVisible();
  expect(screen.getByText("Class 2")).toBeVisible();

  const productDetails = screen.getByText("Product details").closest("details");
  const searchDetails = screen.getByText("Search details").closest("details");
  expect(productDetails).not.toHaveAttribute("open");
  expect(searchDetails).not.toHaveAttribute("open");
  expect(screen.getByLabelText("Retrieval relevance 86 percent")).not.toBeVisible();
  expect(screen.getByText("Grounded evidence (1)")).not.toBeVisible();
  expect(screen.getByLabelText("RFI search metrics")).not.toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Accept" }));
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Too old.");
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));
  await userEvent.click(screen.getByText("Product details"));

  expect(productDetails).toHaveAttribute("open");
  expect(screen.getByText("86%")).toBeVisible();
  expect(screen.getByLabelText("Retrieval relevance 86 percent")).toHaveAttribute(
    "title",
    "Retrieval relevance, not analytic confidence",
  );
  expect(screen.getByText("Grounded evidence (1)")).toBeVisible();
  expect(screen.getByText("Regional brief.pdf, page 2")).toBeInTheDocument();
  expect(screen.getByText(/Synthetic reporting describes activity/)).toBeInTheDocument();

  await userEvent.click(screen.getByText("Search details"));
  expect(searchDetails).toHaveAttribute("open");
  expect(screen.getByLabelText("RFI search metrics")).toBeVisible();
  expect(onAccept).toHaveBeenCalledWith("product-1");
  expect(onReject).toHaveBeenCalledWith("product-1", "Too old.");
});

test("makes degraded retrieval explicit and avoids claiming a definitive no-match", () => {
  renderPanel(
    <ProductOffersPanel
      canManageOffers
      canRunSearch
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onRun={vi.fn()}
      results={{
        ...rfiResults,
        offers: [],
        retrievalMode: "lexical_only",
        degradedReason: "provider_unavailable",
        metrics: rfiResults.metrics
          ? { ...rfiResults.metrics, retrievalMode: "lexical_only" }
          : null,
      }}
      ticket={{ ...ticket, state: "RFI_SEARCH_INCOMPLETE" }}
    />,
  );

  expect(screen.getByRole("alert")).toHaveTextContent(
    "No definitive no-match decision will be made",
  );
  expect(screen.getByRole("alert")).toHaveTextContent("lexical only");
  expect(screen.getByRole("heading", { name: "Product search" })).toBeVisible();
});

test("does not render RFI metrics when metrics are unavailable", () => {
  renderPanel(
    <ProductOffersPanel
      canManageOffers
      canRunSearch
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onRun={vi.fn()}
      results={{ ...rfiResults, metrics: null, offers: [] }}
      ticket={{ ...ticket, state: "JIOC_REVIEW" }}
    />,
  );

  expect(screen.queryByLabelText("RFI search metrics")).not.toBeInTheDocument();
});

test("surfaces offer loading failures instead of an empty offers message", () => {
  renderPanel(
    <ProductOffersPanel
      canManageOffers
      canRunSearch
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
  expect(screen.getByRole("heading", { name: "Product search" })).toBeVisible();
});

test("keeps RFI actions read-only for viewers", async () => {
  const onRun = vi.fn();
  const onAccept = vi.fn();
  const onReject = vi.fn();
  renderPanel(
    <ProductOffersPanel
      canManageOffers={false}
      canRunSearch={false}
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={onAccept}
      onReject={onReject}
      onRun={onRun}
      results={rfiResults}
      ticket={{ ...ticket, state: "RFI_MATCH_OFFERED" }}
    />,
  );

  expect(screen.queryByRole("button", { name: "Retry search" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Accept" })).toBeDisabled();
  expect(screen.getByLabelText("Rejection reason")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Accept" }));

  expect(onRun).not.toHaveBeenCalled();
  expect(onAccept).not.toHaveBeenCalled();
  expect(onReject).not.toHaveBeenCalled();
});

test("shows an empty selection state when no request is selected", () => {
  renderPanel(
    <ProductOffersPanel
      canManageOffers
      canRunSearch
      isAccepting={false}
      isLoading={false}
      isRejecting={false}
      isRunning={false}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onRun={vi.fn()}
    />,
  );

  expect(screen.getByText("No ticket selected")).toBeVisible();
  expect(screen.queryByText("No product offers")).not.toBeInTheDocument();
});
