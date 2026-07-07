import { downloadAssetBlob } from "../../lib/api-client/store";

/**
 * Fetches the asset with the short-lived token in the X-Asset-Token header
 * and hands the blob to the browser as a normal file download.
 */
export async function downloadAssetToDevice(
  productId: string,
  assetId: string,
  token: string,
  filename: string,
) {
  const blob = await downloadAssetBlob(productId, assetId, token);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
