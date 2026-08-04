import { apiRequestJson, apiRequestNoContent } from "./client";
import type { components } from "./generated/openapi";

type Schemas = components["schemas"];
export type SavedView = Schemas["SavedViewResponse"];
export type SavedViewPage = Schemas["SavedViewPage"];
export type PackageTemplate = Schemas["TemplateResponse"];
export type TemplatePage = Schemas["TemplatePage"];
export type WorkUpdate = Schemas["WorkUpdateResponse"];
export type WorkUpdatePage = Schemas["WorkUpdatePage"];
export type Preferences = Schemas["PreferencesResponse"];
export type BoardFilters = Schemas["BoardFiltersPayload"];
export type StoreLink = Schemas["StoreLinkResponse"];
export type StoreLinkPage = Schemas["StoreLinkPage"];

const jsonHeaders = (csrfToken: string) => ({
  "Content-Type": "application/json",
  "X-CSRF-Token": csrfToken,
});

export function getSavedViews(): Promise<SavedViewPage> {
  return apiRequestJson("/api/v1/organisation/saved-board-views?limit=100", { method: "GET" });
}

export function saveView(
  unitId: string,
  name: string,
  filters: BoardFilters,
  csrfToken: string,
): Promise<SavedView> {
  return apiRequestJson(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/saved-board-views`,
    {
      method: "PUT",
      headers: jsonHeaders(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `save-board-view-${crypto.randomUUID()}`,
        viewId: crypto.randomUUID(),
        name,
        expectedVersion: 0,
        filters,
      }),
    },
  );
}

export function deleteView(unitId: string, view: SavedView, csrfToken: string): Promise<void> {
  return apiRequestNoContent(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/saved-board-views/${encodeURIComponent(view.viewId)}`,
    {
      method: "DELETE",
      headers: jsonHeaders(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `delete-board-view-${crypto.randomUUID()}`,
        expectedVersion: view.version,
      }),
    },
  );
}

export function getPackageTemplates(unitId: string): Promise<TemplatePage> {
  return apiRequestJson(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/package-templates?limit=100`,
    { method: "GET" },
  );
}

export function savePackageTemplate(
  unitId: string,
  input: { name: string; packageTitles: string[]; estimatedMinutes?: number },
  grant: { id: string; version: number },
  csrfToken: string,
): Promise<PackageTemplate> {
  return apiRequestJson(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/package-templates`,
    {
      method: "PUT",
      headers: jsonHeaders(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `save-package-template-${crypto.randomUUID()}`,
        templateId: crypto.randomUUID(),
        expectedVersion: 0,
        authorisingGrantId: grant.id,
        expectedGrantVersion: grant.version,
        ...input,
      }),
    },
  );
}

export function deletePackageTemplate(
  unitId: string,
  template: PackageTemplate,
  grant: { id: string; version: number },
  csrfToken: string,
): Promise<void> {
  return apiRequestNoContent(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/package-templates/${encodeURIComponent(template.templateId)}`,
    {
      method: "DELETE",
      headers: jsonHeaders(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `delete-package-template-${crypto.randomUUID()}`,
        expectedVersion: template.version,
        authorisingGrantId: grant.id,
        expectedGrantVersion: grant.version,
      }),
    },
  );
}

export function getWorkUpdates(): Promise<WorkUpdatePage> {
  return apiRequestJson("/api/v1/organisation/work-updates?limit=20", { method: "GET" });
}

export function acknowledgeWorkUpdate(updateId: string, csrfToken: string): Promise<WorkUpdate> {
  return apiRequestJson(
    `/api/v1/organisation/work-updates/${encodeURIComponent(updateId)}/acknowledgements`,
    {
      method: "POST",
      headers: jsonHeaders(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `acknowledge-work-update-${crypto.randomUUID()}`,
      }),
    },
  );
}

export function getWorkUpdatePreferences(): Promise<Preferences> {
  return apiRequestJson("/api/v1/organisation/work-update-preferences", { method: "GET" });
}

export function saveWorkUpdatePreferences(
  preferences: Preferences,
  csrfToken: string,
): Promise<Preferences> {
  return apiRequestJson("/api/v1/organisation/work-update-preferences", {
    method: "PUT",
    headers: jsonHeaders(csrfToken),
    body: JSON.stringify({
      commandId: crypto.randomUUID(),
      idempotencyKey: `save-work-update-preferences-${crypto.randomUUID()}`,
      mode: preferences.mode,
      dueReminders: preferences.dueReminders,
      expectedVersion: preferences.version,
    }),
  });
}

export function getStoreLinks(
  unitId: string,
  sourceType: "ticket" | "work_package",
  sourceId: string,
): Promise<StoreLinkPage> {
  const query = new URLSearchParams({ sourceType, sourceId, limit: "100" });
  return apiRequestJson(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/store-links?${query}`,
    { method: "GET" },
  );
}

export function saveStoreLink(
  unitId: string,
  input: {
    sourceType: "ticket" | "work_package";
    sourceId: string;
    targetType: "project" | "product";
    targetId: string;
  },
  csrfToken: string,
): Promise<StoreLink> {
  return apiRequestJson(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/store-links`,
    {
      method: "PUT",
      headers: jsonHeaders(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `save-store-link-${crypto.randomUUID()}`,
        linkId: crypto.randomUUID(),
        expectedVersion: 0,
        ...input,
      }),
    },
  );
}

export function deleteStoreLink(unitId: string, link: StoreLink, csrfToken: string): Promise<void> {
  return apiRequestNoContent(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/store-links/${encodeURIComponent(link.linkId)}`,
    {
      method: "DELETE",
      headers: jsonHeaders(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `delete-store-link-${crypto.randomUUID()}`,
        expectedVersion: link.version,
      }),
    },
  );
}
