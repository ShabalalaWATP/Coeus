import { useMutation, useQuery } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { listAcgs } from "../../lib/api-client/access";
import {
  uploadAnalystProductSubmission,
  type AnalystTask,
  type ProductSubmissionMetadataInput,
} from "../../lib/api-client/analyst";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

type FormState = {
  title: string;
  summary: string;
  description: string;
  productType: string;
  sourceType: string;
  ownerTeam: string;
  areaOrRegion: string;
  classificationLevel: string;
  tags: string;
  timePeriodStart: string;
  timePeriodEnd: string;
  acgIds: string[];
};

export function AnalystProductSubmissionForm({
  disabled,
  onUploaded,
  task,
}: {
  disabled: boolean;
  onUploaded: (task: AnalystTask) => void;
  task: AnalystTask;
}) {
  const { session } = useAuth();
  const [form, setForm] = useState<FormState>(() => initialForm(task));
  const [file, setFile] = useState<File | null>(null);
  const acgs = useQuery({ queryKey: ["acgs"], queryFn: listAcgs, retry: false });
  const { actionError, clearActionError, failActionWith } = useActionError();
  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a product file.");
      return uploadAnalystProductSubmission(
        task.ticketId,
        metadata(form),
        file,
        session?.csrfToken ?? "",
      );
    },
    onError: failActionWith("The product could not be uploaded. Check the file and metadata."),
    onMutate: clearActionError,
    onSuccess: (nextTask) => {
      setFile(null);
      onUploaded(nextTask);
    },
  });
  const visibleIds = useMemo(() => new Set((acgs.data ?? []).map((acg) => acg.id)), [acgs.data]);
  const validAcgs = form.acgIds.length > 0 && form.acgIds.every((id) => visibleIds.has(id));
  const canUpload =
    file !== null &&
    form.title.trim().length >= 3 &&
    form.summary.trim().length >= 3 &&
    form.description.trim().length >= 3 &&
    form.areaOrRegion.trim().length >= 2 &&
    validAcgs;

  return (
    <form
      className="analyst-draft-form"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <p>
        Upload the finished Word, PowerPoint, PDF or image product. Istari retains the original
        bytes and creates an immutable version for manager and QC review.
      </p>
      <div className="upload-grid">
        <label>
          Product file
          <input
            accept=".docx,.pptx,.pdf,.png,.jpg,.jpeg,.webp"
            disabled={disabled || mutation.isPending}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
        <Field label="Title" name="title" setForm={setForm} value={form.title} />
        <Field label="Summary" name="summary" setForm={setForm} value={form.summary} textarea />
        <Field
          label="Description"
          name="description"
          setForm={setForm}
          value={form.description}
          textarea
        />
        <label>
          Product type
          <select
            onChange={(event) => setForm({ ...form, productType: event.target.value })}
            value={form.productType}
          >
            <option value="assessment_report">Assessment report</option>
            <option value="briefing_note">Briefing note</option>
            <option value="presentation">Presentation</option>
            <option value="imagery_product">Imagery product</option>
          </select>
        </label>
        <Field label="Source type" name="sourceType" setForm={setForm} value={form.sourceType} />
        <Field label="Owner team" name="ownerTeam" setForm={setForm} value={form.ownerTeam} />
        <Field
          label="Area or region"
          name="areaOrRegion"
          setForm={setForm}
          value={form.areaOrRegion}
        />
        <label>
          Classification
          <input
            max="5"
            min="0"
            onChange={(event) => setForm({ ...form, classificationLevel: event.target.value })}
            type="number"
            value={form.classificationLevel}
          />
        </label>
        <Field label="Tags" name="tags" setForm={setForm} value={form.tags} />
        <Field
          label="Period start"
          name="timePeriodStart"
          setForm={setForm}
          type="date"
          value={form.timePeriodStart}
        />
        <Field
          label="Period end"
          name="timePeriodEnd"
          setForm={setForm}
          type="date"
          value={form.timePeriodEnd}
        />
      </div>
      <fieldset>
        <legend>Access control groups</legend>
        {acgs.isError ? <p role="alert">Access groups could not be loaded.</p> : null}
        {(acgs.data ?? []).map((acg) => (
          <label className="analyst-check" key={acg.id}>
            <input
              checked={form.acgIds.includes(acg.id)}
              onChange={() => setForm({ ...form, acgIds: toggle(form.acgIds, acg.id) })}
              type="checkbox"
            />
            <span>{acg.code}</span>
          </label>
        ))}
      </fieldset>
      <small>
        Release markers are fixed to MOCK and MOCK DATA ONLY in this public-safe environment.
      </small>
      <button disabled={disabled || mutation.isPending || !canUpload} type="submit">
        <FileUp aria-hidden="true" size={18} />
        {mutation.isPending ? "Checking and uploading…" : "Upload product version"}
      </button>
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </form>
  );
}

function initialForm(task: AnalystTask): FormState {
  const route = task.assignments.at(-1)?.route;
  return {
    title: task.title,
    summary: "MOCK DATA ONLY. ",
    description: "MOCK DATA ONLY. ",
    productType: "assessment_report",
    sourceType: "analyst_submission",
    ownerTeam: route === "cm" ? "Collection" : "RFA",
    areaOrRegion: task.areaOrRegion ?? "Not specified",
    classificationLevel: "0",
    tags: "mock",
    timePeriodStart: "",
    timePeriodEnd: "",
    acgIds: [],
  };
}

function metadata(form: FormState): ProductSubmissionMetadataInput {
  return {
    ...form,
    classificationLevel: Number(form.classificationLevel),
    releasability: ["MOCK"],
    handlingCaveats: ["MOCK DATA ONLY"],
    tags: form.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
    timePeriodStart: form.timePeriodStart || null,
    timePeriodEnd: form.timePeriodEnd || null,
  };
}

function toggle(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function Field({
  label,
  name,
  setForm,
  textarea = false,
  type = "text",
  value,
}: {
  label: string;
  name: keyof FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  textarea?: boolean;
  type?: string;
  value: string;
}) {
  const input = textarea ? (
    <textarea onChange={(event) => setFormField(setForm, name, event.target.value)} value={value} />
  ) : (
    <input
      onChange={(event) => setFormField(setForm, name, event.target.value)}
      type={type}
      value={value}
    />
  );
  return (
    <label>
      {label}
      {input}
    </label>
  );
}

function setFormField(
  setForm: Dispatch<SetStateAction<FormState>>,
  name: keyof FormState,
  value: string,
) {
  setForm((current) => ({ ...current, [name]: value }));
}
