import { ControlledDocumentViewer } from "../../components/product/ControlledDocumentViewer";
import { workflowProductPreviewUrl, type AnalystTask } from "../../lib/api-client/analyst";

export function SubmissionVersionPreview({ task }: { task: AnalystTask }) {
  const version = task.drafts.at(-1);
  const asset = version?.assets[0];
  if (!version) return <p>No product version has been uploaded.</p>;
  return (
    <section className="submission-version-preview" aria-labelledby="submission-preview-title">
      <div>
        <h4 id="submission-preview-title">
          Version {version.versionNumber}: {version.title}
        </h4>
        <p>{version.summary}</p>
        <dl className="qc-metadata">
          <div>
            <dt>Manifest</dt>
            <dd>{version.manifestHash ? version.manifestHash.slice(0, 16) : "Legacy draft"}</dd>
          </div>
          <div>
            <dt>ACGs</dt>
            <dd>{version.acgIds.length}</dd>
          </div>
          <div>
            <dt>File status</dt>
            <dd>{asset?.processingStatus ?? "No file"}</dd>
          </div>
        </dl>
      </div>
      {asset?.previewAvailable ? (
        <ControlledDocumentViewer
          kind={asset.previewKind}
          title={`${version.title} preview`}
          url={workflowProductPreviewUrl(task.ticketId, version.id, asset.id)}
        />
      ) : (
        <pre className="qc-preview">{version.content}</pre>
      )}
    </section>
  );
}
