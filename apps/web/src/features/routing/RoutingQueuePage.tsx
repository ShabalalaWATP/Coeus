import { CapabilityCataloguePanel } from "./CapabilityCataloguePanel";
import { RoutingDetailPanel } from "./RoutingDetailPanel";
import { RoutingTicketList } from "./RoutingTicketList";
import { RoutingStats } from "./routing-sections";
import { useRoutingQueueController } from "./useRoutingQueueController";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import type { RoutingQueueKind } from "../../lib/api-client/routing";

type RoutingQueuePageProps = {
  queue: RoutingQueueKind;
};

export default function RoutingQueuePage({ queue: queueKind }: RoutingQueuePageProps) {
  const controller = useRoutingQueueController(queueKind);
  const {
    actionPending,
    catalogueRoute,
    detailActions,
    detailState,
    isJioc,
    labels,
    olderQueueMutation,
    queue,
    queueQuery,
    selectTicket,
    selectedTicket,
  } = controller;

  return (
    <div className="routing-page">
      <section className="overview-hero" aria-labelledby="routing-title">
        <div>
          <h1 id="routing-title">{labels.title}</h1>
          <p>{labels.description}</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      <section className="routing-grid">
        <aside className="surface routing-list" aria-label={`${labels.shortName} tickets`}>
          <div className="section-heading">
            <h2>{labels.listTitle}</h2>
            <p>{queue.tickets.length} tickets in this queue.</p>
          </div>
          {isJioc ? <RoutingStats queue={queue} /> : null}
          {queueQuery.isError ? (
            <ErrorState onRetry={() => void queueQuery.refetch()} />
          ) : queueQuery.isFetching && queueQuery.dataUpdatedAt === 0 ? (
            <LoadingState label={`Loading ${labels.shortName} queue`} />
          ) : (
            <>
              <RoutingTicketList
                disabled={actionPending}
                onSelect={selectTicket}
                selectedTicketId={selectedTicket?.ticketId}
                tickets={queue.tickets}
              />
              {queue.nextCursor ? (
                <button
                  className="secondary-button"
                  disabled={olderQueueMutation.isPending}
                  onClick={() => olderQueueMutation.mutate()}
                  type="button"
                >
                  {olderQueueMutation.isPending ? "Loading more…" : "Load more tickets"}
                </button>
              ) : null}
            </>
          )}
          <CapabilityCataloguePanel route={catalogueRoute} showAll={isJioc} />
        </aside>
        <RoutingDetailPanel actions={detailActions} state={detailState} />
      </section>
    </div>
  );
}
