import { downloadAssetBlob } from "../../lib/api-client/store";

const unsafeFilenameCharacters = new Set(["<", ">", ":", '"', "/", "\\", "|", "?", "*"]);
const leadingDots = /^\.+/;
const nonNameCharacters = /[._\-\s]/g;
const maxFilenameLength = 180;

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
  try {
    anchor.href = url;
    anchor.download = safeDownloadFilename(filename);
    document.body.appendChild(anchor);
    anchor.click();
  } finally {
    anchor.remove();
    URL.revokeObjectURL(url);
  }
}

function safeDownloadFilename(filename: string): string {
  const sanitised = Array.from(filename.trim(), (character) =>
    isUnsafeFilenameCharacter(character) ? "_" : character,
  )
    .join("")
    .replace(leadingDots, "")
    .trim()
    .slice(0, maxFilenameLength);
  return sanitised.replace(nonNameCharacters, "") === "" ? "asset-download" : sanitised;
}

function isUnsafeFilenameCharacter(character: string): boolean {
  return character.charCodeAt(0) < 32 || unsafeFilenameCharacters.has(character);
}
