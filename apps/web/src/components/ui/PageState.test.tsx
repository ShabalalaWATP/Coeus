import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { EmptyState, ErrorState, LoadingState } from "./PageState";

test("renders a loading state with the default label", () => {
  render(<LoadingState />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading");
});

test("renders a loading state with a custom label", () => {
  render(<LoadingState label="Loading audit events" />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading audit events");
});

test("renders an error state without a retry action", () => {
  render(<ErrorState />);

  expect(screen.getByRole("alert")).toHaveTextContent("Unable to load data");
  expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
});

test("renders an error state and calls the retry action", async () => {
  const onRetry = vi.fn();
  render(<ErrorState message="Queue unavailable." onRetry={onRetry} />);

  expect(screen.getByText("Queue unavailable.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));

  expect(onRetry).toHaveBeenCalledTimes(1);
});

test("renders an empty state with a hint", () => {
  render(<EmptyState hint="Adjust the filters." title="No results" />);

  expect(screen.getByText("No results")).toBeVisible();
  expect(screen.getByText("Adjust the filters.")).toBeVisible();
});

test("renders an empty state without a hint", () => {
  render(<EmptyState title="No results" />);

  expect(screen.getByText("No results")).toBeVisible();
  expect(screen.queryByRole("paragraph")).not.toBeInTheDocument();
});
