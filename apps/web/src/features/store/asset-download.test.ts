import { downloadAssetToDevice } from "./asset-download";
import { stubObjectUrls } from "./store-test-fixtures";

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

test("sanitises asset filenames before handing them to the browser", async () => {
  const blob = new Blob(["mock"]);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) }),
  );
  const { revokeObjectURL } = stubObjectUrls();
  const anchor = document.createElement("a");
  vi.spyOn(document, "createElement").mockReturnValue(anchor);
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

  await downloadAssetToDevice("product-1", "asset-1", "download-token", "../draft:brief?.pdf");

  expect(anchor.download).toBe("_draft_brief_.pdf");
  expect(anchor.href).toBe("blob:mock-asset");
  expect(click).toHaveBeenCalledTimes(1);
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-asset");
  expect(document.body.querySelector("a")).not.toBeInTheDocument();
});

test("uses a safe fallback filename when the source name has no usable characters", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(["mock"])) }),
  );
  stubObjectUrls();
  const anchor = document.createElement("a");
  vi.spyOn(document, "createElement").mockReturnValue(anchor);
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

  await downloadAssetToDevice("product-1", "asset-1", "download-token", " ../<> ");

  expect(anchor.download).toBe("asset-download");
});

test("cleans up object URLs when browser download dispatch fails", async () => {
  const blob = new Blob(["mock"]);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) }),
  );
  const { revokeObjectURL } = stubObjectUrls();
  const anchor = document.createElement("a");
  vi.spyOn(document, "createElement").mockReturnValue(anchor);
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
    throw new Error("download blocked");
  });

  await expect(
    downloadAssetToDevice("product-1", "asset-1", "download-token", "brief.pdf"),
  ).rejects.toThrow("download blocked");

  expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-asset");
  expect(document.body.querySelector("a")).not.toBeInTheDocument();
});
