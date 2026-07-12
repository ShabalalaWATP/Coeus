import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  applyForAccessGroup,
  withdrawAccessGroupApplication,
  type AccessGroupSummary,
} from "../../lib/api-client/access-groups";
import { actionErrorMessage } from "../../lib/mutations/action-error";

export function AccessGroupApplicationList({
  csrfToken,
  groups,
}: {
  csrfToken: string;
  groups: AccessGroupSummary[];
}) {
  return (
    <section className="access-group-list" aria-labelledby="access-group-list-title">
      <h2 id="access-group-list-title">Available groups</h2>
      {groups.map((group) => (
        <AccessGroupApplicationRow csrfToken={csrfToken} group={group} key={group.id} />
      ))}
    </section>
  );
}

function AccessGroupApplicationRow({
  csrfToken,
  group,
}: {
  csrfToken: string;
  group: AccessGroupSummary;
}) {
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

  return (
    <article className="surface access-group-application">
      <div>
        <h3>{group.name}</h3>
        <p>{group.description}</p>
      </div>
      <strong className="access-group-application__status">
        {group.isMember ? "Member" : statusLabel(group.applicationStatus)}
      </strong>
      {canApply ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            applyMutation.mutate();
          }}
        >
          <label>
            Why do you need access to {group.name}?
            <textarea
              disabled={pending}
              maxLength={1000}
              onChange={(event) => setJustification(event.target.value)}
              value={justification}
            />
          </label>
          <button disabled={pending || justification.trim().length < 10} type="submit">
            Apply for access
          </button>
        </form>
      ) : null}
      {!group.isMember && group.applicationStatus === "pending" ? (
        <button
          disabled={pending}
          onClick={() => {
            if (window.confirm(`Withdraw your application to ${group.name}?`)) {
              withdrawMutation.mutate();
            }
          }}
          type="button"
        >
          Withdraw application
        </button>
      ) : null}
      {message ? <p role={message.tone === "fail" ? "alert" : "status"}>{message.text}</p> : null}
    </article>
  );
}

function statusLabel(status: AccessGroupSummary["applicationStatus"]) {
  if (status === "pending") return "Application pending";
  if (status === "rejected") return "Application rejected";
  if (status === "approved") return "Application approved";
  if (status === "withdrawn") return "Application withdrawn";
  return "Not a member";
}
