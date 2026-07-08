import { render, screen } from "@testing-library/react";

import { StoreMatchReasons } from "./StoreMatchReasons";

test("renders compact formatted store match reasons", () => {
  render(
    <StoreMatchReasons
      reasons={["lexical-rank:2", "vector-similarity:0.81", "semantic-label:maritime"]}
      show
    />,
  );

  expect(screen.getByLabelText("Why this matched")).toBeVisible();
  expect(screen.getByText("Text rank 2")).toBeVisible();
  expect(screen.getByText("Semantic 81%")).toBeVisible();
  expect(screen.getByText("Label maritime")).toBeVisible();
});

test("hides visible-only reasons and formats fallback reasons", () => {
  const { rerender } = render(<StoreMatchReasons reasons={["visible"]} show />);

  expect(screen.queryByLabelText("Why this matched")).not.toBeInTheDocument();

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

test("does not render reasons before a query is submitted", () => {
  render(<StoreMatchReasons reasons={["lexical-rank:1"]} show={false} />);

  expect(screen.queryByLabelText("Why this matched")).not.toBeInTheDocument();
});
