import { formatWorkflowState, toneForState } from "../../lib/workflow/state-format";

type StatusPillProps = {
  state: string;
};

export function StatusPill({ state }: StatusPillProps) {
  return (
    <span className={`status-pill status-pill--${toneForState(state)}`}>
      {formatWorkflowState(state)}
    </span>
  );
}
