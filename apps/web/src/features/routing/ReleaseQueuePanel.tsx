import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackageCheck, Send } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState } from "../../components/ui/PageState";
import {
  listReleaseQueue,
  releaseProduct,
  type RoutingQueue,
  type RoutingRoute,
} from "../../lib/api-client/routing";

type ReleaseQueuePanelProps = {
  csrfToken: string;
  route: RoutingRoute;
};

export function ReleaseQueuePanel({ csrfToken, route }: ReleaseQueuePanelProps) {
  const queryClient = useQueryClient();
  const [releasedReference, setReleasedReference] = useState<string | null>(null);
  const [releaseError, setReleaseError] = useState(false);
  const queueQuery = useQuery({
    queryKey: ["release-queue", route],
    queryFn: () => listReleaseQueue(route),
  });
  const releaseMutation = useMutation({
    mutationFn: (ticketId: string) => releaseProduct(ticketId, route, csrfToken),
    onSuccess: (ticket) => {
      setReleaseError(false);
      setReleasedReference(ticket.reference);
      queryClient.setQueryData<RoutingQueue>(["release-queue", route], (current) =>
        current === undefined
          ? current
          : {
              ...current,
              tickets: current.tickets.filter((item) => item.ticketId !== ticket.ticketId),
            },
      );
    },
    onError: () => setReleaseError(true),
  });
  const tickets = queueQuery.data?.tickets ?? [];

  return (
    <section className="surface release-panel" aria-labelledby="release-title">
      <div className="section-heading access-heading">
        <PackageCheck aria-hidden="true" size={20} />
        <div>
          <h2 id="release-title">Final release</h2>
          <p>QC-approved products awaiting your release to the customer.</p>
        </div>
      </div>
      {queueQuery.isError ? (
        <ErrorState onRetry={() => void queueQuery.refetch()} />
      ) : tickets.length === 0 ? (
        <EmptyState
          hint="Products approved by quality control appear here for final release."
          title="Nothing awaiting release"
        />
      ) : (
        <div className="stack-list">
          {tickets.map((ticket) => (
            <article className="release-row" key={ticket.ticketId}>
              <div>
                <strong>{ticket.reference}</strong>
                <span>{ticket.title}</span>
              </div>
              <button
                disabled={releaseMutation.isPending}
                onClick={() => releaseMutation.mutate(ticket.ticketId)}
                type="button"
              >
                <Send aria-hidden="true" size={16} />
                Release to customer
              </button>
            </article>
          ))}
        </div>
      )}
      {releasedReference !== null ? (
        <p className="release-confirmation" role="status">
          {releasedReference} released. The customer has been notified by email and in Istari.
        </p>
      ) : null}
      {releaseError ? (
        <p className="auth-error" role="alert">
          The release could not be completed. Refresh and try again.
        </p>
      ) : null}
    </section>
  );
}
