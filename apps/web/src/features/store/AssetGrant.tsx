import { Download, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { downloadAssetToDevice } from "./asset-download";
import type { AssetAccessGrant } from "../../lib/api-client/store";

type AssetGrantProps = {
  assetId: string;
  assetName: string;
  grant?: AssetAccessGrant;
  productId: string;
  status: string;
};

export function AssetGrant({ assetId, assetName, grant, productId, status }: AssetGrantProps) {
  const [downloadError, setDownloadError] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  if (status === "error") {
    return (
      <div className="asset-grant asset-grant--denied">
        <ShieldAlert aria-hidden="true" size={18} />
        <span>Asset access denied or unavailable.</span>
      </div>
    );
  }
  if (grant === undefined) {
    return <div className="asset-grant">Preparing controlled access</div>;
  }

  async function download() {
    setDownloadError(false);
    setIsDownloading(true);
    try {
      await downloadAssetToDevice(productId, assetId, grant?.downloadToken ?? "", assetName);
    } catch {
      setDownloadError(true);
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="asset-grant">
      <Download aria-hidden="true" size={18} />
      <div>
        <strong>Download authorised.</strong>{" "}
        <button
          className="asset-grant__download"
          disabled={isDownloading}
          onClick={() => void download()}
          type="button"
        >
          {isDownloading ? "Downloading asset" : "Download asset"}
        </button>
        <small> Expires in {Math.round(grant.expiresInSeconds / 60)} minutes.</small>
        {downloadError ? (
          <p className="auth-error" role="alert">
            The asset could not be downloaded. Request access again and retry.
          </p>
        ) : null}
      </div>
    </div>
  );
}
