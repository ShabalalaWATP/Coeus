import { lazy, Suspense } from "react";

const ControlledPdfViewer = lazy(() =>
  import("./ControlledPdfViewer").then((module) => ({
    default: module.ControlledPdfViewer,
  })),
);

type ControlledDocumentViewerProps = {
  kind: string;
  mimeType?: string;
  title: string;
  url: string;
};

export function ControlledDocumentViewer({
  kind,
  mimeType,
  title,
  url,
}: ControlledDocumentViewerProps) {
  if (kind === "image") {
    return <img alt={title} className="controlled-document-viewer" src={url} />;
  }
  if (kind === "pdf" || mimeType === "application/pdf") {
    return (
      <Suspense fallback={<p role="status">Preparing PDF renderer…</p>}>
        <ControlledPdfViewer title={title} url={url} />
      </Suspense>
    );
  }
  return (
    <iframe
      className="controlled-document-viewer"
      referrerPolicy="no-referrer"
      sandbox=""
      src={url}
      title={title}
    />
  );
}
