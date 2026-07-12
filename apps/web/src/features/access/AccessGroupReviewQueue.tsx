import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  decideAccessGroupApplication,
  type AccessGroupApplication,
} from "../../lib/api-client/access-groups";
import { actionErrorMessage } from "../../lib/mutations/action-error";

export function AccessGroupReviewQueue({
  applications,
  csrfToken,
  currentUserId,
  onDecisionSuccess,
}: {
  applications: AccessGroupApplication[];
  csrfToken: string;
  currentUserId: string;
  onDecisionSuccess: (message: string) => void;
}) {
  return (
    <section className="surface access-group-reviews" aria-labelledby="access-group-reviews-title">
      <h2 id="access-group-reviews-title">Applications to review</h2>
      <p>Only applications for groups you administer appear here.</p>
      {applications.map((application) => (
        <ApplicationReviewRow
          application={application}
          csrfToken={csrfToken}
          currentUserId={currentUserId}
          key={application.id}
          onDecisionSuccess={onDecisionSuccess}
        />
      ))}
    </section>
  );
}

function ApplicationReviewRow({
  application,
  csrfToken,
  currentUserId,
  onDecisionSuccess,
}: {
  application: AccessGroupApplication;
  csrfToken: string;
  currentUserId: string;
  onDecisionSuccess: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const decisionMutation = useMutation({
    mutationFn: (decision: "approve" | "reject") =>
      decideAccessGroupApplication(application, decision, reason.trim(), csrfToken),
    onMutate: () => setMessage(null),
    onError: (error) =>
      setMessage(actionErrorMessage(error, "The application decision could not be recorded.")),
    onSuccess: async (_, decision) => {
      setReason("");
      onDecisionSuccess(
        `${application.applicantDisplayName}'s application was ${decision === "approve" ? "approved" : "rejected"}.`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["access-group-applications"] }),
        queryClient.invalidateQueries({ queryKey: ["access-groups"] }),
      ]);
    },
  });
  const selfDecision = application.applicantUserId === currentUserId;
  return (
    <article className="access-group-review-row">
      <div>
        <strong>{application.applicantDisplayName}</strong>
        <span>{application.acgName}</span>
        <p>{application.justification}</p>
      </div>
      <label>
        Rejection reason for {application.applicantDisplayName}
        <input
          disabled={decisionMutation.isPending || selfDecision}
          maxLength={500}
          onChange={(event) => setReason(event.target.value)}
          value={reason}
        />
      </label>
      <div>
        <button
          disabled={decisionMutation.isPending || selfDecision}
          onClick={() => {
            if (
              window.confirm(
                `Approve ${application.applicantDisplayName} for ${application.acgName}?`,
              )
            ) {
              decisionMutation.mutate("approve");
            }
          }}
          type="button"
        >
          Approve
        </button>
        <button
          disabled={decisionMutation.isPending || selfDecision || reason.trim().length < 3}
          onClick={() => {
            if (
              window.confirm(
                `Reject ${application.applicantDisplayName}'s application to ${application.acgName}?`,
              )
            ) {
              decisionMutation.mutate("reject");
            }
          }}
          type="button"
        >
          Reject
        </button>
      </div>
      {selfDecision ? <p>You cannot decide your own application.</p> : null}
      {message ? <p role="alert">{message}</p> : null}
    </article>
  );
}
