import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Send, Star } from "lucide-react";
import { useState } from "react";

import {
  listFeedbackRequests,
  submitFeedback,
  type FeedbackRequest,
} from "../../lib/api-client/analytics";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

const EMPTY_FEEDBACK: FeedbackRequest[] = [];

type FeedbackPanelProps = {
  csrfToken: string;
};

export function FeedbackPanel({ csrfToken }: FeedbackPanelProps) {
  const { session } = useAuth();
  const canSubmitFeedback = session?.user.permissions.includes("feedback:create") ?? false;
  const feedbackQuery = useQuery({
    queryKey: ["feedback-requests"],
    queryFn: listFeedbackRequests,
    enabled: canSubmitFeedback,
    placeholderData: EMPTY_FEEDBACK,
    refetchInterval: 25_000,
    retry: false,
  });
  const requests = feedbackQuery.data ?? EMPTY_FEEDBACK;
  const pendingRequests = requests.filter((request) => request.status === "requested");
  const [submittedProduct, setSubmittedProduct] = useState<string | null>(null);

  if (!canSubmitFeedback) {
    return null;
  }

  if (!feedbackQuery.isError && pendingRequests.length === 0 && submittedProduct === null) {
    return null;
  }

  return (
    <section className="surface feedback-panel" aria-labelledby="feedback-title">
      <div className="feedback-panel__heading">
        <Star aria-hidden="true" size={20} />
        <div>
          <h2 id="feedback-title">Feedback on a closed request</h2>
          <p>Help the team understand whether the completed product answered your request.</p>
        </div>
      </div>
      {feedbackQuery.isError ? (
        <div className="workspace-alert" role="alert">
          <span>Feedback requests could not be loaded.</span>
          <button onClick={() => void feedbackQuery.refetch()} type="button">
            Retry feedback
          </button>
        </div>
      ) : null}
      {submittedProduct ? (
        <p className="feedback-panel__confirmation" role="status">
          <CheckCircle2 aria-hidden="true" size={18} />
          Feedback sent for {submittedProduct}.
        </p>
      ) : null}
      {!feedbackQuery.isError && pendingRequests[0] ? (
        <FeedbackRequestRow
          csrfToken={csrfToken}
          onSubmitted={setSubmittedProduct}
          pendingCount={pendingRequests.length}
          request={pendingRequests[0]}
        />
      ) : null}
    </section>
  );
}

type FeedbackRequestRowProps = FeedbackPanelProps & {
  onSubmitted: (productTitle: string) => void;
  pendingCount: number;
  request: FeedbackRequest;
};

const OUTCOME_OPTIONS = [
  { rating: 5, label: "Yes, fully", hint: "It answered the request." },
  { rating: 3, label: "Partly", hint: "It helped, but gaps remained." },
  { rating: 1, label: "No", hint: "It did not answer the request." },
] as const;

function FeedbackRequestRow({
  csrfToken,
  onSubmitted,
  pendingCount,
  request,
}: FeedbackRequestRowProps) {
  const queryClient = useQueryClient();
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const submitMutation = useMutation({
    onError: failActionWith("The feedback could not be submitted. Try again."),
    onMutate: clearActionError,
    mutationFn: () =>
      submitFeedback(
        request.id,
        { rating: rating ?? 0, comment, followUpRequested: false },
        csrfToken,
      ),
    onSuccess: (updated) => {
      onSubmitted(updated.productTitle);
      queryClient.setQueryData<FeedbackRequest[]>(["feedback-requests"], (current) =>
        (current ?? EMPTY_FEEDBACK).map((item) => (item.id === updated.id ? updated : item)),
      );
    },
  });

  return (
    <article className="feedback-row">
      <div className="feedback-row__context">
        <span className="mono-ref">{request.ticketReference}</span>
        {pendingCount > 1 ? (
          <small>{pendingCount} completed requests awaiting feedback</small>
        ) : null}
      </div>
      <strong>{request.productTitle}</strong>
      <form
        aria-label={`Feedback for ${request.productTitle}`}
        className="feedback-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (rating !== null) submitMutation.mutate();
        }}
      >
        <fieldset disabled={submitMutation.isPending}>
          <legend>Did the delivered product answer your request?</legend>
          <div className="feedback-outcomes">
            {OUTCOME_OPTIONS.map((option) => (
              <label key={option.rating}>
                <input
                  checked={rating === option.rating}
                  name={`feedback-outcome-${request.id}`}
                  onChange={() => setRating(option.rating)}
                  type="radio"
                  value={option.rating}
                />
                <strong>{option.label}</strong>
                <small>{option.hint}</small>
              </label>
            ))}
          </div>
        </fieldset>
        <label className="feedback-comment">
          <span>
            Add context <small>Optional</small>
          </span>
          <textarea
            disabled={submitMutation.isPending}
            maxLength={1000}
            onChange={(event) => setComment(event.target.value)}
            placeholder="What was useful, or what could be improved?"
            rows={3}
            value={comment}
          />
        </label>
        {actionError ? (
          <p className="auth-error" role="alert">
            {actionError}
          </p>
        ) : null}
        <button disabled={rating === null || submitMutation.isPending} type="submit">
          <Send aria-hidden="true" size={18} />
          {submitMutation.isPending ? "Sending…" : "Send feedback"}
        </button>
      </form>
    </article>
  );
}
