import { Database, RefreshCw } from "lucide-react";
import { useState } from "react";

import { AdminDisclosureSummary } from "./AdminDisclosureSummary";
import {
  SearchConfigurationSummary,
  SearchEmbeddingConfiguration,
} from "./SearchEmbeddingConfiguration";
import { searchModelLabel, searchProviderLabel } from "./searchEmbeddingLabels";
import { searchEmbeddingPresentation, searchFailureMessage } from "./searchEmbeddingPresentation";
import { useSearchEmbeddingsPanelController } from "./useSearchEmbeddingsPanelController";

export function SearchEmbeddingsPanel({
  csrfToken,
  initiallyOpen = true,
}: {
  csrfToken: string;
  initiallyOpen?: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  const controller = useSearchEmbeddingsPanelController(csrfToken);
  const { query, state, reindexMutation, actionPending } = controller;
  const presentation = state ? searchEmbeddingPresentation(state) : null;

  return (
    <details
      className="surface admin-disclosure search-admin ai-model-panel"
      onToggle={(event) => setOpen(event.currentTarget.open)}
      open={open}
    >
      <AdminDisclosureSummary
        description="See whether Intelligence Store search is ready. Updates happen automatically."
        eyebrow="Intelligence Store search"
        icon={Database}
        statuses={
          presentation
            ? [
                { label: presentation.statusLabel, tone: presentation.statusTone },
                ...(!state?.definitiveNoMatchEnabled
                  ? [{ label: "Quality checks pending", tone: "attention" as const }]
                  : []),
              ]
            : [{ label: "Checking search" }]
        }
        title="Search & embeddings"
        titleId="search-embedding-title"
      />
      <div className="admin-disclosure__body">
        {query.isLoading ? <p role="status">Loading search settings…</p> : null}
        {query.isError ? (
          <p className="workspace-alert" role="alert">
            Search settings are unavailable.
          </p>
        ) : null}
        {state ? (
          <div className="search-admin__body">
            <SearchConfigurationSummary state={state} />
            {!state.definitiveNoMatchEnabled ? (
              <div className="search-admin__quality" role="status">
                <strong>Quality checks pending</strong>
                <span>
                  Search works now. Until its checks pass, Istari will avoid saying that no matching
                  information exists.
                </span>
              </div>
            ) : null}
            <SearchEmbeddingConfiguration controller={controller} />
            <section aria-labelledby="search-index-heading" className="search-admin__index">
              <div className="search-admin__index-heading">
                <div>
                  <h3 id="search-index-heading">Search library</h3>
                  <p>
                    New and changed intelligence is prepared for search automatically. No routine
                    maintenance is required.
                  </p>
                </div>
                {presentation?.needsAttention ? (
                  <button
                    className="ai-btn-primary"
                    disabled={actionPending}
                    onClick={() => reindexMutation.mutate()}
                    type="button"
                  >
                    <RefreshCw aria-hidden="true" size={16} />
                    {reindexMutation.isPending ? "Trying again…" : "Try automatic update again"}
                  </button>
                ) : null}
              </div>
              {reindexMutation.isError ? (
                <p className="field-hint" role="alert">
                  Istari could not restart the search library update.
                </p>
              ) : null}
              <div aria-label="Search library status" className="search-admin__facts">
                <Status label="Intelligence products" value={String(state.productCount)} />
                <Status label="Searchable sections" value={String(state.chunkCount)} />
                <Status label="Requests prepared for matching" value={String(state.ticketCount)} />
                <Status label="Files needing attention" value={String(state.failedAssetCount)} />
                <Status
                  label="Last updated"
                  value={
                    state.lastIndexedAt ? new Date(state.lastIndexedAt).toLocaleString() : "Never"
                  }
                />
              </div>
              <details className="search-admin__technical">
                <summary>Technical details</summary>
                <dl>
                  <Fact label="Search service" value={searchProviderLabel(state.provider)} />
                  <Fact label="Embedding model" value={searchModelLabel(state.model)} />
                  <Fact label="Vector size" value={`${state.dimensions} dimensions`} />
                  <Fact label="Generation" value={String(state.indexGeneration)} />
                  <Fact label="Corpus" value={state.corpusVersion} />
                  <Fact label="Search release" value={state.releaseId} />
                </dl>
              </details>
            </section>
            {presentation?.needsAttention ? (
              <p className="workspace-alert" role="alert">
                {searchFailureMessage(state.degradedReason)}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </details>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
