type StoreMatchReasonsProps = {
  reasons: string[];
  show: boolean;
};

export function StoreMatchReasons({ reasons, show }: StoreMatchReasonsProps) {
  const visibleReasons = reasons.filter((reason) => reason !== "visible").slice(0, 3);
  if (!show || visibleReasons.length === 0) {
    return null;
  }
  return (
    <div aria-label="Why this matched" className="store-match-reasons">
      <span>Why it matched</span>
      {visibleReasons.map((reason) => (
        <small key={reason}>{formatReason(reason)}</small>
      ))}
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
