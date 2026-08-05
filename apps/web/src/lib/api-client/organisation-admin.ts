import { apiRequestJson } from "./client";
import type { components } from "./generated/openapi";

type ApiSchemas = components["schemas"];

export type OrganisationUnit = ApiSchemas["OrganisationUnitResponse"];
export type ManagementGrant = ApiSchemas["ManagementGrantResponse"];
export type OrganisationMutation = ApiSchemas["OrganisationMutationPayload"];
export type OrganisationMutationPreview = ApiSchemas["OrganisationMutationPreviewResponse"];
export type OrganisationMutationResult = ApiSchemas["OrganisationMutationResultResponse"];
export type OrganisationBootstrapRequest = ApiSchemas["OrganisationBootstrapRequest"];
export type OrganisationBootstrapResult = ApiSchemas["OrganisationBootstrapResponse"];
export type ReparentRequest = ApiSchemas["ReparentRequestPayload"];
export type ReparentPreview = ApiSchemas["ReparentPreviewResponse"];
export type ReparentResult = ApiSchemas["ReparentResultResponse"];
export type DeactivationRequest = ApiSchemas["DeactivationRequestPayload-Input"];
export type DeactivationPreview = ApiSchemas["DeactivationPreviewResponse"];
export type DeactivationResult = ApiSchemas["DeactivationResultResponse"];
export type ManagementAction = ApiSchemas["ManagementAction"];
export type ManagementGrantResult = ApiSchemas["ManagementGrantResultResponse"];
export type MembershipRecord = ApiSchemas["MembershipRecordResponse"];
export type MembershipRequest = ApiSchemas["MembershipRequestPayload-Input"];
export type MembershipPreview = ApiSchemas["MembershipPreviewResponse"];
export type MembershipResult = ApiSchemas["MembershipResultResponse"];
export type TransferRequest = ApiSchemas["TransferRequestPayload-Input"];
export type TransferPreview = ApiSchemas["TransferPreviewResponse"];
export type TransferResult = ApiSchemas["TransferResultResponse"];
export type MergeRequest = ApiSchemas["MergeRequestPayload"];
export type MergeImpact = ApiSchemas["MergeImpactResponse"];
export type MergePlan = ApiSchemas["MergePlanPayload"];
export type MergePreview = ApiSchemas["MergePreviewResponse"];
export type MergeResult = ApiSchemas["MergeResultResponse"];
export type SplitRequest = ApiSchemas["SplitRequestPayload"];
export type SplitImpact = ApiSchemas["SplitImpactResponse"];
export type SplitPlan = ApiSchemas["SplitPlanPayload"];
export type SplitPreview = ApiSchemas["SplitPreviewResponse"];
export type SplitResult = ApiSchemas["SplitResultResponse"];
export type SyntheticFixturePreview = ApiSchemas["SyntheticFixturePreviewResponse"];
export type SyntheticFixtureResult = ApiSchemas["SyntheticFixtureResultResponse"];

export async function listOrganisationUnits(parentId?: string): Promise<OrganisationUnit[]> {
  const query = parentId === undefined ? "" : `?parentId=${encodeURIComponent(parentId)}`;
  const response = await apiRequestJson<ApiSchemas["OrganisationUnitListResponse"]>(
    `/api/v1/admin/organisation/units${query}`,
    { method: "GET" },
  );
  return response.units;
}

export function getOrganisationUnit(unitId: string): Promise<OrganisationUnit> {
  return apiRequestJson<OrganisationUnit>(
    `/api/v1/admin/organisation/units/${encodeURIComponent(unitId)}`,
    { method: "GET" },
  );
}

export async function listManagementGrants(rootUnitId?: string): Promise<ManagementGrant[]> {
  const query = new URLSearchParams({ includeInactive: "true" });
  if (rootUnitId !== undefined) query.set("rootUnitId", rootUnitId);
  const response = await apiRequestJson<ApiSchemas["ManagementGrantListResponse"]>(
    `/api/v1/admin/organisation/grants?${query.toString()}`,
    { method: "GET" },
  );
  return response.grants;
}

