import { useId } from "react";

type StoreMatchReasonsProps = {
  reasons: string[];
  show: boolean;
};

export function StoreMatchReasons({ reasons, show }: StoreMatchReasonsProps) {
  const visibleReasons = reasons.filter((reason) => reason !== "visible").slice(0, 3);
  const headingId = useId();
  if (!show || visibleReasons.length === 0) {
    return null;
  }
  return (
    <div className="store-match-reasons">
      <span id={headingId}>Why it matched</span>
      <ul aria-labelledby={headingId}>
        {visibleReasons.map((reason, index) => (
          <li key={`${reason}-${index}`}>
            <small>{formatReason(reason)}</small>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatReason(reason: string) {
  if (reason.startsWith("lexical-rank:")) {
    return `Text rank ${reason.split(":")[1]}`;
  }
  if (reason.startsWith("vector-similarity:")) {
    return `Semantic ${Math.round(Number(reason.split(":")[1]) * 100)}%`;
  }
  if (reason.startsWith("semantic-label:")) {
    return `Label ${reason.split(":")[1]}`;
  }
  if (reason.startsWith("full-text:")) {
    return `Term ${reason.split(":")[1]}`;
  }
  if (reason === "retrieval:lexical-only") {
    return "Lexical fallback";
  }
  if (reason.startsWith("metadata:")) {
    return `Metadata ${reason.split(":")[1]}`;
  }
  return reason;
}
