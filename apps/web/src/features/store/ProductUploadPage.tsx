import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Lightbulb, Upload } from "lucide-react";
import { useState, type ChangeEvent, type Dispatch, type SetStateAction } from "react";
import { Link } from "react-router-dom";

import { csvToValues, productTypeOptions } from "./store-options";
import { apiClient } from "../../lib/api-client/client";
import {
  createStoreProduct,
  suggestStoreMetadata,
  uploadStoreProduct,
} from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

const initialForm = {
  title: "Mock Harbour Activity Brief",
  summary: "MOCK DATA ONLY assessment of harbour activity.",
  description: "Synthetic product metadata for controlled store upload.",
  productType: "assessment_report",
  sourceType: "finished_assessment",
  ownerTeam: "RFA",
  areaOrRegion: "Baltic ports",
  classificationLevel: "2",
  tags: "ports, activity",
  assetName: "harbour-brief.pdf",
  assetType: "pdf",
  mimeType: "application/pdf",
  sizeBytes: "42000",
  sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  acgId: "",
};

export default function ProductUploadPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(initialForm);
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const acgsQuery = useQuery({
    queryKey: ["acgs"],
    queryFn: () => apiClient.listAcgs(),
    retry: false,
  });
  const acgs = acgsQuery.data ?? [];
  const hasVisibleAcgs = acgs.length > 0;
  const hasSelectedVisibleAcg = acgs.some((acg) => acg.id === form.acgId);
  const csrfToken = session?.csrfToken ?? "";
  const { actionError, clearActionError, failActionWith } = useActionError();
  const createMutation = useMutation({
    onError: failActionWith("Product registration failed. Check the metadata and try again."),
    onMutate: clearActionError,
    onSuccess: () => {
      // Newly registered products must appear in store searches immediately.
      void queryClient.invalidateQueries({ queryKey: ["store-products"] });
    },
    mutationFn: () => {
      const payload = {
        title: form.title,
        summary: form.summary,
        description: form.description,
        productType: form.productType,
        sourceType: form.sourceType,
        ownerTeam: form.ownerTeam,
        areaOrRegion: form.areaOrRegion,
        classificationLevel: Number(form.classificationLevel),
        releasability: ["MOCK"],
        handlingCaveats: ["MOCK DATA ONLY"],
        tags: csvToValues(form.tags),
        acgIds: [form.acgId],
        status: "published",
        geojsonRef: form.productType === "geographic_product" ? "mock://geojson/layer" : null,
      };
      if (assetFile !== null) {
        return uploadStoreProduct(payload, assetFile, csrfToken);
      }
      return createStoreProduct(
        {
          ...payload,
          assets: [
            {
              name: form.assetName,
              assetType: form.assetType,
              mimeType: form.mimeType,
              sizeBytes: Number(form.sizeBytes),
              sha256: form.sha256,
            },
          ],
        },
        csrfToken,
      );
    },
  });
  const suggestMutation = useMutation({
    mutationFn: () =>
      suggestStoreMetadata(
        {
          title: form.title,
          summary: form.summary,
          productType: form.productType,
          areaOrRegion: form.areaOrRegion,
        },
        csrfToken,
      ),
    onSuccess: (suggestion) =>
      setForm((current) => ({ ...current, tags: suggestion.tags.join(", ") })),
    onError: failActionWith("Metadata suggestions could not be generated. Try again."),
    onMutate: clearActionError,
  });
  const created = createMutation.data;

  return (
    <div className="store-page">
      <section className="overview-hero" aria-labelledby="upload-title">
        <div>
          <h1 id="upload-title">Upload Product</h1>
          <p>Register existing product metadata and controlled asset hashes.</p>
        </div>
        <Link className="store-action store-action--secondary" to="/store">
          <ArrowLeft aria-hidden="true" size={18} />
          Back to store
        </Link>
      </section>

      <form
        className="surface upload-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!hasSelectedVisibleAcg) {
            return;
          }
          createMutation.mutate();
        }}
      >
        <section className="upload-grid">
          <label>
            Title
            <input name="title" onChange={handleChange(setForm)} value={form.title} />
          </label>
          <label>
            Product type
            <select name="productType" onChange={handleChange(setForm)} value={form.productType}>
              {productTypeOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Summary
            <textarea name="summary" onChange={handleChange(setForm)} value={form.summary} />
          </label>
          <label>
            Description
            <textarea
              name="description"
              onChange={handleChange(setForm)}
              value={form.description}
            />
          </label>
          <label>
            Owner team
            <select name="ownerTeam" onChange={handleChange(setForm)} value={form.ownerTeam}>
              <option value="RFA">RFA</option>
              <option value="Collection">Collection</option>
            </select>
          </label>
          <div className="upload-field">
            <label htmlFor="product-acg">ACG</label>
            <select
              aria-describedby={
                !acgsQuery.isLoading &&
                !acgsQuery.isError &&
                hasVisibleAcgs &&
                !hasSelectedVisibleAcg
                  ? "product-acg-hint"
                  : undefined
              }
              disabled={acgsQuery.isLoading || acgsQuery.isError}
              id="product-acg"
              name="acgId"
              onChange={handleChange(setForm)}
              value={form.acgId}
            >
              <option value="">Select visible ACG</option>
              {acgs.map((acg) => (
                <option key={acg.id} value={acg.id}>
                  {acg.code}
                </option>
              ))}
            </select>
            {!acgsQuery.isLoading &&
            !acgsQuery.isError &&
            hasVisibleAcgs &&
            !hasSelectedVisibleAcg ? (
              <small className="field-hint" id="product-acg-hint">
                Select an ACG before registering.
              </small>
            ) : null}
          </div>
          <label>
            Region
            <input name="areaOrRegion" onChange={handleChange(setForm)} value={form.areaOrRegion} />
          </label>
          <label>
            Classification
            <input
              min="0"
              max="5"
              name="classificationLevel"
              onChange={handleChange(setForm)}
              type="number"
              value={form.classificationLevel}
            />
          </label>
          <label>
            Tags
            <input name="tags" onChange={handleChange(setForm)} value={form.tags} />
          </label>
          <label>
            Source type
            <input name="sourceType" onChange={handleChange(setForm)} value={form.sourceType} />
          </label>
          <label>
            Asset name
            <input name="assetName" onChange={handleChange(setForm)} value={form.assetName} />
          </label>
          <label>
            Asset file
            <input name="assetFile" onChange={handleFile(setForm, setAssetFile)} type="file" />
          </label>
          <label>
            SHA-256
            <input name="sha256" onChange={handleChange(setForm)} value={form.sha256} />
          </label>
        </section>
        {acgsQuery.isError ? (
          <div className="workspace-alert" role="alert">
            <span>Access groups could not be loaded. Refresh and try again.</span>
            <button onClick={() => void acgsQuery.refetch()} type="button">
              Retry access groups
            </button>
          </div>
        ) : null}
        {!acgsQuery.isLoading && !acgsQuery.isError && !hasVisibleAcgs ? (
          <div className="workspace-alert" role="alert">
            <span>
              No visible access groups are available. Ask an administrator to add you to an active
              ACG before registering products.
            </span>
          </div>
        ) : null}
        <div className="store-actions">
          <button
            disabled={suggestMutation.isPending}
            onClick={() => suggestMutation.mutate()}
            type="button"
          >
            <Lightbulb aria-hidden="true" size={18} />
            Suggest metadata
          </button>
          <button
            disabled={
              createMutation.isPending ||
              acgsQuery.isLoading ||
              acgsQuery.isError ||
              !hasSelectedVisibleAcg
            }
            type="submit"
          >
            <Upload aria-hidden="true" size={18} />
            Register product
          </button>
        </div>
        {suggestMutation.data?.semanticLabels.length ? (
          <div className="store-facets" aria-label="Suggested semantic labels">
            {suggestMutation.data.semanticLabels.map((label) => (
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
    </div>
  );
}

function handleChange(setForm: Dispatch<SetStateAction<typeof initialForm>>) {
  return (event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };
}

function handleFile(
  setForm: Dispatch<SetStateAction<typeof initialForm>>,
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
