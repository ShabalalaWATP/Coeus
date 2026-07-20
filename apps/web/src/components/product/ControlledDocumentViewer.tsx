type ControlledDocumentViewerProps = {
  kind: string;
  title: string;
  url: string;
};

export function ControlledDocumentViewer({ kind, title, url }: ControlledDocumentViewerProps) {
  if (kind === "image") {
    return <img alt={title} className="controlled-document-viewer" src={url} />;
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
