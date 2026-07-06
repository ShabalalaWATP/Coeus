import type { AccessControlGroup } from "../../lib/api-client/client";
import type { QcProduct } from "../../lib/api-client/qc";
import type { QcReleaseFormState } from "./qc-release-model";

export function MetadataChecks({ acgId, product }: { acgId: string; product: QcProduct }) {
  const draft = product.latestDraft;
  const checks: [string, boolean][] = [
    ["Draft content", Boolean(draft?.content)],
    ["Product asset", Boolean(draft?.assets.length)],
    ["ACG selected", acgId.trim().length > 0],
    ["Releasability checked", true],
  ];
  return (
    <section className="qc-panel">
      <h3>Release checks</h3>
      <ul className="qc-check-list">
        {checks.map(([label, passed]) => (
          <li key={label}>
            <span>{label}</span>
            <strong>{passed ? "Ready" : "Missing"}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ReleaseForm({
  acgs,
  form,
  onChange,
}: {
  acgs: AccessControlGroup[];
  form: QcReleaseFormState;
  onChange: (form: QcReleaseFormState) => void;
}) {
  return (
    <section className="qc-panel">
      <h3>Release metadata</h3>
      <div className="qc-form-grid">
        <label>
          Classification
          <input
            max="5"
            min="0"
            onChange={(event) => onChange({ ...form, classificationLevel: event.target.value })}
            type="number"
            value={form.classificationLevel}
          />
        </label>
        <label>
          ACG
          <select
            onChange={(event) => onChange({ ...form, acgId: event.target.value })}
            value={form.acgId}
          >
            <option value="">Use first visible ACG</option>
            {acgs.map((acg) => (
              <option key={acg.id} value={acg.id}>
                {acg.code}
              </option>
            ))}
          </select>
        </label>
        <label>
          Releasability
          <input
            onChange={(event) => onChange({ ...form, releasability: event.target.value })}
            value={form.releasability}
          />
        </label>
        <label>
          Handling caveats
          <input
            onChange={(event) => onChange({ ...form, caveats: event.target.value })}
            value={form.caveats}
          />
        </label>
        <label>
          Approval reason
          <textarea
            onChange={(event) => onChange({ ...form, reason: event.target.value })}
            value={form.reason}
          />
        </label>
        <label>
          Rejection reason
          <textarea
            onChange={(event) => onChange({ ...form, rejectionReason: event.target.value })}
            value={form.rejectionReason}
          />
        </label>
      </div>
    </section>
  );
}

export function PostReleaseStatus({ product }: { product: QcProduct }) {
  if (product.ingestedProduct === null) {
    return null;
  }
  const released = product.disseminations.length > 0;
  return (
    <section className="qc-panel qc-success">
      <h3>{released ? "Released to customer" : "Awaiting manager release"}</h3>
      <p>
        {product.ingestedProduct.reference}: {product.ingestedProduct.title}
      </p>
      <p>{product.indexRecords.at(-1)?.status ?? "queued"} in Intelligence Store indexing.</p>
      {released ? (
        <p>{product.feedbackRequests.length} feedback request created.</p>
      ) : (
        <p>The route manager performs the final release and customer notification.</p>
      )}
    </section>
  );
}
