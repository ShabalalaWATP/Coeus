import { useEffect, useState } from "react";

import {
  breakGlassAssetAccess,
  getAssetAccess,
  type AssetAccessGrant,
} from "../../lib/api-client/store";

export type EphemeralAssetAccess = {
  data?: AssetAccessGrant;
  status: "error" | "pending" | "success";
};

export function useEphemeralAssetAccess({
  assetId,
  breakGlassReason,
  csrfToken,
  enabled,
  productId,
}: {
  assetId?: string;
  breakGlassReason: string | null;
  csrfToken: string;
  enabled: boolean;
  productId?: string;
}): EphemeralAssetAccess {
  const [access, setAccess] = useState<EphemeralAssetAccess>({ status: "pending" });

  useEffect(() => {
    let active = true;
    let expiryTimer: ReturnType<typeof setTimeout> | undefined;
    if (!enabled || productId === undefined || assetId === undefined) {
      setAccess({ status: "pending" });
      return () => {
        active = false;
      };
    }
    setAccess({ status: "pending" });
    const request =
      breakGlassReason === null
        ? getAssetAccess(productId, assetId)
        : breakGlassAssetAccess(productId, assetId, breakGlassReason, csrfToken);
    void request.then(
      (grant) => {
        if (!active) return;
        setAccess({ data: grant, status: "success" });
        expiryTimer = setTimeout(
          () => setAccess({ status: "error" }),
          Math.max(0, grant.expiresInSeconds * 1_000),
        );
      },
      () => {
        if (active) setAccess({ status: "error" });
      },
    );
    return () => {
      active = false;
      if (expiryTimer !== undefined) clearTimeout(expiryTimer);
    };
  }, [assetId, breakGlassReason, csrfToken, enabled, productId]);

  return access;
}
