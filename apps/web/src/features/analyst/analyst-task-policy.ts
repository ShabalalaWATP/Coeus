import type { AnalystTask } from "../../lib/api-client/analyst";

export const ACTIVE_ANALYST_STATES = new Set(["ANALYST_IN_PROGRESS", "REWORK_REQUIRED"]);

export function canSubmitTask(task: AnalystTask): boolean {
  return submissionBlockers(task).length === 0;
}

export function submissionBlockers(task: AnalystTask): string[] {
  const blockers: string[] = [];
  if (!ACTIVE_ANALYST_STATES.has(task.state))
    blockers.push("This task is not open for analyst work.");
  if (task.workPackages.some((item) => item.status !== "complete")) {
    blockers.push("Complete every work package.");
  }
  if (task.drafts.length === 0) blockers.push("Save at least one draft product.");
  return blockers;
}