export function createManagementGrant(
  request: Omit<
    ApiSchemas["CreateManagementGrantPayload"],
    "commandId" | "grantId" | "idempotencyKey"
  >,
  csrfToken: string,
): Promise<ManagementGrantResult> {
  const commandId = crypto.randomUUID();
  return postOrganisationCommand<ManagementGrantResult>(
    "grants",
    {
      ...request,
      commandId,
      grantId: crypto.randomUUID(),
      idempotencyKey: `organisation-grant-${commandId}`,
    },
    csrfToken,
  );
}

export function revokeManagementGrant(
  grant: Pick<ManagementGrant, "id" | "version">,
  reason: string,
  csrfToken: string,
): Promise<ManagementGrantResult> {
  const commandId = crypto.randomUUID();
  return postOrganisationCommand<ManagementGrantResult>(
    `grants/${encodeURIComponent(grant.id)}/revoke`,
    {
      commandId,
      idempotencyKey: `organisation-grant-revoke-${commandId}`,
      expectedVersion: grant.version,
      reason,
    },
    csrfToken,
  );
}

export async function listUnitMemberships(unitId: string): Promise<MembershipRecord[]> {
  const response = await apiRequestJson<ApiSchemas["MembershipListResponse"]>(
    `/api/v1/admin/organisation/units/${encodeURIComponent(unitId)}/memberships`,
    { method: "GET" },
  );
  return response.memberships;
}

export async function listUserMemberships(userId: string): Promise<MembershipRecord[]> {
  const response = await apiRequestJson<ApiSchemas["MembershipListResponse"]>(
    `/api/v1/admin/organisation/users/${encodeURIComponent(userId)}/memberships`,
    { method: "GET" },
  );
  return response.memberships;
}

export function previewMembership(
  request: MembershipRequest,
  csrfToken: string,
): Promise<MembershipPreview> {
  return postOrganisationCommand("membership-previews", request, csrfToken);
}

export function executeMembership(
  request: MembershipRequest,
  previewHash: string,
  csrfToken: string,
): Promise<MembershipResult> {
  return executeStructureCommand("membership-commands", request, previewHash, csrfToken);
}

export function previewTransfer(
  request: TransferRequest,
  csrfToken: string,
): Promise<TransferPreview> {
  return postOrganisationCommand("transfer-previews", request, csrfToken);
}

export function executeTransfer(
  request: TransferRequest,
  previewHash: string,
  csrfToken: string,
): Promise<TransferResult> {
  return executeStructureCommand("transfer-commands", request, previewHash, csrfToken);
}

export function assessMerge(request: MergeRequest, csrfToken: string): Promise<MergeImpact> {
  return postOrganisationCommand("merge-assessments", request, csrfToken);
}

export function previewMerge(plan: MergePlan, csrfToken: string): Promise<MergePreview> {
  return postOrganisationCommand("merge-previews", plan, csrfToken);
}

export function executeMerge(
  plan: MergePlan,
  previewHash: string,
  csrfToken: string,
): Promise<MergeResult> {
  const commandId = crypto.randomUUID();
  return postOrganisationCommand(
    "merge-commands",
    {
      commandId,
      idempotencyKey: `organisation-merge-${commandId}`,
      plan,
      previewHash,
    },
    csrfToken,
  );
}

export function assessSplit(request: SplitRequest, csrfToken: string): Promise<SplitImpact> {
  return postOrganisationCommand("split-assessments", request, csrfToken);
}

export function previewSplit(plan: SplitPlan, csrfToken: string): Promise<SplitPreview> {
  return postOrganisationCommand("split-previews", plan, csrfToken);
}

export function executeSplit(
  plan: SplitPlan,
  previewHash: string,
  csrfToken: string,
): Promise<SplitResult> {
  const commandId = crypto.randomUUID();
  return postOrganisationCommand(
    "split-commands",
    {
      commandId,
      idempotencyKey: `organisation-split-${commandId}`,
      plan,
      previewHash,
    },
    csrfToken,
  );
}

