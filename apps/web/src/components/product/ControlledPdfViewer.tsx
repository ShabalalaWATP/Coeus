import { useEffect, useRef, useState } from "react";
import type { PDFDocumentLoadingTask, PDFDocumentProxy } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

type PreviewState = "error" | "loading" | "ready" | "unsupported";

export function ControlledPdfViewer({ title, url }: { title: string; url: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [document, setDocument] = useState<PDFDocumentProxy>();
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [state, setState] = useState<PreviewState>("loading");

  useEffect(() => {
    let active = true;
    let loadingTask: PDFDocumentLoadingTask | undefined;
    setDocument(undefined);
    setPageNumber(1);
    setPageCount(0);
    setState("loading");

    if (globalThis.DOMMatrix === undefined) {
      setState("unsupported");
      return () => {
        active = false;
      };
    }

    void (async () => {
      try {
        const { GlobalWorkerOptions, getDocument } = await import("pdfjs-dist");
        if (!active) return;
        GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
        loadingTask = getDocument({ stopAtErrors: true, url });
        const loadedDocument = await loadingTask.promise;
        if (!active) return;
        setDocument(loadedDocument);
        setPageCount(loadedDocument.numPages);
      } catch {
        if (active) setState("error");
      }
    })();

    return () => {
      active = false;
      void loadingTask?.destroy();
    };
  }, [url]);

  useEffect(() => {
    if (document === undefined) return;
    let active = true;
    let cancelRender: (() => void) | undefined;
    setState("loading");
    void (async () => {
      try {
        const page = await document.getPage(pageNumber);
        if (!active || canvasRef.current === null) return;
        const viewport = page.getViewport({ scale: 1.35 });
        canvasRef.current.width = Math.ceil(viewport.width);
        canvasRef.current.height = Math.ceil(viewport.height);
        const renderTask = page.render({ canvas: canvasRef.current, viewport });
        cancelRender = () => renderTask.cancel();
        await renderTask.promise;
        if (active) setState("ready");
      } catch {
        if (active) setState("error");
      }
    })();
    return () => {
      active = false;
      cancelRender?.();
    };
  }, [document, pageNumber]);

  return (
    <div className="controlled-pdf-viewer" aria-label={`${title} PDF preview`}>
      <div className="controlled-pdf-viewer__toolbar">
        <button
          disabled={pageNumber <= 1 || state === "loading"}
          onClick={() => setPageNumber((current) => current - 1)}
          type="button"
        >
          Previous page
        </button>
        <span aria-live="polite">
          Page {pageNumber} of {pageCount || "…"}
        </span>
        <button
          disabled={pageNumber >= pageCount || state === "loading"}
          onClick={() => setPageNumber((current) => current + 1)}
          type="button"
        >
          Next page
        </button>
      </div>
      <div className="controlled-pdf-viewer__stage">
        {state === "loading" ? <p role="status">Rendering controlled preview…</p> : null}
        {state === "error" ? (
          <p className="workspace-alert" role="alert">
            This PDF could not be rendered safely. Use the authorised download instead.
          </p>
        ) : null}
        {state === "unsupported" ? (
          <p className="workspace-alert" role="status">
            This browser cannot render the controlled PDF preview. Use the authorised download
            instead.
          </p>
        ) : null}
        <canvas
          aria-label={`${title}, page ${pageNumber}`}
          className="controlled-pdf-viewer__canvas"
          hidden={state !== "ready"}
          ref={canvasRef}
          role="img"
        />
      </div>
    </div>
  );
}
