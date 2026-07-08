type AnalystDraft = {
  title: string;
  summary: string;
  productType: string;
  content: string;
  assetName: string;
};

type AnalystDraftFormProps = {
  draft: AnalystDraft;
  onChange: (draft: AnalystDraft) => void;
  onSubmit: () => void;
};

export function AnalystDraftForm({ draft, onChange, onSubmit }: AnalystDraftFormProps) {
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
          onChange={(event) => onChange({ ...draft, title: event.target.value })}
          value={draft.title}
        />
      </label>
      <label>
        Summary
        <input
          onChange={(event) => onChange({ ...draft, summary: event.target.value })}
          value={draft.summary}
        />
      </label>
      <label>
        Content
        <textarea
          onChange={(event) => onChange({ ...draft, content: event.target.value })}
          value={draft.content}
        />
      </label>
      <label>
        Asset name
        <input
          onChange={(event) => onChange({ ...draft, assetName: event.target.value })}
          value={draft.assetName}
        />
      </label>
      <button disabled={!canSave} type="submit">
        Save draft
      </button>
    </form>
  );
}
