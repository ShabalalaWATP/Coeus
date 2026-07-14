import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ProductUploadForm } from "./ProductUploadForm";
import {
  initialProductUploadForm,
  manualAssetMetadata,
  metadataSuggestionInput,
  productUploadMetadata,
} from "./product-upload-model";
import { listAcgs } from "../../lib/api-client/access";
import {
  createStoreProduct,
  suggestStoreMetadata,
  uploadStoreProduct,
} from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

export default function ProductUploadPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(initialProductUploadForm);
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const acgsQuery = useQuery({
    queryKey: ["acgs"],
    queryFn: listAcgs,
    retry: false,
  });
  const acgs = acgsQuery.data ?? [];
  const hasVisibleAcgs = acgs.length > 0;
  const hasSelectedVisibleAcg = acgs.some((acg) => acg.id === form.acgId);
  const csrfToken = session?.csrfToken ?? "";
  const canPublish = session?.user.permissions.includes("product:publish") ?? false;
  const { actionError, clearActionError, failActionWith } = useActionError();
  const createMutation = useMutation({
    onError: failActionWith("Product registration failed. Check the metadata and try again."),
    onMutate: clearActionError,
    onSuccess: () => {
      // Newly registered products must appear in store searches immediately.
      void queryClient.invalidateQueries({ queryKey: ["store-products"] });
    },
    mutationFn: () => {
      const payload = productUploadMetadata(form);
      if (assetFile !== null) {
        return uploadStoreProduct(payload, assetFile, csrfToken);
      }
      return createStoreProduct(
        {
          ...payload,
          assets: [manualAssetMetadata(form)],
        },
        csrfToken,
      );
    },
  });
  const suggestMutation = useMutation({
    mutationFn: () => suggestStoreMetadata(metadataSuggestionInput(form), csrfToken),
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

      <ProductUploadForm
        acgs={acgs}
        acgsFailed={acgsQuery.isError}
        acgsLoading={acgsQuery.isLoading}
        actionError={actionError}
        canPublish={canPublish}
        created={created}
        createPending={createMutation.isPending}
        form={form}
        hasSelectedVisibleAcg={hasSelectedVisibleAcg}
        hasVisibleAcgs={hasVisibleAcgs}
        onCreate={() => createMutation.mutate()}
        onRetryAcgs={() => void acgsQuery.refetch()}
        onSetAssetFile={setAssetFile}
        onSetForm={setForm}
        onSuggest={() => suggestMutation.mutate()}
        suggestion={suggestMutation.data}
        suggestPending={suggestMutation.isPending}
      />
    </div>
  );
}
