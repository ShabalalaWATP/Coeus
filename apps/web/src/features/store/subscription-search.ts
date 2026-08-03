import { readStoreSearch, writeStoreSearch, type StoreSearchState } from "./store-search-params";
import type {
  StoreSubscription,
  StoreSubscriptionInput,
  StoreSubscriptionScope,
} from "../../lib/api-client/store-organisation";

type Criteria = StoreSubscriptionInput["criteria"];

export function criteriaFromParams(params: URLSearchParams): Criteria {
  const search = readStoreSearch(params);
  return {
    acgIds: search.acgIds,
    query: search.query || null,
    productType: search.productType || null,
    region: search.region || null,
    tag: search.tag || null,
    sourceType: search.sourceType || null,
    dateFrom: search.dateFrom || null,
    dateTo: search.dateTo || null,
  };
}

export function hasSubscriptionCriteria(criteria: Criteria): boolean {
  return (
    (criteria.acgIds?.length ?? 0) > 0 ||
    Object.entries(criteria).some(
      ([key, value]) => key !== "acgIds" && typeof value === "string" && value.trim(),
    )
  );
}

export function subscriptionSearchPath(subscription: StoreSubscription): string {
  const criteria = subscription.criteria;
  const search: StoreSearchState = {
    acgIds: criteria.acgIds,
    query: criteria.query ?? "",
    productType: criteria.productType ?? "",
    region: criteria.region ?? "",
    tag: criteria.tag ?? "",
    sourceType: criteria.sourceType ?? "",
    dateFrom: criteria.dateFrom ?? "",
    dateTo: criteria.dateTo ?? "",
    sort: "relevance",
    page: 1,
  };
  return `/store?${writeStoreSearch(search).toString()}`;
}

export function criteriaSummary(
  subscription: StoreSubscription,
  scopes: StoreSubscriptionScope[],
  unknownAcgLabel = "Access changed",
): string {
  const labels = new Map(scopes.map((scope) => [scope.id, scope.code]));
  const values = subscription.criteria.acgIds.map((acgId) => labels.get(acgId) ?? unknownAcgLabel);
  for (const [key, value] of Object.entries(subscription.criteria)) {
    if (key !== "acgIds" && value) values.push(String(value));
  }
  return values.join(" · ");
}

export function hasCurrentAcgAccess(
  subscription: StoreSubscription,
  scopes: StoreSubscriptionScope[],
): boolean {
  const available = new Set(scopes.map((scope) => scope.id));
  return subscription.criteria.acgIds.every((acgId) => available.has(acgId));
}
