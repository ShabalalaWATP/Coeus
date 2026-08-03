import {
  criteriaFromParams,
  criteriaSummary,
  hasCurrentAcgAccess,
  hasSubscriptionCriteria,
  subscriptionSearchPath,
} from "./subscription-search";
import { subscriptionFixture, subscriptionScopeFixture } from "./store-organisation.fixtures";

test("recognises ACG, keyword and empty subscription criteria", () => {
  expect(hasSubscriptionCriteria({})).toBe(false);
  expect(hasSubscriptionCriteria({ acgIds: [], query: null })).toBe(false);
  expect(hasSubscriptionCriteria({ acgIds: [], query: " " })).toBe(false);
  expect(hasSubscriptionCriteria({ acgIds: [], query: "ports" })).toBe(true);
  expect(hasSubscriptionCriteria({ acgIds: ["acg-eastern"] })).toBe(true);
});

test("maps empty URL parameters to an empty subscription", () => {
  expect(criteriaFromParams(new URLSearchParams())).toEqual({
    acgIds: [],
    query: null,
    productType: null,
    region: null,
    tag: null,
    sourceType: null,
    dateFrom: null,
    dateTo: null,
  });
});

test("writes every supported criterion back to an authorised Store search", () => {
  const subscription = {
    ...subscriptionFixture,
    criteria: {
      acgIds: ["acg-eastern"],
      query: "ports",
      productType: "assessment_report",
      region: "Eastern Europe",
      tag: "logistics",
      sourceType: "finished_assessment",
      dateFrom: "2026-01-01",
      dateTo: "2026-08-03",
    },
  };

  expect(subscriptionSearchPath(subscription)).toBe(
    "/store?acg=acg-eastern&q=ports&type=assessment_report&region=Eastern+Europe&tag=logistics&source=finished_assessment&from=2026-01-01&to=2026-08-03",
  );
});

test("summarises current scopes and fails closed after an access change", () => {
  expect(criteriaSummary(subscriptionFixture, [subscriptionScopeFixture])).toContain("ACG-EAST");
  expect(criteriaSummary(subscriptionFixture, [])).toContain("Access changed");
  expect(hasCurrentAcgAccess(subscriptionFixture, [subscriptionScopeFixture])).toBe(true);
  expect(hasCurrentAcgAccess(subscriptionFixture, [])).toBe(false);
  expect(
    hasCurrentAcgAccess(
      { ...subscriptionFixture, criteria: { ...subscriptionFixture.criteria, acgIds: [] } },
      [],
    ),
  ).toBe(true);
});
