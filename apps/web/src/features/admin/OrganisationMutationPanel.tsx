import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, X } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { useAuth } from "../../lib/auth/auth-context";
import {
  executeOrganisationMutation,
  listManagementGrants,
  previewOrganisationMutation,
  type OrganisationMutation,
  type OrganisationMutationPreview,
  type OrganisationUnit,
} from "../../lib/api-client/organisation-admin";

type MutationMode = "create" | "edit";

type OrganisationMutationPanelProps = {
  mode: MutationMode;
  onClose: () => void;
  parent?: OrganisationUnit;
  unit?: OrganisationUnit;
};

export function OrganisationMutationPanel({
  mode,
  onClose,
  parent,
  unit,
}: OrganisationMutationPanelProps) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [unitId] = useState(() => unit?.id ?? crypto.randomUUID());
  const [name, setName] = useState(unit?.name ?? "");
  const [shortName, setShortName] = useState(unit?.shortName ?? "");
  const [category, setCategory] = useState(unit?.category ?? "delivery_team");
  const [timeZone, setTimeZone] = useState(unit?.timeZone ?? parent?.timeZone ?? "Europe/London");
  const [description, setDescription] = useState(unit?.description ?? "");
  const [reason, setReason] = useState("");
  const [grantId, setGrantId] = useState("");
  const [previewed, setPreviewed] = useState<{
    impact: OrganisationMutationPreview;
    mutation: OrganisationMutation;
  }>();
  const grants = useQuery({
    queryKey: ["organisation-grants", "all-active"],
    queryFn: () => listManagementGrants(),
  });
  const applicableGrants = useMemo(
    () =>
      grants.data?.filter(
        (grant) => grant.revokedAt === null && grant.action === `organisation:${mode}`,
      ) ?? [],
    [grants.data, mode],
  );
  const operation = useMutation({
    mutationFn: async (input: { mutation: OrganisationMutation; previewHash?: string }) =>
      input.previewHash === undefined
        ? previewOrganisationMutation(input.mutation, session?.csrfToken ?? "")
        : executeOrganisationMutation(input.mutation, input.previewHash, session?.csrfToken ?? ""),
  });

  const buildMutation = (): OrganisationMutation => ({
    operation: mode,
    unitId,
    parentId: mode === "create" ? (parent?.id ?? null) : null,
    expectedVersion: mode === "create" ? (parent?.version ?? 1) : (unit?.version ?? 1),
    name: name.trim(),
    shortName: shortName.trim(),
    category,
    timeZone: timeZone.trim(),
    description: description.trim(),
    authorisingGrantId: grantId,
    reason: reason.trim(),
  });

  const requestPreview = (event: FormEvent) => {
    event.preventDefault();
    operation.mutate(
      { mutation: buildMutation() },
      {
        onSuccess: (result, variables) =>
          setPreviewed({
            impact: result as OrganisationMutationPreview,
            mutation: variables.mutation,
          }),
      },
    );
  };

  const confirm = () => {
    if (previewed === undefined) return;
    operation.mutate(
      { mutation: previewed.mutation, previewHash: previewed.impact.previewHash },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: ["organisation-units"] });
          onClose();
        },
      },
    );
  };

  return (
    <section className="organisation-mutation" aria-labelledby="organisation-mutation-title">
      <header>
        <div>
          <span className="eyebrow">Preview required</span>
          <h2 id="organisation-mutation-title">
            {mode === "create"
              ? `Add a unit below ${parent?.shortName}`
              : `Edit ${unit?.shortName}`}
          </h2>
        </div>
        <button aria-label="Close organisation change" onClick={onClose} type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </header>

      <form onSubmit={requestPreview}>
        <label>
          Name
          <input
            disabled={previewed !== undefined}
            maxLength={120}
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
        </label>
        <label>
          Short name
          <input
            disabled={previewed !== undefined}
            maxLength={32}
            onChange={(event) => setShortName(event.target.value)}
            required
            value={shortName}
          />
        </label>
        <label>
          Unit type
          <select
            disabled={mode === "edit" || previewed !== undefined}
            onChange={(event) => setCategory(event.target.value as typeof category)}
            value={category}
          >
            <option value="command">Command</option>
            <option value="branch">Branch</option>
            <option value="customer_team">Customer team</option>
            <option value="delivery_team">Delivery team</option>
            <option value="governance_team">Governance team</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Time zone
          <input
            disabled={previewed !== undefined}
            maxLength={64}
            onChange={(event) => setTimeZone(event.target.value)}
            required
            value={timeZone}
          />
        </label>
        <label className="organisation-mutation__wide">
          Description
          <textarea
            disabled={previewed !== undefined}
            maxLength={1000}
            onChange={(event) => setDescription(event.target.value)}
            value={description}
          />
        </label>
        <label>
          Authorising grant
          <select
            disabled={previewed !== undefined}
            onChange={(event) => setGrantId(event.target.value)}
            required
            value={grantId}
          >
            <option value="">Select a grant</option>
            {applicableGrants.map((grant) => (
              <option key={grant.id} value={grant.id}>
                {grant.includeDescendants ? "Descendant authority" : "Direct authority"} · granted{" "}
                {new Date(grant.validFrom).toLocaleDateString("en-GB")}
              </option>
            ))}
          </select>
        </label>
        <label>
          Reason
          <input
            disabled={previewed !== undefined}
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            required
            value={reason}
          />
        </label>
        {grants.isSuccess && applicableGrants.length === 0 ? (
          <p className="organisation-mutation__warning" role="alert">
            <AlertTriangle aria-hidden="true" size={17} />
            No active {mode} grant is available to this account.
          </p>
        ) : null}
        {operation.isError ? <p role="alert">{operation.error.message}</p> : null}
        <button
          disabled={operation.isPending || applicableGrants.length === 0 || previewed !== undefined}
          type="submit"
        >
          Review impact
        </button>
      </form>

      {previewed ? (
        <div className="organisation-mutation__preview" role="status">
          <div>
            <Check aria-hidden="true" size={18} />
            <strong>Impact checked</strong>
          </div>
          <p>
            {previewed.impact.affectedDescendants} descendants,{" "}
            {previewed.impact.affectedMemberships} memberships, {previewed.impact.affectedGrants}{" "}
            grants and {previewed.impact.affectedTaskLegs} task legs are affected.
          </p>
          <button disabled={operation.isPending} onClick={confirm} type="button">
            Confirm {mode === "create" ? "creation" : "changes"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
