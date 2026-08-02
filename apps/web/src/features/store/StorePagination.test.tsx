import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PaginationControls, PaginationSummary } from "./StorePagination";
import { pageWindow } from "./store-page-window";

test("summarises the visible slice of a result set", () => {
  const { rerender } = render(<PaginationSummary page={2} pageSize={24} total={60} />);
  expect(screen.getByText("Showing 25-48 of 60")).toBeVisible();

  rerender(<PaginationSummary page={3} pageSize={24} total={60} />);
  expect(screen.getByText("Showing 49-60 of 60")).toBeVisible();

  rerender(<PaginationSummary page={1} pageSize={24} total={0} />);
  expect(screen.getByText("No products to show.")).toBeVisible();
});

test("describes no range for a page past the end rather than a backwards one", () => {
  const { container } = render(<PaginationSummary page={3} pageSize={24} total={17} />);

  expect(container).toBeEmptyDOMElement();
});

test("keeps a deep catalogue navigable with first, last and a local window", () => {
  expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
  expect(pageWindow(1, 47)).toEqual([1, 2, null, 47]);
  expect(pageWindow(24, 47)).toEqual([1, null, 23, 24, 25, null, 47]);
  expect(pageWindow(47, 47)).toEqual([1, null, 46, 47]);
});

test("renders nothing rather than guessing when the page count is unusable", () => {
  const { container, rerender } = render(
    <PaginationControls onSelect={vi.fn()} page={1} totalPages={1} />,
  );
  expect(container).toBeEmptyDOMElement();

  rerender(
    <PaginationControls
      onSelect={vi.fn()}
      page={undefined as unknown as number}
      totalPages={undefined as unknown as number}
    />,
  );
  expect(container).toBeEmptyDOMElement();
  expect(pageWindow(1, undefined as unknown as number)).toEqual([]);
});

test("selects a page directly and by stepping", async () => {
  const onSelect = vi.fn();
  render(<PaginationControls onSelect={onSelect} page={2} totalPages={5} />);

  await userEvent.click(screen.getByRole("button", { name: "Page 5" }));
  expect(onSelect).toHaveBeenLastCalledWith(5);

  await userEvent.click(screen.getByRole("button", { name: "Next page" }));
  expect(onSelect).toHaveBeenLastCalledWith(3);

  await userEvent.click(screen.getByRole("button", { name: "Previous page" }));
  expect(onSelect).toHaveBeenLastCalledWith(1);

  expect(screen.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-current", "page");
});

test("disables stepping past either end", () => {
  const { rerender } = render(<PaginationControls onSelect={vi.fn()} page={1} totalPages={4} />);
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();

  rerender(<PaginationControls onSelect={vi.fn()} page={4} totalPages={4} />);
  expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
});
