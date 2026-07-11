import type { AnalystTask } from "../../lib/api-client/analyst";

export const ACTIVE_ANALYST_STATES = new Set(["ANALYST_IN_PROGRESS", "REWORK_REQUIRED"]);

export function canSubmitTask(task: AnalystTask): boolean {
  return (
    ACTIVE_ANALYST_STATES.has(task.state) &&
    task.drafts.length > 0 &&
    task.workPackages.every((item) => item.status === "complete")
  );
}
