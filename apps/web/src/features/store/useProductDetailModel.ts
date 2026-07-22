import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api-client/client";
import { breakGlassStoreProduct, getStoreProduct } from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";
import { backNavigationFor } from "./store-navigation";
import { useEphemeralAssetAccess } from "./useEphemeralAssetAccess";

export function useProductDetailModel() {
  const { assetId, productId } = useStoreRouteIds();
  const { session } = useAuth();
  const [breakGlassReason, setBreakGlassReason] = useState<string | null>(null);
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const productQuery = useQuery({
    enabled: productId !== undefined,
    queryKey: ["store-product", productId],
    queryFn: () => getStoreProduct(productId ?? ""),
    retry: false,
  });
  const breakGlassMutation = useMutation({
    mutationFn: (reason: string) =>
      breakGlassStoreProduct(productId ?? "", reason, session?.csrfToken ?? ""),
    onSuccess: (_product, reason) => setBreakGlassReason(reason),
  });
  const hasBreakGlassProduct = breakGlassMutation.data !== undefined && breakGlassReason !== null;
  const canDownload = session?.user.permissions.includes("product:download") ?? false;
  const canRequestAssetAccess = canDownload || hasBreakGlassProduct;
  const access = useEphemeralAssetAccess({
    assetId,
    breakGlassReason: hasBreakGlassProduct ? breakGlassReason : null,
    csrfToken: session?.csrfToken ?? "",
    enabled:
      productId !== undefined &&
      assetId !== undefined &&
      canRequestAssetAccess &&
      (productQuery.data !== undefined || hasBreakGlassProduct),
    productId,
  });
  const product = breakGlassMutation.data ?? productQuery.data;

  return {
    access,
    assetId,
    back: backNavigationFor(from),
    canRequestAssetAccess,
    from,
    product,
    productQuery,
    productNotFound: productQuery.isError && isNotFound(productQuery.error),
    canBreakGlass:
      productId !== undefined &&
      (session?.user.permissions.includes("product:read_restricted") ?? false),
    breakGlassPending: breakGlassMutation.isPending,
    breakGlassError: breakGlassMutation.isError,
    requestBreakGlass: (reason: string) => breakGlassMutation.mutate(reason),
  };
}

function isNotFound(error: Error) {
  return error instanceof ApiError && error.status === 404;
}

function useStoreRouteIds() {
  const params = useParams();
  const location = useLocation();
  const match = /\/store\/products\/([^/]+)(?:\/assets\/([^/]+))?/.exec(location.pathname);
  return { productId: params.productId ?? match?.[1], assetId: params.assetId ?? match?.[2] };
}
