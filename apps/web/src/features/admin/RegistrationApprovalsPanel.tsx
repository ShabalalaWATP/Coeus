import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserCheck, UserX } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState } from "../../components/ui/PageState";
import {
  approveRegistration,
  listPendingRegistrations,
  rejectRegistration,
  type PendingRegistration,
} from "../../lib/api-client/registration";

type RegistrationApprovalsPanelProps = {
  csrfToken: string;
};

export function RegistrationApprovalsPanel({ csrfToken }: RegistrationApprovalsPanelProps) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const registrationsQuery = useQuery({
    queryKey: ["registrations"],
    queryFn: listPendingRegistrations,
  });
  const registrations = registrationsQuery.data?.registrations ?? [];
  const removeRegistration = (registration: PendingRegistration) => {
    setActionError(null);
    queryClient.setQueryData<{ registrations: PendingRegistration[] }>(["registrations"], {
      registrations: registrations.filter((item) => item.id !== registration.id),
    });
  };
  const failAction = () =>
    setActionError("The decision could not be applied. Refresh and try again.");
  const approveMutation = useMutation({
    mutationFn: (registrationId: string) => approveRegistration(registrationId, csrfToken),
    onSuccess: removeRegistration,
    onError: failAction,
  });
  const rejectMutation = useMutation({
    mutationFn: ({ registrationId, reason }: { registrationId: string; reason: string }) =>
      rejectRegistration(registrationId, reason, csrfToken),
    onSuccess: removeRegistration,
    onError: failAction,
  });

  return (
    <section className="surface approvals-panel" aria-labelledby="approvals-title">
      <div className="section-heading">
        <h2 id="approvals-title">Access requests</h2>
        <p>Approve or reject self-service registration requests.</p>
      </div>
      {registrationsQuery.isError ? (
        <ErrorState onRetry={() => void registrationsQuery.refetch()} />
      ) : registrations.length === 0 ? (
        <EmptyState
          hint="New requests from the sign-in page appear here for review."
          title="No pending access requests"
        />
      ) : (
        <>
          <div className="stack-list">
            {registrations.map((registration) => (
              <RegistrationRow
                actionPending={approveMutation.isPending || rejectMutation.isPending}
                key={registration.id}
                onApprove={() => approveMutation.mutate(registration.id)}
                onReject={(reason) =>
                  rejectMutation.mutate({ registrationId: registration.id, reason })
                }
                registration={registration}
              />
            ))}
          </div>
        </>
      )}
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}

function RegistrationRow({
  actionPending,
  onApprove,
  onReject,
  registration,
}: {
  actionPending: boolean;
  onApprove: () => void;
  onReject: (reason: string) => void;
  registration: PendingRegistration;
}) {
  const [reason, setReason] = useState("");
  return (
    <article className="approvals-row">
      <div>
        <strong>{registration.displayName}</strong>
        <span>{registration.username}</span>
        {registration.justification ? <p>{registration.justification}</p> : null}
      </div>
      <label className="approvals-reason">
        Rejection reason for {registration.displayName}
        <input
          aria-label={`Rejection reason for ${registration.displayName}`}
          disabled={actionPending}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Required before rejecting"
          value={reason}
        />
      </label>
      <div className="approvals-actions">
        <button disabled={actionPending} onClick={onApprove} type="button">
          <UserCheck aria-hidden="true" size={16} /> Approve
        </button>
        <button
          className="approvals-reject"
          disabled={actionPending || reason.trim().length < 3}
          onClick={() => onReject(reason.trim())}
          type="button"
        >
          <UserX aria-hidden="true" size={16} /> Reject
        </button>
      </div>
    </article>
  );
}
