import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Plus, Rss, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { StoreWorkspaceNav } from "./StoreWorkspaceNav";
import {
  createStoreSubscription,
  deleteStoreSubscription,
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
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["store-subscriptions"] });
  const create = useMutation({
    mutationFn: () => createStoreSubscription(draft, session?.csrfToken ?? ""),
    onSuccess: () => {
      setDraft({ name: "", cadence: "weekly", enabled: true, criteria: {} });
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
            if (draft.name.trim() && hasCriteria(draft)) create.mutate();
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
          <CriteriaFields draft={draft} onChange={setDraft} />
          <button
            className="store-action"
            disabled={!draft.name.trim() || !hasCriteria(draft) || create.isPending}
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
          {(subscriptions.data ?? []).map((subscription) => (
            <article
              className={
                subscription.enabled ? "store-subscription" : "store-subscription is-paused"
              }
              key={subscription.id}
            >
              <Rss aria-hidden="true" size={20} />
              <div>
                <strong>{subscription.name}</strong>
                <p>{criteriaSummary(subscription)}</p>
                <small>
                  {cadenceLabel(subscription.cadence)} ·{" "}
                  {subscription.enabled ? "Active" : "Paused"}
                </small>
              </div>
              <div className="store-subscription__actions">
                <Link className="store-action" to={subscriptionSearchPath(subscription)}>
                  Open results
                </Link>
                <button
                  aria-label={`${subscription.enabled ? "Pause" : "Resume"} ${subscription.name}`}
                  disabled={update.isPending}
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
          ))}
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

function CriteriaFields({
  draft,
  onChange,
}: {
  draft: StoreSubscriptionInput;
  onChange: (value: StoreSubscriptionInput) => void;
}) {
  const update = (field: keyof StoreSubscriptionInput["criteria"], value: string) =>
    onChange({ ...draft, criteria: { ...draft.criteria, [field]: value || null } });
  return (
    <div className="store-subscription-criteria">
      <label>
        Search terms
        <input
          maxLength={200}
          onChange={(event) => update("query", event.target.value)}
          value={draft.criteria.query ?? ""}
        />
      </label>
      <label>
        Region
        <input
          maxLength={180}
          onChange={(event) => update("region", event.target.value)}
          value={draft.criteria.region ?? ""}
        />
      </label>
      <label>
        Product type
        <input
          maxLength={80}
          onChange={(event) => update("productType", event.target.value)}
          value={draft.criteria.productType ?? ""}
        />
      </label>
      <label>
        Tag
        <input
          maxLength={80}
          onChange={(event) => update("tag", event.target.value)}
          value={draft.criteria.tag ?? ""}
        />
      </label>
      <label>
        Source type
        <input
          maxLength={80}
          onChange={(event) => update("sourceType", event.target.value)}
          value={draft.criteria.sourceType ?? ""}
        />
      </label>
      <label>
        Coverage from
        <input
          onChange={(event) => update("dateFrom", event.target.value)}
          type="date"
          value={draft.criteria.dateFrom ?? ""}
        />
      </label>
      <label>
        Coverage to
        <input
          onChange={(event) => update("dateTo", event.target.value)}
          type="date"
          value={draft.criteria.dateTo ?? ""}
        />
      </label>
    </div>
  );
}

function criteriaFromParams(params: URLSearchParams): StoreSubscriptionInput["criteria"] {
  const value = (key: string) => params.get(key) || null;
  return {
    query: value("query"),
    productType: value("productType"),
    region: value("region"),
    tag: value("tag"),
    sourceType: value("sourceType"),
    dateFrom: value("dateFrom"),
    dateTo: value("dateTo"),
  };
}

function hasCriteria(draft: StoreSubscriptionInput) {
  return Object.values(draft.criteria).some((value) => typeof value === "string" && value.trim());
}

function subscriptionSearchPath(subscription: StoreSubscription) {
  const params = new URLSearchParams();
  Object.entries(subscription.criteria).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return `/store?${params.toString()}`;
}

function criteriaSummary(subscription: StoreSubscription) {
  return Object.values(subscription.criteria).filter(Boolean).join(" · ");
}

function cadenceLabel(cadence: StoreSubscription["cadence"]) {
  return cadence === "manual"
    ? "Review when needed"
    : `${cadence[0].toUpperCase()}${cadence.slice(1)} review`;
}