export function previewOrganisationMutation(
  mutation: OrganisationMutation,
  csrfToken: string,
): Promise<OrganisationMutationPreview> {
  return apiRequestJson<OrganisationMutationPreview>("/api/v1/admin/organisation/unit-previews", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify(mutation),
  });
}

export function executeOrganisationMutation(
  mutation: OrganisationMutation,
  previewHash: string,
  csrfToken: string,
): Promise<OrganisationMutationResult> {
  const commandId = crypto.randomUUID();
  return apiRequestJson<OrganisationMutationResult>("/api/v1/admin/organisation/unit-commands", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({
      commandId,
      idempotencyKey: `organisation-unit-${commandId}`,
      previewHash,
      request: mutation,
    }),
  });
}

export function bootstrapOrganisation(
  request: Omit<OrganisationBootstrapRequest, "commandId" | "rootUnitId">,
  csrfToken: string,
): Promise<OrganisationBootstrapResult> {
  return apiRequestJson<OrganisationBootstrapResult>("/api/v1/admin/organisation/bootstrap", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({
      ...request,
      commandId: crypto.randomUUID(),
      rootUnitId: crypto.randomUUID(),
    }),
  });
}

export function previewSyntheticOrganisationFixture(
  csrfToken: string,
): Promise<SyntheticFixturePreview> {
  return postOrganisationCommand("synthetic-fixture-preview", {}, csrfToken);
}

export function applySyntheticOrganisationFixture(
  previewHash: string,
  currentPassword: string,
  csrfToken: string,
): Promise<SyntheticFixtureResult> {
  const commandId = crypto.randomUUID();
  return postOrganisationCommand(
    "synthetic-fixture-commands",
    {
      commandId,
      idempotencyKey: `synthetic-organisation-fixture-${commandId}`,
      previewHash,
      currentPassword,
    },
    csrfToken,
  );
}

export function reconcileSyntheticOrganisationFixture(
  previewHash: string,
  currentPassword: string,
  csrfToken: string,
): Promise<SyntheticFixtureResult> {
  const commandId = crypto.randomUUID();
  return postOrganisationCommand(
    "synthetic-fixture-reconcile-commands",
    {
      commandId,
      idempotencyKey: `synthetic-organisation-reconcile-${commandId}`,
      previewHash,
      currentPassword,
    },
    csrfToken,
  );
}

export function previewReparent(
  request: ReparentRequest,
  csrfToken: string,
): Promise<ReparentPreview> {
  return postOrganisationCommand("reparent-previews", request, csrfToken);
}

export function executeReparent(
  request: ReparentRequest,
  previewHash: string,
  csrfToken: string,
): Promise<ReparentResult> {
  return executeStructureCommand("reparent-commands", request, previewHash, csrfToken);
}

export function previewDeactivation(
  request: DeactivationRequest,
  csrfToken: string,
): Promise<DeactivationPreview> {
  return postOrganisationCommand("deactivation-previews", request, csrfToken);
}

export function executeDeactivation(
  request: DeactivationRequest,
  previewHash: string,
  csrfToken: string,
): Promise<DeactivationResult> {
  return executeStructureCommand("deactivation-commands", request, previewHash, csrfToken);
}

function postOrganisationCommand<TResponse>(
  path: string,
  body: object,
  csrfToken: string,
): Promise<TResponse> {
  return apiRequestJson<TResponse>(`/api/v1/admin/organisation/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify(body),
  });
}

function executeStructureCommand<TRequest extends object, TResponse>(
  path: string,
  request: TRequest,
  previewHash: string,
  csrfToken: string,
): Promise<TResponse> {
  const commandId = crypto.randomUUID();
  return postOrganisationCommand<TResponse>(
    path,
    {
      commandId,
      idempotencyKey: `organisation-structure-${commandId}`,
      previewHash,
      request,
    },
    csrfToken,
  );
}
