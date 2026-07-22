import { useEffect, useState } from "react";

import { ControlledDocumentViewer } from "../../components/product/ControlledDocumentViewer";
import {
  previewStoreAssetBlob,
  type AssetAccessGrant,
  type StoreAsset,
} from "../../lib/api-client/store";

export function StoreAssetPreview({
  asset,
  grant,
  productId,
}: {
  asset: StoreAsset;
  grant?: AssetAccessGrant;
  productId: string;
}) {
  const preview = useControlledPreview(productId, asset.id, grant);
  if (preview.status === "error") {
    return <p className="workspace-alert">A safe inline preview is not available for this file.</p>;
  }
  if (preview.url === null) return <p>Preparing controlled preview…</p>;
  return (
    <section className="store-asset-preview" aria-label={`${asset.name} preview`}>
      <h3>Controlled preview</h3>
      <ControlledDocumentViewer kind={asset.previewKind} title={asset.name} url={preview.url} />
      <small>Preview content is access controlled and is not cached by Istari.</small>
    </section>
  );
}

function useControlledPreview(
  productId: string,
  assetId: string,
  grant: AssetAccessGrant | undefined,
) {
  const [preview, setPreview] = useState<{
    status: "error" | "pending" | "ready";
    url: string | null;
  }>({ status: "pending", url: null });
  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    const expiryTimer =
      grant === undefined
        ? undefined
        : setTimeout(
            () => setPreview({ status: "error", url: null }),
            Math.max(0, grant.expiresInSeconds * 1_000),
          );
    setPreview({ status: "pending", url: null });
    if (grant === undefined) {
      return () => {
        active = false;
      };
    }
    void previewStoreAssetBlob(productId, assetId, grant.downloadToken).then(
      (blob) => {
        if (!active || typeof URL.createObjectURL !== "function") return;
        objectUrl = URL.createObjectURL(blob);
        setPreview({ status: "ready", url: objectUrl });
      },
      () => {
        if (active) setPreview({ status: "error", url: null });
      },
    );
    return () => {
      active = false;
      if (expiryTimer !== undefined) clearTimeout(expiryTimer);
      if (objectUrl !== undefined && typeof URL.revokeObjectURL === "function") {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [assetId, grant, productId]);
  return preview;
}
