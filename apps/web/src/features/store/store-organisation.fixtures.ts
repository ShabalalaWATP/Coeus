import { productFixture } from "./store-test-fixtures";
import type {
  StoreProject,
  StoreProjectSummary,
  StoreSubscription,
} from "../../lib/api-client/store-organisation";

export const projectSummary: StoreProjectSummary = {
  archived: false,
  dateFrom: "2026-01-01",
  dateTo: null,
  id: "project-1",
  memberCount: 1,
  name: "Eastern Europe watch",
  owner: true,
  purpose: "Track regional reporting",
  region: "Eastern Europe",
  updatedAt: "2026-08-02T09:00:00Z",
  visibleProductCount: 1,
};

export const projectDetail: StoreProject = {
  ...projectSummary,
  activity: [
    {
      action: "project_created",
      actorDisplayName: "Sprint 2 Operator",
      id: "activity-1",
      occurredAt: "2026-08-02T09:00:00Z",
    },
  ],
  entries: [],
  members: [
    {
      displayName: "Sprint 2 Operator",
      id: "preview-user",
      owner: true,
      username: "preview@example.test",
    },
  ],
  products: [productFixture],
};

export const subscriptionFixture: StoreSubscription = {
  cadence: "weekly",
  createdAt: "2026-08-02T09:00:00Z",
  criteria: {
    dateFrom: null,
    dateTo: null,
    productType: null,
    query: "drone activity",
    region: "Eastern Europe",
    sourceType: null,
    tag: null,
  },
  enabled: true,
  id: "subscription-1",
  name: "Regional drone reporting",
  updatedAt: "2026-08-02T09:00:00Z",
};
