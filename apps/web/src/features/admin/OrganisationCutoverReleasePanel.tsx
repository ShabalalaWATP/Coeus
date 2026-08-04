import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleX, Eye, KeyRound, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { CutoverManifestEditor } from "./CutoverManifestEditor";
import { EMPTY_CUTOVER_MANIFEST, isCompleteManifest } from "./cutover-manifest";
import {
  approveCutoverSlice,
  CUTOVER_SLICES,
  getCutoverRelease,
  previewCutoverSlice,
  type CutoverApprovalRole,
  type CutoverManifest,
  type CutoverSlice,
  type CutoverSliceState,
} from "../../lib/api-client/cutover-release";
import { useAuth } from "../../lib/auth/auth-context";

const SLICE_LABELS: Record<CutoverSlice, string> = {
  organisation: "Organisation and authority",
  calendar: "Calendars and availability",
  task_capacity: "Tasks and capacity",
};
const ROLE_LABELS: Record<CutoverApprovalRole, string> = {
  security_review: "Security reviewer",
  release_authority: "Release authority",
};
const APPROVAL_ROLES = ["security_review", "release_authority"] as const;

type ApprovalSelection = { slice: CutoverSlice; role: CutoverApprovalRole };

export function OrganisationCutoverReleasePanel() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [manifest, setManifest] = useState<CutoverManifest>(EMPTY_CUTOVER_MANIFEST);
  const [approval, setApproval] = useState<ApprovalSelection>();
  const [currentPassword, setCurrentPassword] = useState("");
  const query = useQuery({
    queryKey: ["organisation-cutover-release"],
    queryFn: getCutoverRelease,
    retry: false,
  });

  useEffect(() => {
    if (query.data?.manifest) setManifest(query.data.manifest);
  }, [query.data?.manifest]);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["organisation-cutover-release"] });
    await queryClient.invalidateQueries({ queryKey: ["organisation-cutover-readiness"] });
  };
  const preview = useMutation({
    mutationFn: (slice: CutoverSlice) =>
      previewCutoverSlice(slice, manifest, session?.csrfToken ?? ""),
    onSuccess: refresh,
  });
  const approve = useMutation({
    mutationFn: (selection: ApprovalSelection) => {
      const slice = query.data?.slices.find((item) => item.slice === selection.slice);
      if (!query.data?.candidateDigest || !slice?.previewDigest) {
        throw new Error("The exact candidate preview is no longer available.");
      }
      return approveCutoverSlice(
        {
          slice: selection.slice,
          candidateDigest: query.data.candidateDigest,
          previewDigest: slice.previewDigest,
          approvalRole: selection.role,
          currentPassword,
        },
        session?.csrfToken ?? "",
      );
    },
    onSettled: () => setCurrentPassword(""),
    onSuccess: async () => {
      setApproval(undefined);
      await refresh();
    },
  });

  if (query.isPending) {
    return (
      <section className="cutover-release" aria-busy="true">
        Loading release controls…
      </section>
    );
  }
  if (query.isError) {
    return (
      <section className="cutover-release cutover-release--blocked" aria-labelledby="release-title">
        <header>
          <CircleX aria-hidden="true" size={22} />
          <div>
            <span className="eyebrow">Controlled release</span>
            <h2 id="release-title">Release status could not be verified</h2>
            <p>All cutover actions are blocked. Current services remain authoritative.</p>
          </div>
          <button onClick={() => void query.refetch()} type="button">
            <RefreshCw aria-hidden="true" size={16} /> Retry
          </button>
        </header>
      </section>
    );
  }

  const actorId = session?.user.id;
  const hasCandidate = Boolean(query.data.candidateDigest && query.data.manifest);
  return (
    <section className="cutover-release" aria-labelledby="release-title">
      <header>
        <ShieldCheck aria-hidden="true" size={23} />
        <div>
          <span className="eyebrow">Controlled release</span>
          <h2 id="release-title">
            {query.data.eligible
              ? "Release is active and verified"
              : "Release activation is blocked"}
          </h2>
          <p>
            {hasCandidate
              ? "Each bounded service is previewed and independently approved against this exact candidate."
              : "No release candidate has been recorded. Enter immutable evidence, then preview each service."}
          </p>
        </div>
        <span className={`cutover-release__state ${query.data.eligible ? "is-active" : ""}`}>
          {query.data.eligible ? "Active" : "No activation"}
        </span>
      </header>

      <div className="cutover-release__guardrail">
        <KeyRound aria-hidden="true" size={19} />
        <p>
          <strong>Four-person separation of duties applies.</strong> The proposer, security
          reviewer, release authority and executor must be different people. Approval requires your
          current password. This page never activates a service.
        </p>
      </div>

      {query.data.candidateDigest ? (
        <p className="cutover-release__candidate">
          Exact candidate <code>{query.data.candidateDigest}</code>
        </p>
      ) : null}
      <CutoverManifestEditor locked={hasCandidate} onChange={setManifest} value={manifest} />

      <div className="cutover-release__slices" aria-label="Cutover service status">
        {CUTOVER_SLICES.map((sliceName) => {
          const slice = query.data.slices.find((item) => item.slice === sliceName);
          if (!slice) return null;
          return (
            <SliceCard
              actorId={actorId}
              approval={approval}
              approvalError={approve.isError ? approve.error.message : undefined}
              currentPassword={currentPassword}
              key={sliceName}
              manifestReady={isCompleteManifest(manifest)}
              onApprove={(event) => {
                event.preventDefault();
                if (approval) approve.mutate(approval);
              }}
              onPassword={setCurrentPassword}
              onPreview={() => preview.mutate(sliceName)}
              onSelectApproval={setApproval}
              pendingApproval={approve.isPending}
              pendingPreview={preview.isPending && preview.variables === sliceName}
              previewError={preview.isError ? preview.error.message : undefined}
              selected={approval?.slice === sliceName ? approval : undefined}
              slice={slice}
            />
          );
        })}
      </div>
    </section>
  );
}

