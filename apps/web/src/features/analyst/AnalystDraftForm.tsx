type AnalystDraft = {
  title: string;
  summary: string;
  productType: string;
  content: string;
  assetName: string;
};

type AnalystDraftFormProps = {
  disabled?: boolean;
  draft: AnalystDraft;
  onChange: (draft: AnalystDraft) => void;
  onSubmit: () => void;
};

export function AnalystDraftForm({
  disabled = false,
  draft,
  onChange,
  onSubmit,
}: AnalystDraftFormProps) {
  const canSave = draft.title.trim() && draft.summary.trim() && draft.content.trim().length >= 10;
  return (
    <form
      className="analyst-draft-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label>
        Title
        <input
          disabled={disabled}
          onChange={(event) => onChange({ ...draft, title: event.target.value })}
          value={draft.title}
        />
      </label>
      <label>
        Summary
        <input
          disabled={disabled}
          onChange={(event) => onChange({ ...draft, summary: event.target.value })}
          value={draft.summary}
        />
      </label>
      <label>
        Content
        <textarea
          disabled={disabled}
          onChange={(event) => onChange({ ...draft, content: event.target.value })}
          value={draft.content}
        />
      </label>
      <label>
        Mock supporting asset name
        <input
          disabled={disabled}
          onChange={(event) => onChange({ ...draft, assetName: event.target.value })}
          value={draft.assetName}
        />
      </label>
      <small>This records synthetic asset metadata only. It does not upload a file.</small>
      {!canSave ? (
        <small>Enter a title, summary and at least 10 characters of content.</small>
      ) : null}
      <button disabled={disabled || !canSave} type="submit">
        Save draft
      </button>
    </form>
  );
}
