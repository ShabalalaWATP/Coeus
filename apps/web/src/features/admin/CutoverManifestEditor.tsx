import { HASH_FIELDS, REFERENCE_FIELDS } from "./cutover-manifest";
import type { CutoverManifest } from "../../lib/api-client/cutover-release";

type Props = {
  locked: boolean;
  value: CutoverManifest;
  onChange: (value: CutoverManifest) => void;
};

export function CutoverManifestEditor({ locked, onChange, value }: Props) {
  const update = (field: keyof CutoverManifest, next: string) => {
    onChange({ ...value, [field]: next.trim() });
  };

  return (
    <details className="cutover-release__manifest">
      <summary>{locked ? "Candidate evidence" : "Enter candidate evidence"}</summary>
      <p>
        Every reference and SHA-256 digest identifies one immutable release candidate. Evidence is
        checked again by the server for every slice.
      </p>
      <div className="cutover-release__manifest-fields">
        {REFERENCE_FIELDS.map(([field, label]) => (
          <label key={field}>
            {label}
            <input
              disabled={locked}
              maxLength={128}
              onChange={(event) => update(field, event.target.value)}
              pattern="[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,127}"
              required
              value={value[field]}
            />
          </label>
        ))}
        {HASH_FIELDS.map(([field, label]) => (
          <label key={field}>
            {label}
            <input
              autoCapitalize="none"
              autoCorrect="off"
              disabled={locked}
              maxLength={64}
              minLength={64}
              onChange={(event) => update(field, event.target.value.toLowerCase())}
              pattern="[0-9a-f]{64}"
              required
              spellCheck={false}
              value={value[field]}
            />
          </label>
        ))}
      </div>
    </details>
  );
}
