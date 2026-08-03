import type {
  StoreSubscriptionInput,
  StoreSubscriptionScope,
} from "../../lib/api-client/store-organisation";

type Props = {
  draft: StoreSubscriptionInput;
  onChange: (value: StoreSubscriptionInput) => void;
  scopes: StoreSubscriptionScope[];
  scopesError: boolean;
  scopesLoading: boolean;
};

export function SubscriptionCriteriaFields({
  draft,
  onChange,
  scopes,
  scopesError,
  scopesLoading,
}: Props) {
  const update = (field: keyof StoreSubscriptionInput["criteria"], value: string) =>
    onChange({ ...draft, criteria: { ...draft.criteria, [field]: value || null } });
  const selected = draft.criteria.acgIds ?? [];
  const toggleAcg = (acgId: string) => {
    const acgIds = selected.includes(acgId)
      ? selected.filter((item) => item !== acgId)
      : [...selected, acgId].slice(0, 12);
    onChange({ ...draft, criteria: { ...draft.criteria, acgIds } });
  };

  return (
    <div className="store-subscription-criteria">
      <fieldset className="subscription-acg-scope">
        <legend>Access control groups</legend>
        <p>Select the ACGs you want to follow. You can only choose groups you currently hold.</p>
        {scopesLoading ? <small>Loading your ACG access…</small> : null}
        {scopesError ? (
          <small className="auth-error" role="alert">
            Your available ACGs could not be loaded.
          </small>
        ) : null}
        {!scopesLoading && !scopesError && scopes.length === 0 ? (
          <small>No active ACG access is available.</small>
        ) : null}
        <div className="subscription-acg-options">
          {scopes.map((scope) => (
            <label key={scope.id}>
              <input
                checked={selected.includes(scope.id)}
                disabled={!selected.includes(scope.id) && selected.length >= 12}
                onChange={() => toggleAcg(scope.id)}
                type="checkbox"
              />
              <span>
                <strong>{scope.code}</strong>
                <small>{scope.name}</small>
              </span>
            </label>
          ))}
        </div>
        <small>Leave all unchecked to search across every ACG you can currently access.</small>
      </fieldset>
      <label className="subscription-keywords">
        Keywords or phrases
        <input
          maxLength={200}
          onChange={(event) => update("query", event.target.value)}
          value={draft.criteria.query ?? ""}
        />
        <small>Matches titles, summaries, descriptions and indexed terms.</small>
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
