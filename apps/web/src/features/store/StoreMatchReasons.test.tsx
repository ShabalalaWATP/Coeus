import { render, screen } from "@testing-library/react";

import { StoreMatchReasons } from "./StoreMatchReasons";
import { matchSummary } from "./store-match-language";

test("leads with what matched and keeps retrieval detail secondary", () => {
  render(
    <StoreMatchReasons
      reasons={["lexical-rank:2", "vector-similarity:0.81", "full-text:harbour"]}
      show
    />,
  );

  expect(screen.getByText("Matched harbour")).toBeVisible();
  expect(screen.getByText("Text rank 2 · Meaning 81% · Term harbour")).toBeVisible();
});

test("describes a semantic-only match in words rather than a score", () => {
  render(<StoreMatchReasons reasons={["vector-similarity:0.44"]} show />);

  expect(screen.getByText("Close match on meaning")).toBeVisible();
});

test("summarises matched terms and related labels together", () => {
  expect(matchSummary(["full-text:arctic", "full-text:ice", "semantic-label:maritime"])).toBe(
    "Matched arctic and ice, related to maritime",
  );
  expect(matchSummary(["semantic-label:maritime"])).toBe("Related to maritime");
  expect(matchSummary(["full-text:arctic", "semantic-label:arctic"])).toBe("Matched arctic");
});

test("joins three or more matched terms readably", () => {
  expect(matchSummary(["full-text:a", "full-text:b", "full-text:c"])).toBe("Matched a, b and c");
});

test("renders nothing when there is nothing to explain", () => {
  const { rerender, container } = render(<StoreMatchReasons reasons={["visible"]} show />);
  expect(container).toBeEmptyDOMElement();

  rerender(<StoreMatchReasons reasons={["full-text:harbour"]} show={false} />);
  expect(container).toBeEmptyDOMElement();

  expect(matchSummary(["lexical-rank:1"])).toBeNull();
});

test("formats remaining signal types without inventing wording", () => {
  render(
    <StoreMatchReasons
      reasons={[
        "retrieval:lexical-only",
        "metadata:region",
        "semantic-label:maritime",
        "full-text:harbour",
        "custom",
      ]}
      show
    />,
  );

  expect(
    screen.getByText("Wording only · Metadata region · Label maritime · Term harbour · custom"),
  ).toBeVisible();
});
