import type { TeamTaskBoard } from "../../lib/api-client/team-task-board";

/** One assigned work package placed on a calendar day. */
export type AssignedDay = {
  packageId: string;
  title: string;
  reference: string;
  analystUserId: string | null;
  state: string;
  day: string;
  /** True when the day came from the ticket rather than the package itself. */
  fromTicket: boolean;
};

const COMPLETE_STATES = new Set(["complete", "cancelled"]);

/**
 * Place assigned work on the calendar by the date it is due.
 *
 * A package carries its own dueAt; where it has none the ticket's target date
 * stands in, which is the date the team is actually working towards. Packages
 * with neither are left off rather than guessed onto a day, and finished work
 * is dropped because the calendar is about what is still coming.
 */
export function assignmentsByDay(board: TeamTaskBoard | undefined): Map<string, AssignedDay[]> {
  const byDay = new Map<string, AssignedDay[]>();
  for (const card of board?.cards ?? []) {
    for (const item of card.packages) {
      if (COMPLETE_STATES.has(item.state)) continue;
      const own = dayOf(item.dueAt);
      const day = own ?? dayOf(card.targetDate);
      if (!day) continue;
      const assigned: AssignedDay = {
        packageId: item.packageId,
        title: item.title,
        reference: card.reference,
        analystUserId: item.accountableUserId,
        state: item.state,
        day,
        fromTicket: own === null,
      };
      byDay.set(day, [...(byDay.get(day) ?? []), assigned]);
    }
  }
  for (const [day, items] of byDay) {
    byDay.set(
      day,
      [...items].sort((left, right) => left.reference.localeCompare(right.reference)),
    );
  }
  return byDay;
}

function dayOf(value: string | null | undefined): string | null {
  if (!value) return null;
  const day = value.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : null;
}

/** Inclusive day range between two picks, whichever order they were made in. */
export function selectedRange(first: string, second: string): { from: string; to: string } {
  return first <= second ? { from: first, to: second } : { from: second, to: first };
}

export function withinRange(day: string, from: string, to: string): boolean {
  return day >= from && day <= to;
}