type SliceCardProps = {
  actorId?: string;
  approval?: ApprovalSelection;
  approvalError?: string;
  currentPassword: string;
  manifestReady: boolean;
  onApprove: (event: FormEvent) => void;
  onPassword: (value: string) => void;
  onPreview: () => void;
  onSelectApproval: (value: ApprovalSelection | undefined) => void;
  pendingApproval: boolean;
  pendingPreview: boolean;
  previewError?: string;
  selected?: ApprovalSelection;
  slice: CutoverSliceState;
};

function SliceCard(props: SliceCardProps) {
  const { slice } = props;
  const actorParticipated =
    slice.proposedByUserId === props.actorId ||
    slice.approvals.some((item) => item.approvedByUserId === props.actorId);
  const canPreview =
    props.manifestReady && slice.status !== "active" && slice.approvals.length === 0;

  return (
    <article className={`cutover-release__slice is-${slice.status}`}>
      <header>
        <div>
          <span>{formatStatus(slice.status)}</span>
          <h3>{SLICE_LABELS[slice.slice]}</h3>
        </div>
        {slice.status === "active" ? <CheckCircle2 aria-label="Active" size={21} /> : null}
      </header>
      <ol aria-label={`${SLICE_LABELS[slice.slice]} release stages`}>
        <li className={slice.previewDigest ? "is-complete" : ""}>Impact preview</li>
        {APPROVAL_ROLES.map((role) => {
          const evidence = slice.approvals.find((item) => item.approvalRole === role);
          return (
            <li className={evidence ? "is-complete" : ""} key={role}>
              {ROLE_LABELS[role]} {evidence ? "approved" : "required"}
            </li>
          );
        })}
        <li className={slice.status === "active" ? "is-complete" : ""}>Separate activation</li>
      </ol>

      {!slice.previewDigest || (slice.status === "previewed" && slice.approvals.length === 0) ? (
        <button
          disabled={!canPreview || props.pendingPreview}
          onClick={props.onPreview}
          type="button"
        >
          <Eye aria-hidden="true" size={16} />
          {props.pendingPreview
            ? "Checking impact…"
            : slice.previewDigest
              ? "Refresh preview"
              : "Preview impact"}
        </button>
      ) : null}

      {slice.previewDigest && slice.status !== "active" ? (
        <div className="cutover-release__approvals">
          {actorParticipated ? (
            <p>
              You already participated in this slice. Another authorised administrator must
              continue.
            </p>
          ) : (
            APPROVAL_ROLES.filter(
              (role) => !slice.approvals.some((item) => item.approvalRole === role),
            ).map((role) => (
              <button
                key={role}
                onClick={() => props.onSelectApproval({ slice: slice.slice, role })}
                type="button"
              >
                Approve as {ROLE_LABELS[role].toLowerCase()}
              </button>
            ))
          )}
        </div>
      ) : null}

      {props.selected ? (
        <form className="cutover-release__reauth" onSubmit={props.onApprove}>
          <p>
            Confirm the exact preview as <strong>{ROLE_LABELS[props.selected.role]}</strong>.
          </p>
          <label>
            Current password
            <input
              autoComplete="current-password"
              autoFocus
              onChange={(event) => props.onPassword(event.target.value)}
              required
              type="password"
              value={props.currentPassword}
            />
          </label>
          <div>
            <button disabled={props.pendingApproval} type="submit">
              {props.pendingApproval ? "Verifying…" : "Confirm approval"}
            </button>
            <button onClick={() => props.onSelectApproval(undefined)} type="button">
              Cancel
            </button>
          </div>
        </form>
      ) : null}
      {props.previewError ? <p role="alert">Preview failed: {props.previewError}</p> : null}
      {props.selected && props.approvalError ? (
        <p role="alert">Approval failed: {props.approvalError}</p>
      ) : null}
    </article>
  );
}

function formatStatus(status: CutoverSliceState["status"]): string {
  return status
    .replace("not_previewed", "Not previewed")
    .replace("previewed", "Previewed")
    .replace("approved", "Approved")
    .replace("active", "Active");
}
