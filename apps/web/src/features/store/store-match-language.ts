/**
 * Turn retrieval signals into words an operator would use.
 *
 * The backend explains a hit with terms like `lexical-rank:1` and
 * `vector-similarity:0.82`. Those are engineering telemetry: useful when
 * diagnosing relevance, meaningless to someone deciding whether to open a
 * report. The summary answers "why am I seeing this?"; the signal list stays
 * available for anyone who needs it.
 */
export function matchSummary(reasons: string[]): string | null {
  const terms = valuesFor(reasons, "full-text:");
  const labels = valuesFor(reasons, "semantic-label:").filter((label) => !terms.includes(label));
  const parts: string[] = [];
  if (terms.length > 0) {
    parts.push(`Matched ${joinWords(terms)}`);
  }
  if (labels.length > 0) {
    parts.push(`${parts.length > 0 ? "related to" : "Related to"} ${joinWords(labels)}`);
  }
  if (parts.length === 0 && reasons.some((reason) => reason.startsWith("vector-similarity:"))) {
    return "Close match on meaning";
  }
  return parts.length > 0 ? parts.join(", ") : null;
}

export function formatSignal(reason: string): string {
  if (reason.startsWith("lexical-rank:")) {
    return `Text rank ${reason.split(":")[1]}`;
  }
  if (reason.startsWith("vector-similarity:")) {
    return `Meaning ${Math.round(Number(reason.split(":")[1]) * 100)}%`;
  }
  if (reason.startsWith("semantic-label:")) {
    return `Label ${reason.split(":")[1]}`;
  }
  if (reason.startsWith("full-text:")) {
    return `Term ${reason.split(":")[1]}`;
  }
  if (reason === "retrieval:lexical-only") {
    return "Wording only";
  }
  if (reason.startsWith("metadata:")) {
    return `Metadata ${reason.split(":")[1]}`;
  }
  return reason;
}

function valuesFor(reasons: string[], prefix: string) {
  return [
    ...new Set(
      reasons
        .filter((reason) => reason.startsWith(prefix))
        .map((reason) => reason.slice(prefix.length))
        .filter((value) => value !== ""),
    ),
  ].slice(0, 3);
}

function joinWords(values: string[]) {
  if (values.length === 1) {
    return values[0];
  }
  return `${values.slice(0, -1).join(", ")} and ${values[values.length - 1]}`;
}
