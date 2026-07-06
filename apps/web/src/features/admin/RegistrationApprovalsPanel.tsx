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
  const [rejectReason, setRejectReason] = useState("");
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
    mutationFn: (registrationId: string) =>
      rejectRegistration(registrationId, rejectReason, csrfToken),
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
          <label className="approvals-reason">
            Rejection reason
            <input
              onChange={(event) => setRejectReason(event.target.value)}
              placeholder="Required before rejecting"
              value={rejectReason}
            />
          </label>
          <div className="stack-list">
            {registrations.map((registration) => (
              <article className="approvals-row" key={registration.id}>
                <div>
                  <strong>{registration.displayName}</strong>
                  <span>{registration.username}</span>
                  {registration.justification ? <p>{registration.justification}</p> : null}
                </div>
                <div className="approvals-actions">
                  <button
                    disabled={approveMutation.isPending}
                    onClick={() => approveMutation.mutate(registration.id)}
                    type="button"
                  >
                    <UserCheck aria-hidden="true" size={16} />
                    Approve
                  </button>
                  <button
                    className="approvals-reject"
                    disabled={rejectMutation.isPending || rejectReason.trim().length < 3}
                    onClick={() => rejectMutation.mutate(registration.id)}
                    type="button"
                  >
                    <UserX aria-hidden="true" size={16} />
                    Reject
                  </button>
                </div>
              </article>
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
