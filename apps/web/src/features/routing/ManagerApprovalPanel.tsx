import { useMutation } from "@tanstack/react-query";
import { ClipboardCheck, Undo2 } from "lucide-react";
import { useState } from "react";

import {
  approveManagerWork,
  returnWorkForRework,
  type RoutingRoute,
  type RoutingTicket,
} from "../../lib/api-client/routing";

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

  return (
    <section className="routing-assign" aria-label="Manager approval">
      <h3>Manager approval</h3>
      <p>
        The analysts have submitted their work. Approve it to forward the product to Quality
        Control, or return it with a reason for rework.
      </p>
      <div className="routing-actions">
        <button disabled={isPending} onClick={() => approveMutation.mutate()} type="button">
          <ClipboardCheck aria-hidden="true" size={18} />
          Approve and send to QC
        </button>
      </div>
      <label>
        Rework reason
        <textarea
          onChange={(event) => setReworkReason(event.target.value)}
          placeholder="What must the analysts change before this can go to QC?"
          value={reworkReason}
        />
      </label>
      <button
        disabled={isPending || reworkReason.trim().length < 3}
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
