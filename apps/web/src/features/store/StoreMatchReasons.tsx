import { formatSignal, matchSummary } from "./store-match-language";

type StoreMatchReasonsProps = {
  reasons: string[];
  show: boolean;
};

export function StoreMatchReasons({ reasons, show }: StoreMatchReasonsProps) {
  const signals = reasons.filter((reason) => reason !== "visible");
  const summary = matchSummary(signals);
  if (!show || summary === null) {
    return null;
  }
  return (
    <p className="store-match">
      <span className="store-match__summary">{summary}</span>
      <span className="store-match__detail">{signals.map(formatSignal).join(" · ")}</span>
    </p>
  );
}
