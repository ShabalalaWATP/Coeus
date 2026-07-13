import { Lightbulb, Upload } from "lucide-react";
import type { ChangeEvent, Dispatch, SetStateAction } from "react";

import { productTypeOptions } from "./store-options";
import type { AccessControlGroup } from "../../lib/api-client/access";
import type { MetadataSuggestion, StoreProduct } from "../../lib/api-client/store";
import type { ProductUploadFormState } from "./product-upload-model";

type ProductUploadFormProps = {
  acgs: AccessControlGroup[];
  acgsFailed: boolean;
  acgsLoading: boolean;
  actionError: string | null;
  created: StoreProduct | undefined;
  createPending: boolean;
  form: ProductUploadFormState;
  hasSelectedVisibleAcg: boolean;
  hasVisibleAcgs: boolean;
  onCreate: () => void;
  onRetryAcgs: () => void;
  onSetAssetFile: Dispatch<SetStateAction<File | null>>;
  onSetForm: Dispatch<SetStateAction<ProductUploadFormState>>;
  onSuggest: () => void;
  suggestion: MetadataSuggestion | undefined;
  suggestPending: boolean;
};

export function ProductUploadForm({
  acgs,
  acgsFailed,
  acgsLoading,
  actionError,
  created,
  createPending,
  form,
  hasSelectedVisibleAcg,
  hasVisibleAcgs,
  onCreate,
  onRetryAcgs,
  onSetAssetFile,
  onSetForm,
  onSuggest,
  suggestion,
  suggestPending,
}: ProductUploadFormProps) {
  return (
    <form
      className="surface upload-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (!hasSelectedVisibleAcg) {
          return;
        }
        onCreate();
      }}
    >
      <section className="upload-grid">
        <label>
          Title
          <input name="title" onChange={handleChange(onSetForm)} value={form.title} />
        </label>
        <label>
          Product type
          <select name="productType" onChange={handleChange(onSetForm)} value={form.productType}>
            {productTypeOptions.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Summary
          <textarea name="summary" onChange={handleChange(onSetForm)} value={form.summary} />
        </label>
        <label>
          Description
          <textarea
            name="description"
            onChange={handleChange(onSetForm)}
            value={form.description}
          />
        </label>
        <label>
          Owner team
          <select name="ownerTeam" onChange={handleChange(onSetForm)} value={form.ownerTeam}>
            <option value="RFA">RFA</option>
            <option value="Collection">Collection</option>
          </select>
        </label>
        <div className="upload-field">
          <label htmlFor="product-acg">ACG</label>
          <select
            aria-describedby={
              !acgsLoading && !acgsFailed && hasVisibleAcgs && !hasSelectedVisibleAcg
                ? "product-acg-hint"
                : undefined
            }
            disabled={acgsLoading || acgsFailed}
            id="product-acg"
            name="acgId"
            onChange={handleChange(onSetForm)}
            value={form.acgId}
          >
            <option value="">Select visible ACG</option>
            {acgs.map((acg) => (
              <option key={acg.id} value={acg.id}>
                {acg.code}
              </option>
            ))}
          </select>
          {!acgsLoading && !acgsFailed && hasVisibleAcgs && !hasSelectedVisibleAcg ? (
            <small className="field-hint" id="product-acg-hint">
              Select an ACG before registering.
            </small>
          ) : null}
        </div>
        <label>
          Region
          <input name="areaOrRegion" onChange={handleChange(onSetForm)} value={form.areaOrRegion} />
        </label>
        <label>
          Classification
          <input
            min="0"
            max="5"
            name="classificationLevel"
            onChange={handleChange(onSetForm)}
            type="number"
            value={form.classificationLevel}
          />
        </label>
        <label>
          Status
          <select name="status" onChange={handleChange(onSetForm)} value={form.status}>
            <option value="draft">Draft</option>
            <option value="published">Published</option>
          </select>
        </label>
        <label>
          Tags
          <input name="tags" onChange={handleChange(onSetForm)} value={form.tags} />
        </label>
        <label>
          Source type
          <input name="sourceType" onChange={handleChange(onSetForm)} value={form.sourceType} />
        </label>
        <label>
          Asset name
          <input name="assetName" onChange={handleChange(onSetForm)} value={form.assetName} />
        </label>
        <label>
          Asset file
          <input name="assetFile" onChange={handleFile(onSetForm, onSetAssetFile)} type="file" />
        </label>
        <label>
          SHA-256
          <input name="sha256" onChange={handleChange(onSetForm)} value={form.sha256} />
        </label>
      </section>
      {acgsFailed ? (
        <div className="workspace-alert" role="alert">
          <span>Access groups could not be loaded. Refresh and try again.</span>
          <button onClick={onRetryAcgs} type="button">
            Retry access groups
          </button>
        </div>
      ) : null}
      {!acgsLoading && !acgsFailed && !hasVisibleAcgs ? (
        <div className="workspace-alert" role="alert">
          <span>
            No visible access groups are available. Ask an administrator to add you to an active ACG
            before registering products.
          </span>
        </div>
      ) : null}
      <div className="store-actions">
        <button disabled={suggestPending} onClick={onSuggest} type="button">
          <Lightbulb aria-hidden="true" size={18} />
          Suggest metadata
        </button>
        <button
          disabled={createPending || acgsLoading || acgsFailed || !hasSelectedVisibleAcg}
          type="submit"
        >
          <Upload aria-hidden="true" size={18} />
          Register product
        </button>
      </div>
      {suggestion?.semanticLabels.length ? (
        <div className="store-facets" aria-label="Suggested semantic labels">
          {suggestion.semanticLabels.map((label) => (
            <span className="store-chip store-chip--semantic" key={label}>
              {label}
            </span>
          ))}
        </div>
      ) : null}
      {created !== undefined ? (
        <p className="store-success">
          Created {created.reference}: {created.title}
        </p>
      ) : null}
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </form>
  );
}

function handleChange(setForm: Dispatch<SetStateAction<ProductUploadFormState>>) {
  return (event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };
}

function handleFile(
  setForm: Dispatch<SetStateAction<ProductUploadFormState>>,
  setAssetFile: Dispatch<SetStateAction<File | null>>,
) {
  return (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setAssetFile(file);
    if (file === null) {
      return;
    }
    const assetType = file.name.split(".").pop() || "binary";
    setForm((current) => ({
      ...current,
      assetName: file.name,
      assetType,
      mimeType: file.type || "application/octet-stream",
      sizeBytes: String(file.size),
    }));
  };
}
