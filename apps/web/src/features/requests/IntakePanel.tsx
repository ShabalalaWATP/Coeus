import { Paperclip, Play, Save } from "lucide-react";
import { Fragment, useEffect, useState } from "react";

import type { AttachmentMetadataInput, IntakeUpdate, Ticket } from "../../lib/api-client/tickets";

const editableFields = [
  ["title", "Title", 3],
  ["description", "Description", 3],
  ["operationalQuestion", "Operational question", 3],
  ["areaOrRegion", "Area or region", 2],
  ["timePeriodStart", "Time period start", 1],
  ["timePeriodEnd", "Time period end", 1],
  ["priority", "Priority", 2],
  ["supportedOperation", "Supported operation", 2],
  ["urgencyJustification", "Why it is urgent", 3],
  ["deadline", "Latest useful time", 1],
  ["requestingUnit", "Requesting unit", 2],
  ["intelligenceDisciplines", "Disciplines", 2],
  ["requiredOutputFormat", "Output format", 2],
  ["customerSuccessCriteria", "Success criteria", 3],
] as const;

type EditableFieldKey = (typeof editableFields)[number][0];

type IntakePanelProps = {
  isSaving: boolean;
  isSubmitting: boolean;
  isAddingAttachment: boolean;
  onAddAttachment: (payload: AttachmentMetadataInput, onSuccess?: () => void) => void;
  onSave: (payload: IntakeUpdate) => void;
  onSubmit: () => void;
  ticket?: Ticket;
};

export function IntakePanel({
  isSaving,
  isSubmitting,
  isAddingAttachment,
  onAddAttachment,
  onSave,
  onSubmit,
  ticket,
}: IntakePanelProps) {
  const [formState, setFormState] = useState<IntakeUpdate>({});
  const [attachment, setAttachment] = useState<AttachmentMetadataInput>({
    name: "",
    description: "",
    sourceType: "metadata-only",
  });

  useEffect(() => {
    if (ticket === undefined) {
      setFormState({});
      return;
    }
    setFormState({
      title: ticket.intake.title ?? "",
      description: ticket.intake.description ?? "",
      operationalQuestion: ticket.intake.operationalQuestion ?? "",
      areaOrRegion: ticket.intake.areaOrRegion ?? "",
      timePeriodStart: ticket.intake.timePeriodStart ?? "",
      timePeriodEnd: ticket.intake.timePeriodEnd ?? "",
      priority: ticket.intake.priority ?? "",
      supportedOperation: ticket.intake.supportedOperation ?? "",
      urgencyJustification: ticket.intake.urgencyJustification ?? "",
      deadline: ticket.intake.deadline ?? "",
      requestingUnit: ticket.intake.requestingUnit ?? "",
      intelligenceDisciplines: ticket.intake.intelligenceDisciplines ?? "",
      requiredOutputFormat: ticket.intake.requiredOutputFormat ?? "",
      customerSuccessCriteria: ticket.intake.customerSuccessCriteria ?? "",
    });
  }, [ticket]);

  function saveIntake(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: IntakeUpdate = {};
    for (const [key] of editableFields) {
      const value = (formState[key] ?? "").trim();
      const original = ticket?.intake[key] ?? null;
      if (value !== (original ?? "").trim()) {
        payload[key] = value === "" ? null : value;
      }
    }
    onSave(payload);
  }

  function fieldHint(key: EditableFieldKey, minLength: number) {
    const value = (formState[key] ?? "").trim();
    if (value.length === 0 || value.length >= minLength) {
      return null;
    }
    return (
      <small className="field-hint">
        Needs at least {minLength} characters. Clearing a saved value removes it.
      </small>
    );
  }

  function addAttachment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (attachment.name.trim() && attachment.description.trim()) {
      onAddAttachment(attachment, () =>
        setAttachment({ name: "", description: "", sourceType: "metadata-only" }),
      );
    }
  }

  return (
    <section className="surface intake-panel" aria-labelledby="intake-title">
      <div className="section-heading access-heading">
        <Save aria-hidden="true" size={20} />
        <h2 id="intake-title">Extracted Intake</h2>
      </div>
      {ticket === undefined ? <p>No ticket selected</p> : null}
      {ticket !== undefined ? (
        <>
          <form className="intake-form" onSubmit={saveIntake}>
            {editableFields.map(([key, label, minLength]) => (
              <Fragment key={key}>
                <label>
                  {label}
                  {key === "description" || key === "customerSuccessCriteria" ? (
                    <textarea
                      onChange={(event) =>
                        setFormState((current) => ({ ...current, [key]: event.target.value }))
                      }
                      rows={3}
                      value={formState[key] ?? ""}
                    />
                  ) : (
                    <input
                      onChange={(event) =>
                        setFormState((current) => ({ ...current, [key]: event.target.value }))
                      }
                      value={formState[key] ?? ""}
                    />
                  )}
                </label>
                {fieldHint(key, minLength)}
              </Fragment>
            ))}
            <div className="intake-actions">
              <button disabled={isSaving} type="submit">
                <Save aria-hidden="true" size={18} />
                Save
              </button>
              <button
                disabled={!ticket.isReadyForSubmission || isSubmitting}
                onClick={onSubmit}
                type="button"
              >
                <Play aria-hidden="true" size={18} />
                Submit
              </button>
            </div>
          </form>
          <div className="missing-fields">
            <strong>Missing</strong>
            <span>{ticket.intake.missingInformation.join(", ") || "None"}</span>
          </div>
          <form className="attachment-form" onSubmit={addAttachment}>
            <div className="section-heading access-heading">
              <Paperclip aria-hidden="true" size={18} />
              <h3>Attachment Metadata</h3>
            </div>
            <label>
              Name
              <input
                disabled={isAddingAttachment}
                onChange={(event) =>
                  setAttachment((current) => ({ ...current, name: event.target.value }))
                }
                value={attachment.name}
              />
            </label>
            <label>
              Description
              <input
                disabled={isAddingAttachment}
                onChange={(event) =>
                  setAttachment((current) => ({ ...current, description: event.target.value }))
                }
                value={attachment.description}
              />
            </label>
            <button disabled={isAddingAttachment} type="submit">
              <Paperclip aria-hidden="true" size={18} />
              Add metadata
            </button>
          </form>
        </>
      ) : null}
    </section>
  );
}
