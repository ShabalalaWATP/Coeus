import { render, screen } from "@testing-library/react";

import { StoreMatchReasons } from "./StoreMatchReasons";

test("renders compact formatted store match reasons", () => {
  render(
    <StoreMatchReasons
      reasons={["lexical-rank:2", "vector-similarity:0.81", "semantic-label:maritime"]}
      show
    />,
  );

  expect(screen.getByRole("list", { name: "Why it matched" })).toBeVisible();
  expect(screen.getByText("Text rank 2")).toBeVisible();
  expect(screen.getByText("Semantic 81%")).toBeVisible();
  expect(screen.getByText("Label maritime")).toBeVisible();
});

test("hides visible-only reasons and formats fallback reasons", () => {
  const { rerender } = render(<StoreMatchReasons reasons={["visible"]} show />);

  expect(screen.queryByRole("list", { name: "Why it matched" })).not.toBeInTheDocument();

  rerender(
    <StoreMatchReasons
      reasons={["retrieval:lexical-only", "metadata:region", "full-text:harbour", "custom"]}
      show
    />,
  );

  expect(screen.getByText("Lexical fallback")).toBeVisible();
  expect(screen.getByText("Metadata region")).toBeVisible();
  expect(screen.getByText("Term harbour")).toBeVisible();
  expect(screen.queryByText("custom")).not.toBeInTheDocument();
});

test("renders unknown reasons when inside the visible truncation window", () => {
  render(<StoreMatchReasons reasons={["custom", "metadata:region", "full-text:harbour"]} show />);

  expect(screen.getByText("custom")).toBeVisible();
});

test("does not render reasons before a query is submitted", () => {
  render(<StoreMatchReasons reasons={["lexical-rank:1"]} show={false} />);

  expect(screen.queryByRole("list", { name: "Why it matched" })).not.toBeInTheDocument();
});
