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

async function search(term: string) {
  renderWithProviders(<StorePage />, "/store");
  await screen.findByRole("heading", { name: "Intelligence Store" });
  await userEvent.type(screen.getByLabelText("Search the Intelligence Store"), term);
  await userEvent.click(screen.getByRole("button", { name: "Search" }));
}

test("explains a word-order hybrid match in the operator's own terms", async () => {
  vi.stubGlobal("fetch", searchResponses(["lexical-rank:1", "full-text:vessel"]));

  await search("vessel port");

  expect(await screen.findByText("Gulf Vessel Movement Assessment")).toBeVisible();
  expect(screen.getByText("Matched vessel")).toBeVisible();
  expect(screen.getByText("Text rank 1 · Term vessel")).toBeVisible();
});

test("explains a stem-folded hybrid match", async () => {
  vi.stubGlobal("fetch", searchResponses(["lexical-rank:1", "full-text:vessels"]));

  await search("vessels");

  expect(await screen.findByText("Gulf Vessel Movement Assessment")).toBeVisible();
  expect(screen.getByText("Matched vessels")).toBeVisible();
});

function searchResponses(matchReasons: string[]) {
  // The store fetches nothing until the search is submitted, so the search
  // response is the only one needed.
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        products: [{ ...baseProduct, matchReasons }],
        total: 1,
        facets: {
          productTypes: [],
          regions: [],
          tags: [],
          counts: { productTypes: {}, regions: {}, tags: {} },
        },
        relaxed: false,
      }),
  });
}
