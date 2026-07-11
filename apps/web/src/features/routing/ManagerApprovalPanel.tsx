import { useMutation, useQuery } from "@tanstack/react-query";
import { ClipboardCheck, Undo2 } from "lucide-react";
import { useState } from "react";

import {
  approveManagerWork,
  getManagerWork,
  returnWorkForRework,
  type RoutingRoute,
  type RoutingTicket,
} from "../../lib/api-client/routing";
import { ManagerWorkReview } from "./ManagerWorkReview";

type ManagerApprovalPanelProps = {
  csrfToken: string;
  onDecided: (ticket: RoutingTicket) => void;
  route: RoutingRoute;
  ticketId: string;
};

export function ManagerApprovalPanel({
  csrfToken,
  onDecided,
  route,
  ticketId,
}: ManagerApprovalPanelProps) {
  const [reworkReason, setReworkReason] = useState("");
  const workQuery = useQuery({
    queryKey: ["routing", ticketId, "manager-work"],
    queryFn: () => getManagerWork(ticketId),
  });
  const approveMutation = useMutation({
    mutationFn: () => approveManagerWork(ticketId, csrfToken),
    onSuccess: onDecided,
  });
  const reworkMutation = useMutation({
    mutationFn: () => returnWorkForRework(ticketId, route, reworkReason.trim(), csrfToken),
    onSuccess: (ticket) => {
      setReworkReason("");
      onDecided(ticket);
    },
  });
  const isPending = approveMutation.isPending || reworkMutation.isPending;
  const decisionUnavailable = isPending || !workQuery.data || workQuery.isError;

  return (
    <section className="routing-assign" aria-label="Manager approval">
      <h3>Manager approval</h3>
      <p>
        The analysts have submitted their work. Approve it to forward the product to Quality
        Control, or return it with a reason for rework.
      </p>
      {workQuery.isPending ? <p role="status">Loading submitted work…</p> : null}
      {workQuery.isError ? (
        <div className="inline-error" role="alert">
          <p>The submitted work could not be loaded. Decisions remain locked.</p>
          <button onClick={() => void workQuery.refetch()} type="button">
            Retry
          </button>
        </div>
      ) : null}
      {workQuery.data ? <ManagerWorkReview task={workQuery.data} /> : null}
      <div className="routing-actions">
        <button
          disabled={decisionUnavailable || (workQuery.data?.drafts?.length ?? 0) === 0}
          onClick={() => approveMutation.mutate()}
          type="button"
        >
          <ClipboardCheck aria-hidden="true" size={18} />
          Approve and send to QC
        </button>
      </div>
      <label>
        Rework reason
        <textarea
          disabled={decisionUnavailable}
          onChange={(event) => setReworkReason(event.target.value)}
          placeholder="What must the analysts change before this can go to QC?"
          value={reworkReason}
        />
      </label>
      <button
        disabled={decisionUnavailable || reworkReason.trim().length < 3}
        onClick={() => reworkMutation.mutate()}
        type="button"
      >
        <Undo2 aria-hidden="true" size={18} />
        Return for rework
      </button>
      {approveMutation.isError || reworkMutation.isError ? (
        <p role="alert">The decision could not be recorded. Try again.</p>
      ) : null}
    </section>
  );
}
