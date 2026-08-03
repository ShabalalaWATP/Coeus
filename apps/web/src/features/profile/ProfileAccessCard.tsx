import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { listAccessGroups } from "../../lib/api-client/access-groups";

/**
 * The need-to-know groups this account holds.
 *
 * Membership decides which holdings are visible at all, so it belongs on the
 * profile rather than only in the access-group catalogue. Pending applications
 * are shown too, so a request in flight is not invisible.
 */
/** Enough to recognise the shape of your access without burying the page. */
const MAX_SHOWN = 9;

export function ProfileAccessCard({ canViewAcgs }: { canViewAcgs: boolean }) {
  const catalogue = useQuery({
    enabled: canViewAcgs,
    queryKey: ["acg-catalogue", 1, ""],
    queryFn: () => listAccessGroups(1, ""),
  });
  if (!canViewAcgs) return null;

  const groups = catalogue.data?.acgs ?? [];
  const held = groups.filter((group) => group.isMember);
  const pending = groups.filter(
    (group) => !group.isMember && group.applicationStatus === "pending",
  );

  return (
    <section className="profile-panel" aria-labelledby="profile-access-title">
      <div className="profile-panel__heading">
        <h3 id="profile-access-title">
          Need-to-know access
          <span className="profile-panel__count">{held.length}</span>
        </h3>
        <Link className="profile-panel__link" to="/access-groups">
          Manage
          <ArrowRight aria-hidden="true" size={15} />
        </Link>
      </div>

      {catalogue.isLoading ? <p className="profile-muted">Loading your access groups…</p> : null}
      {catalogue.isError ? (
        <p className="profile-muted">Your access groups could not be loaded.</p>
      ) : null}

      {catalogue.isSuccess && held.length === 0 ? (
        <p className="profile-muted">
          You hold no access groups yet, so no controlled holdings are visible to you.
        </p>
      ) : null}

      {held.length > 0 ? (
        <>
          <ul className="profile-access-list">
            {held.slice(0, MAX_SHOWN).map((group) => (
              <li key={group.id}>
                <ShieldCheck aria-hidden="true" size={14} />
                <span>
                  <strong>{group.code}</strong>
                  <small>{group.name}</small>
                </span>
              </li>
            ))}
          </ul>
          {held.length > MAX_SHOWN ? (
            <p className="profile-muted">
              and {held.length - MAX_SHOWN} more. <Link to="/access-groups">See all groups</Link>.
            </p>
          ) : null}
        </>
      ) : null}

      {pending.length > 0 ? (
        <p className="profile-muted">
          {pending.length} application{pending.length === 1 ? "" : "s"} awaiting review.
        </p>
      ) : null}
    </section>
  );
}
