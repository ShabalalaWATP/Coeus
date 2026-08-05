import type {
  OrganisationUnit,
  SplitImpact,
  SplitPlan,
  SplitRequest,
} from "../../lib/api-client/organisation-admin";

export type SplitSuccessor = SplitRequest["successors"][number];
export type SplitMoveKind = "child_unit" | "membership" | "task";

export function buildSplitPlan(
  request: SplitRequest,
  impact: SplitImpact,
  targets: Partial<Record<SplitMoveKind, string>>,
): SplitPlan {
  return {
    request,
    dispositions: impact.records.map((record) => {
      const action = splitAction(record.kind);
      const target = action === "move" ? targets[record.kind as SplitMoveKind] : null;
      return {
        action,
        expectedVersion: record.version,
        kind: record.kind,
        recordId: record.recordId,
        replacementId:
          record.kind === "membership" && action === "move" ? crypto.randomUUID() : null,
        targetUnitId: target ?? null,
      };
    }),
  };
}

function splitAction(kind: SplitImpact["records"][number]["kind"]) {
  if (kind === "grant") return "revoke" as const;
  if (kind === "pending_transfer") return "cancel" as const;
  if (kind === "delivery_profile" || kind === "capability") return "end" as const;
  return "move" as const;
}

export function blankSuccessor(source: OrganisationUnit): SplitSuccessor {
  return {
    category: source.category,
    description: "",
    name: "",
    shortName: "",
    timeZone: source.timeZone,
    unitId: crypto.randomUUID(),
  };
}

export function updateSuccessor(
  items: SplitSuccessor[],
  change: (value: SplitSuccessor[]) => void,
  index: number,
  key: "name" | "shortName",
  value: string,
) {
  change(items.map((item, itemIndex) => (itemIndex === index ? { ...item, [key]: value } : item)));
}
