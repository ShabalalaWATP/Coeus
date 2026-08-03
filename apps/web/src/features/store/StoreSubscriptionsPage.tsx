import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Plus, Rss, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { SubscriptionCriteriaFields } from "./SubscriptionCriteriaFields";
import { StoreWorkspaceNav } from "./StoreWorkspaceNav";
import {
  criteriaFromParams,
  criteriaSummary,
  hasCurrentAcgAccess,
  hasSubscriptionCriteria,
  subscriptionSearchPath,
} from "./subscription-search";
import {
  createStoreSubscription,
  deleteStoreSubscription,
  getStoreSubscriptionScopes,
  getStoreSubscriptions,
  updateStoreSubscription,
  type StoreSubscription,
  type StoreSubscriptionInput,
} from "../../lib/api-client/store-organisation";
import { useAuth } from "../../lib/auth/auth-context";

export default function StoreSubscriptionsPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const initialCriteria = useMemo(() => criteriaFromParams(searchParams), [searchParams]);
  const [draft, setDraft] = useState<StoreSubscriptionInput>({
    name: "",
    cadence: "weekly",
    enabled: true,
    criteria: initialCriteria,
  });
  const subscriptions = useQuery({
    queryKey: ["store-subscriptions"],
    queryFn: getStoreSubscriptions,
  });
  const scopes = useQuery({
    queryKey: ["store-subscription-scopes"],
    queryFn: getStoreSubscriptionScopes,
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["store-subscriptions"] });
  const create = useMutation({
    mutationFn: () => createStoreSubscription(draft, session?.csrfToken ?? ""),
    onSuccess: () => {
      setDraft({ name: "", cadence: "weekly", enabled: true, criteria: { acgIds: [] } });
      refresh();
    },
  });
  const update = useMutation({
    mutationFn: (subscription: StoreSubscription) =>
      updateStoreSubscription(
        subscription.id,
        {
          name: subscription.name,
          cadence: subscription.cadence,
          enabled: !subscription.enabled,
          criteria: subscription.criteria,
        },
        session?.csrfToken ?? "",
      ),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteStoreSubscription(id, session?.csrfToken ?? ""),
    onSuccess: refresh,
  });

  return (
    <div className="store-page">
      <section className="overview-hero" aria-labelledby="subscriptions-title">
        <div>
          <span className="eyebrow">Intelligence Store</span>
          <h1 id="subscriptions-title">Subscriptions</h1>
          <p>Save searches you want to review repeatedly as new intelligence is added.</p>
        </div>
      </section>
      <StoreWorkspaceNav />

      <section className="store-subscriptions-layout">
        <form
          className="surface store-subscription-create"
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.name.trim() && hasSubscriptionCriteria(draft.criteria)) create.mutate();
          }}
        >
          <div>
            <span className="eyebrow">New subscription</span>
            <h2>Save a search</h2>
            <p>Subscriptions always run with your current access.</p>
          </div>
          <label>
            Name
            <input
              maxLength={80}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              value={draft.name}
            />
          </label>
          <label>
            Review cadence
            <select
              onChange={(event) =>
                setDraft({
                  ...draft,
                  cadence: event.target.value as StoreSubscriptionInput["cadence"],
                })
              }
              value={draft.cadence}
            >
              <option value="manual">When I choose</option>
              <option value="daily">Daily review</option>
              <option value="weekly">Weekly review</option>
            </select>
          </label>
          <SubscriptionCriteriaFields
            draft={draft}
            onChange={setDraft}
            scopes={scopes.data ?? []}
            scopesError={scopes.isError}
            scopesLoading={scopes.isLoading}
          />
          <button
            className="store-action"
            disabled={
              !draft.name.trim() || !hasSubscriptionCriteria(draft.criteria) || create.isPending
            }
            type="submit"
          >
            <Plus aria-hidden="true" size={17} /> Create subscription
          </button>
          {create.isError ? (
            <p className="auth-error" role="alert">
              The subscription could not be saved.
            </p>
          ) : null}
        </form>

        <section
          className="surface store-subscription-list"
          aria-labelledby="saved-subscriptions-title"
        >
          <div className="store-section-heading">
            <div>
              <span className="eyebrow">Saved searches</span>
              <h2 id="saved-subscriptions-title">Your subscriptions</h2>
            </div>
            <span className="store-chip">{subscriptions.data?.length ?? 0}</span>
          </div>
          {subscriptions.isLoading ? <p>Loading subscriptions…</p> : null}
          {subscriptions.isError ? (
            <p className="auth-error">Subscriptions are unavailable.</p>
          ) : null}
          {(subscriptions.data ?? []).map((subscription) => {
            const hasSelectedAcgs = subscription.criteria.acgIds.length > 0;
            const currentAccess =
              !hasSelectedAcgs ||
              (scopes.isSuccess && hasCurrentAcgAccess(subscription, scopes.data));
            const accessLabel = scopes.isLoading
              ? "Checking ACG access"
              : scopes.isError
                ? "ACG access unavailable"
                : "ACG access changed";
            return (
              <article
                className={
                  subscription.enabled ? "store-subscription" : "store-subscription is-paused"
                }
                key={subscription.id}
              >
                <Rss aria-hidden="true" size={20} />
                <div>
                  <strong>{subscription.name}</strong>
                  <p>{criteriaSummary(subscription, scopes.data ?? [], accessLabel)}</p>
                  <small>
                    {cadenceLabel(subscription.cadence)} ·{" "}
                    {subscription.enabled ? "Active" : "Paused"}
                  </small>
                </div>
                <div className="store-subscription__actions">
                  {currentAccess ? (
                    <Link className="store-action" to={subscriptionSearchPath(subscription)}>
                      Open results
                    </Link>
                  ) : (
                    <span className="store-subscription__access-changed">{accessLabel}</span>
                  )}
                  <button
                    aria-label={`${subscription.enabled ? "Pause" : "Resume"} ${subscription.name}`}
                    disabled={update.isPending || !currentAccess}
                    onClick={() => update.mutate(subscription)}
                    type="button"
                  >
                    {subscription.enabled ? (
                      <Pause aria-hidden="true" size={16} />
                    ) : (
                      <Play aria-hidden="true" size={16} />
                    )}
                  </button>
                  <button
                    aria-label={`Delete ${subscription.name}`}
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(subscription.id)}
                    type="button"
                  >
                    <Trash2 aria-hidden="true" size={16} />
                  </button>
                </div>
              </article>
            );
          })}
          {!subscriptions.isLoading &&
          !subscriptions.isError &&
          subscriptions.data?.length === 0 ? (
            <p>No subscriptions yet. Save a search you expect to revisit.</p>
          ) : null}
          {update.isError || remove.isError ? (
            <p className="auth-error" role="alert">
              The subscription change could not be saved.
            </p>
          ) : null}
        </section>
      </section>
    </div>
  );
}

function cadenceLabel(cadence: StoreSubscription["cadence"]) {
  return cadence === "manual"
    ? "Review when needed"
    : `${cadence[0].toUpperCase()}${cadence.slice(1)} review`;
}
