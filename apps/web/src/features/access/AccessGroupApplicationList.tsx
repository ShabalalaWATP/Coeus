import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Search, ShieldCheck, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  applyForAccessGroup,
  withdrawAccessGroupApplication,
  type AccessGroupSummary,
} from "../../lib/api-client/access-groups";
import { actionErrorMessage } from "../../lib/mutations/action-error";

type AccessGroupApplicationListProps = {
  csrfToken: string;
  groups: AccessGroupSummary[];
  onSearchChange: (query: string) => void;
  searchQuery: string;
  total: number;
};

export function AccessGroupApplicationList({
  csrfToken,
  groups,
  onSearchChange,
  searchQuery,
  total,
}: AccessGroupApplicationListProps) {
  const orderedGroups = useMemo(
    () => [...groups].sort((left, right) => statusRank(left) - statusRank(right)),
    [groups],
  );
  const [selectedId, setSelectedId] = useState(orderedGroups[0]?.id ?? "");
  const selected = orderedGroups.find((group) => group.id === selectedId) ?? orderedGroups[0];

  useEffect(() => {
    if (selected !== undefined && selected.id !== selectedId) setSelectedId(selected.id);
  }, [selected, selectedId]);

  return (
    <section className="access-group-directory" aria-labelledby="access-group-list-title">
      <div className="access-group-directory__heading">
        <div>
          <h2 id="access-group-list-title">Available ACGs</h2>
          <p>
            {total} active access {total === 1 ? "group matches" : "groups match"} this view.
          </p>
        </div>
        <label className="access-group-search">
          <Search aria-hidden="true" size={18} />
          <span className="sr-only">Search access groups</span>
          <input
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search by name, code or purpose"
            type="search"
            value={searchQuery}
          />
        </label>
      </div>

      <div className="access-group-directory__layout">
        <nav aria-label="Available access groups" className="access-group-results">
          {orderedGroups.map((group) => (
            <button
              aria-current={group.id === selected?.id ? "true" : undefined}
              className="access-group-result"
              key={group.id}
              onClick={() => setSelectedId(group.id)}
              type="button"
            >
              <span className="access-group-result__code">{group.code}</span>
              <strong>{group.name}</strong>
              <small>{statusLabel(group)}</small>
              <ArrowRight aria-hidden="true" size={16} />
            </button>
          ))}
          {orderedGroups.length === 0 ? (
            <p className="access-group-results__empty">No ACGs match your search.</p>
          ) : null}
        </nav>

        {selected ? (
          <AccessGroupDetail csrfToken={csrfToken} group={selected} key={selected.id} />
        ) : (
          <section className="surface access-group-detail" aria-label="Access group detail">
            <p>Choose a different search to view an access group.</p>
          </section>
        )}
      </div>
    </section>
  );
}

function AccessGroupDetail({ csrfToken, group }: { csrfToken: string; group: AccessGroupSummary }) {
  const queryClient = useQueryClient();
  const [justification, setJustification] = useState("");
  const [message, setMessage] = useState<{ tone: "ok" | "fail"; text: string } | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["access-groups"] });
  const applyMutation = useMutation({
    mutationFn: () => applyForAccessGroup(group.id, justification.trim(), csrfToken),
    onMutate: () => setMessage(null),
    onError: (error) =>
      setMessage({
        tone: "fail",
        text: actionErrorMessage(error, "The application could not be submitted."),
      }),
    onSuccess: async () => {
      setJustification("");
      setMessage({ tone: "ok", text: "Application submitted." });
      await refresh();
    },
  });
  const withdrawMutation = useMutation({
    mutationFn: () => withdrawAccessGroupApplication(group.id, csrfToken),
    onMutate: () => setMessage(null),
    onError: (error) =>
      setMessage({
        tone: "fail",
        text: actionErrorMessage(error, "The application could not be withdrawn."),
      }),
    onSuccess: async () => {
      setMessage({ tone: "ok", text: "Application withdrawn." });
      await refresh();
    },
  });
  const pending = applyMutation.isPending || withdrawMutation.isPending;
  const canApply = !group.isMember && group.applicationStatus !== "pending";
  const managerNames = group.managerNames ?? [];

  return (
    <article className="surface access-group-detail border-glow">
      <header className="access-group-detail__header">
        <div>
          <span>{group.code}</span>
          <h3>{group.name}</h3>
        </div>
        <strong className="access-group-status">
          <ShieldCheck aria-hidden="true" size={16} />
          {statusLabel(group)}
        </strong>
      </header>
      <p>{group.description}</p>
      <section className="access-group-managers" aria-labelledby="access-group-managers-title">
        <div>
          <UsersRound aria-hidden="true" size={18} />
          <h4 id="access-group-managers-title">Current managers</h4>
        </div>
        {managerNames.length ? (
          <ul>
            {managerNames.map((manager) => (
              <li key={manager}>{manager}</li>
            ))}
          </ul>
        ) : (
          <p>No active managers are listed.</p>
        )}
      </section>
      {canApply ? (
        <form
          className="access-group-application-form"
          onSubmit={(event) => {
            event.preventDefault();
            applyMutation.mutate();
          }}
        >
          <label htmlFor={`access-justification-${group.id}`}>
            Why do you need access?
            <span>Tell the managers how this ACG supports your work.</span>
          </label>
          <textarea
            disabled={pending}
            id={`access-justification-${group.id}`}
            maxLength={500}
            onChange={(event) => setJustification(event.target.value)}
            placeholder="Describe the task, intended use and how long you expect to need access."
            rows={6}
            value={justification}
          />
          <div className="form-footer">
            <small>{justification.length}/500 characters</small>
            <button disabled={pending || justification.trim().length < 10} type="submit">
              {applyMutation.isPending ? "Submitting…" : "Submit application"}
            </button>
          </div>
        </form>
      ) : null}
      {!group.isMember && group.applicationStatus === "pending" ? (
        <button
          className="secondary-action"
          disabled={pending}
          onClick={() => {
            if (window.confirm(`Withdraw your application to ${group.name}?`)) {
              withdrawMutation.mutate();
            }
          }}
          type="button"
        >
          {withdrawMutation.isPending ? "Withdrawing…" : "Withdraw application"}
        </button>
      ) : null}
      {group.isMember ? (
        <p className="access-group-member-note">You already have access to this ACG.</p>
      ) : null}
      {message ? <p role={message.tone === "fail" ? "alert" : "status"}>{message.text}</p> : null}
    </article>
  );
}

function statusRank(group: AccessGroupSummary) {
  if (group.isMember) return 0;
  if (group.applicationStatus === "pending") return 1;
  return 2;
}

function statusLabel(group: AccessGroupSummary) {
  if (group.isMember) return "Member";
  if (group.applicationStatus === "pending") return "Application pending";
  if (group.applicationStatus === "rejected") return "Application rejected";
  if (group.applicationStatus === "approved") return "Application approved";
  if (group.applicationStatus === "withdrawn") return "Application withdrawn";
  return "Not a member";
}
