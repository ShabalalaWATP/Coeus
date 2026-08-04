import { apiRequestJson, ApiError } from "./client";
import type { components } from "./generated/openapi";

type ApiSchemas = components["schemas"];

export type OrganisationWorkspace = ApiSchemas["OrganisationWorkspaceResponse"];
export type OrganisationWorkspacePage = ApiSchemas["OrganisationWorkspaceListResponse"];

export async function listOrganisationWorkspaces(): Promise<OrganisationWorkspacePage | null> {
  try {
    return await apiRequestJson<OrganisationWorkspacePage>("/api/v1/organisation/workspaces", {
      method: "GET",
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) return null;
    throw error;
  }
}
