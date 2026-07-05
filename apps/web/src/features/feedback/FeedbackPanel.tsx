import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, Star } from "lucide-react";
import { useState } from "react";

import {
  listFeedbackRequests,
  submitFeedback,
  type FeedbackRequest,
} from "../../lib/api-client/analytics";
import { useAuth } from "../../lib/auth/auth-context";

const EMPTY_FEEDBACK: FeedbackRequest[] = [];

type FeedbackPanelProps = {
  csrfToken: string;
};

export function FeedbackPanel({ csrfToken }: FeedbackPanelProps) {
  const { session } = useAuth();
  const canSubmitFeedback = session?.user.permissions.includes("feedback:create") ?? false;
  const queryClient = useQueryClient();
  const [rating, setRating] = useState("5");
  const [comment, setComment] = useState("");
  const [followUpRequested, setFollowUpRequested] = useState(false);
  const feedbackQuery = useQuery({
    queryKey: ["feedback-requests"],
    queryFn: listFeedbackRequests,
    enabled: canSubmitFeedback,
    placeholderData: EMPTY_FEEDBACK,
  });
  const requests = feedbackQuery.data ?? EMPTY_FEEDBACK;
  const pendingRequest = requests.find((request) => request.status === "requested");
  const submitMutation = useMutation({
    mutationFn: () =>
      submitFeedback(
        pendingRequest?.id ?? "",
        {
          rating: Number(rating),
          comment,
          followUpRequested,
        },
        csrfToken,
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData<FeedbackRequest[]>(["feedback-requests"], (current) =>
        (current ?? EMPTY_FEEDBACK).map((request) =>
          request.id === updated.id ? updated : request,
        ),
      );
      setComment("");
      setFollowUpRequested(false);
    },
  });

  if (!canSubmitFeedback) {
    return null;
  }

  return (
    <section className="surface feedback-panel" aria-labelledby="feedback-title">
      <div className="section-heading access-heading">
        <Star aria-hidden="true" size={20} />
        <h2 id="feedback-title">Feedback</h2>
      </div>
      {requests.length === 0 ? <p>No feedback requests yet.</p> : null}
      <div className="feedback-list" aria-label="Feedback requests">
        {requests.map((request) => (
          <article className="feedback-row" key={request.id}>
            <span>{request.ticketReference}</span>
            <strong>{request.productTitle}</strong>
            <small>{request.status}</small>
          </article>
        ))}
      </div>
      {pendingRequest ? (
        <form
          className="feedback-form"
          onSubmit={(event) => {
            event.preventDefault();
            submitMutation.mutate();
          }}
        >
          <label>
            Rating
            <select onChange={(event) => setRating(event.target.value)} value={rating}>
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
              onChange={(event) => setComment(event.target.value)}
              rows={3}
              value={comment}
            />
          </label>
          <label className="feedback-follow-up">
            <input
              checked={followUpRequested}
              onChange={(event) => setFollowUpRequested(event.target.checked)}
              type="checkbox"
            />
            <span>Request follow-up</span>
          </label>
          <button disabled={comment.trim().length < 3 || submitMutation.isPending} type="submit">
            <Send aria-hidden="true" size={18} /> Submit feedback
          </button>
        </form>
      ) : null}
    </section>
  );
}
