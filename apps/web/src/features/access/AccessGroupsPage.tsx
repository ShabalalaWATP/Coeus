import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AccessGroupApplicationList } from "./AccessGroupApplicationList";
import { AccessGroupReviewQueue } from "./AccessGroupReviewQueue";
import { AccessGroupAdminPanel } from "./AccessGroupAdminPanel";
import { AdminReturnLink } from "../../components/ui/AdminReturnLink";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/PageState";
import { listAccessGroupApplications, listAccessGroups } from "../../lib/api-client/access-groups";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

export default function AccessGroupsPage() {
  const { session } = useAuth();
  const [cataloguePage, setCataloguePage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [reviewPage, setReviewPage] = useState(1);
  const groupsQuery = useQuery({
    queryKey: ["access-groups", cataloguePage, searchQuery],
    queryFn: () => listAccessGroups(cataloguePage, searchQuery),
    placeholderData: keepPreviousData,
  });
  const reviewsQuery = useQuery({
    queryKey: ["access-group-applications", reviewPage],
    queryFn: () => listAccessGroupApplications(reviewPage),
    retry: false,
  });
  const csrfToken = session?.csrfToken ?? "";
  const groups = groupsQuery.data?.acgs ?? [];
  const totalGroups = groupsQuery.data?.total ?? groups.length;
  const canReviewApplications = groups.some((group) => group.canReviewApplications);
  const isPlatformAdmin = session !== null && hasPermissions(session.user, ["role:manage"]);
  const [decisionMessage, setDecisionMessage] = useState<string | null>(null);

  return (
    <div className="workspace-page access-groups-page">
      <section className="overview-hero" aria-labelledby="access-groups-title">
        <div>
          <AdminReturnLink />
          <h1 id="access-groups-title">Access Groups</h1>
          <p>Find the need-to-know communities that support your work.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      {groupsQuery.isLoading ? <LoadingState label="Loading access groups" /> : null}
      {groupsQuery.isError ? <ErrorState onRetry={() => void groupsQuery.refetch()} /> : null}
      {groupsQuery.isSuccess && totalGroups === 0 && !searchQuery ? (
        <EmptyState title="No active access groups" hint="An administrator can activate groups." />
      ) : null}
      {groupsQuery.isSuccess && (totalGroups > 0 || searchQuery) ? (
        <AccessGroupApplicationList
          csrfToken={csrfToken}
          groups={groups}
          onSearchChange={(query) => {
            setCataloguePage(1);
            setSearchQuery(query);
          }}
          searchQuery={searchQuery}
          total={totalGroups}
        />
      ) : null}
      {groupsQuery.data && groupsQuery.data.totalPages > 1 ? (
        <nav aria-label="Access group catalogue pages" className="access-group-pagination">
          <button
            disabled={cataloguePage === 1}
            onClick={() => setCataloguePage((page) => page - 1)}
            type="button"
          >
            Previous
          </button>
          <span>
            Page {cataloguePage} of {groupsQuery.data.totalPages}
          </span>
          <button
            disabled={cataloguePage === groupsQuery.data.totalPages}
            onClick={() => setCataloguePage((page) => page + 1)}
            type="button"
          >
            Next
          </button>
        </nav>
      ) : null}
      {reviewsQuery.isLoading ? <LoadingState label="Checking delegated review queue" /> : null}
      {reviewsQuery.isError ? <ErrorState onRetry={() => void reviewsQuery.refetch()} /> : null}
      {decisionMessage ? <p role="status">{decisionMessage}</p> : null}
      {reviewsQuery.isSuccess &&
      reviewsQuery.data.applications.length === 0 &&
      canReviewApplications ? (
        <section className="surface access-group-reviews" aria-labelledby="empty-reviews-title">
          <h2 id="empty-reviews-title">Applications to review</h2>
          <p>No applications await review.</p>
        </section>
      ) : null}
      {reviewsQuery.isSuccess && reviewsQuery.data.applications.length ? (
        <AccessGroupReviewQueue
          applications={reviewsQuery.data.applications}
          csrfToken={csrfToken}
          currentUserId={session?.user.id ?? ""}
          onDecisionSuccess={setDecisionMessage}
        />
      ) : null}
      {reviewsQuery.isSuccess && reviewsQuery.data.totalPages > 1 ? (
        <nav aria-label="Application review pages" className="access-group-pagination">
          <button
            disabled={reviewPage === 1}
            onClick={() => setReviewPage((page) => page - 1)}
            type="button"
          >
            Previous
          </button>
          <span>
            Page {reviewPage} of {reviewsQuery.data.totalPages}
          </span>
          <button
            disabled={reviewPage === reviewsQuery.data.totalPages}
            onClick={() => setReviewPage((page) => page + 1)}
            type="button"
          >
            Next
          </button>
        </nav>
      ) : null}
      {isPlatformAdmin && groups.some((group) => group.canManageAdmins) ? (
        <AccessGroupAdminPanel
          csrfToken={csrfToken}
          groups={groups.filter((group) => group.canManageAdmins)}
        />
      ) : null}
    </div>
  );
}
