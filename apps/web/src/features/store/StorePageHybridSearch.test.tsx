import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import StorePage from "./StorePage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const baseProduct = {
  id: "product-maritime",
  reference: "PROD-2001",
  title: "Gulf Vessel Movement Assessment",
  summary: "MOCK DATA ONLY maritime movement review",
  description: "Synthetic detail",
  productType: "assessment_report",
  sourceType: "finished_assessment",
  ownerTeam: "RFA",
  areaOrRegion: "Baltic ports",
  classificationLevel: 2,
  releasability: ["MOCK"],
  handlingCaveats: ["MOCK DATA ONLY"],
  tags: ["vessel"],
  acgIds: ["acg-alpha"],
  projectId: "project-northstar",
  status: "published",
  timePeriodStart: null,
  timePeriodEnd: null,
  geojsonRef: null,
  assets: [],
  matchScore: 1,
  matchReasons: ["visible"],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders word-order hybrid browse results with match reasons", async () => {
  vi.stubGlobal("fetch", searchResponses(["lexical-rank:1", "full-text:vessel"]));

  renderWithProviders(<StorePage />, "/store");
  await screen.findByRole("heading", { name: "Intelligence Store" });
  await userEvent.type(screen.getByLabelText("Full text"), "vessel port");
  await userEvent.click(screen.getByRole("button", { name: "Search products" }));

  expect(await screen.findByText("Gulf Vessel Movement Assessment")).toBeVisible();
  expect(screen.getByRole("list", { name: "Why it matched" })).toBeVisible();
  expect(screen.getByText("Text rank 1")).toBeVisible();
  expect(screen.getByText("Term vessel")).toBeVisible();
});

test("renders stem-folded hybrid browse results with match reasons", async () => {
  vi.stubGlobal("fetch", searchResponses(["lexical-rank:1", "full-text:vessels"]));

  renderWithProviders(<StorePage />, "/store");
  await screen.findByRole("heading", { name: "Intelligence Store" });
  await userEvent.type(screen.getByLabelText("Full text"), "vessels");
  await userEvent.click(screen.getByRole("button", { name: "Search products" }));

  expect(await screen.findByText("Gulf Vessel Movement Assessment")).toBeVisible();
  expect(screen.getByRole("list", { name: "Why it matched" })).toBeVisible();
  expect(screen.getByText("Term vessels")).toBeVisible();
});

function searchResponses(matchReasons: string[]) {
  return vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [],
          total: 0,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [{ ...baseProduct, matchReasons }],
          total: 1,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    });
}
