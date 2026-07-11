import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, Star } from "lucide-react";
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
    retry: false,
  });
  const requests = feedbackQuery.data ?? EMPTY_FEEDBACK;

  if (!canSubmitFeedback) {
    return null;
  }

  return (
    <section className="surface feedback-panel" aria-labelledby="feedback-title">
      <div className="section-heading access-heading">
        <Star aria-hidden="true" size={20} />
        <h2 id="feedback-title">Feedback</h2>
      </div>
      {feedbackQuery.isError ? (
        <div className="workspace-alert" role="alert">
          <span>Feedback requests could not be loaded.</span>
          <button onClick={() => void feedbackQuery.refetch()} type="button">
            Retry feedback
          </button>
        </div>
      ) : null}
      {!feedbackQuery.isError && requests.length === 0 ? <p>No feedback requests yet.</p> : null}
      <div className="feedback-list" aria-label="Feedback requests">
        {requests.map((request) => (
          <FeedbackRequestRow csrfToken={csrfToken} key={request.id} request={request} />
        ))}
      </div>
    </section>
  );
}

type FeedbackRequestRowProps = FeedbackPanelProps & {
  request: FeedbackRequest;
};

function FeedbackRequestRow({ csrfToken, request }: FeedbackRequestRowProps) {
  const queryClient = useQueryClient();
  const [rating, setRating] = useState("5");
  const [comment, setComment] = useState("");
  const [followUpRequested, setFollowUpRequested] = useState(false);
  const { actionError, clearActionError, failActionWith } = useActionError();
  const submitMutation = useMutation({
    onError: failActionWith("The feedback could not be submitted. Try again."),
    onMutate: clearActionError,
    mutationFn: () =>
      submitFeedback(request.id, { rating: Number(rating), comment, followUpRequested }, csrfToken),
    onSuccess: (updated) => {
      queryClient.setQueryData<FeedbackRequest[]>(["feedback-requests"], (current) =>
        (current ?? EMPTY_FEEDBACK).map((item) => (item.id === updated.id ? updated : item)),
      );
    },
  });

  return (
    <article className="feedback-row">
      <span>{request.ticketReference}</span>
      <strong>{request.productTitle}</strong>
      <small>{request.status}</small>
      {request.status === "requested" ? (
        <form
          aria-label={`Feedback for ${request.productTitle}`}
          className="feedback-form"
          onSubmit={(event) => {
            event.preventDefault();
            submitMutation.mutate();
          }}
        >
          <label>
            Rating
            <select
              disabled={submitMutation.isPending}
              onChange={(event) => setRating(event.target.value)}
              value={rating}
            >
              {[5, 4, 3, 2, 1].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Comment
            <textarea
              disabled={submitMutation.isPending}
              onChange={(event) => setComment(event.target.value)}
              rows={3}
              value={comment}
            />
          </label>
          <label className="feedback-follow-up">
            <input
              checked={followUpRequested}
              disabled={submitMutation.isPending}
              onChange={(event) => setFollowUpRequested(event.target.checked)}
              type="checkbox"
            />
            <span>Request follow-up</span>
          </label>
          {actionError ? (
            <p className="auth-error" role="alert">
              {actionError}
            </p>
          ) : null}
          <button disabled={comment.trim().length < 3 || submitMutation.isPending} type="submit">
            <Send aria-hidden="true" size={18} /> Submit feedback
          </button>
        </form>
      ) : null}
    </article>
  );
}
