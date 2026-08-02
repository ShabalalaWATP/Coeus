import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookmarkMinus } from "lucide-react";
import { useEffect, useState } from "react";

import {
  getPersonalStoreLibrary,
  removePersonalStoreProduct,
  savePersonalStoreProduct,
} from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";

export function SaveProductControl({ productId }: { productId: string }) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const library = useQuery({
    enabled: editing,
    queryKey: ["store-library"],
    queryFn: getPersonalStoreLibrary,
  });
  const saved = (library.data?.savedProducts ?? []).find((item) => item.product.id === productId);
  const [folderId, setFolderId] = useState("");
  useEffect(() => setFolderId(saved?.folderId ?? ""), [saved?.folderId]);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["store-library"] });
  const saveMutation = useMutation({
    mutationFn: () =>
      savePersonalStoreProduct(productId, folderId || null, session?.csrfToken ?? ""),
    onSuccess: refresh,
  });
  const removeMutation = useMutation({
    mutationFn: () => removePersonalStoreProduct(productId, session?.csrfToken ?? ""),
    onSuccess: refresh,
  });
  const pending = saveMutation.isPending || removeMutation.isPending;

  if (!editing) {
    return (
      <button
        aria-expanded="false"
        className="store-action"
        onClick={() => setEditing(true)}
        type="button"
      >
        <Bookmark aria-hidden="true" size={17} />
        Save or organise
      </button>
    );
  }

  return (
    <div className="save-product-control" aria-label="Personal library">
      <label>
        Save to
        <select
          disabled={library.isLoading || pending}
          onChange={(event) => setFolderId(event.target.value)}
          value={folderId}
        >
          <option value="">Unfiled</option>
          {(library.data?.folders ?? []).map((folder) => (
            <option key={folder.id} value={folder.id}>
              {folder.name}
            </option>
          ))}
        </select>
      </label>
      <button
        className="store-action"
        disabled={library.isError || pending}
        onClick={() => saveMutation.mutate()}
        type="button"
      >
        <Bookmark aria-hidden="true" size={17} />
        {saved ? "Update saved report" : "Save report"}
      </button>
      {saved ? (
        <button
          className="store-action store-action--secondary"
          disabled={pending}
          onClick={() => removeMutation.mutate()}
          type="button"
        >
          <BookmarkMinus aria-hidden="true" size={17} />
          Remove
        </button>
      ) : null}
      <button
        className="store-action store-action--secondary"
        disabled={pending}
        onClick={() => setEditing(false)}
        type="button"
      >
        Cancel
      </button>
      {library.isError || saveMutation.isError || removeMutation.isError ? (
        <small className="auth-error" role="alert">
          Your library could not be updated. Try again.
        </small>
      ) : null}
    </div>
  );
}
