"""Later Sprint 24 workflow and workspace tables for logical recovery."""

from coeus.persistence.postgres_backup_table_spec import table as _table

EXTENSION_TABLES = (
    _table(
        "workflow_leg_transfers",
        "transfer_id ticket_id workflow_leg source_unit_id target_unit_id target_user_id "
        "source_manager_user_id target_manager_user_id state expected_ownership_version "
        "result_ownership_version expected_ticket_version result_ticket_version "
        "expected_ticket_source_hash source_grant_id source_grant_version proposal_hash "
        "preview_hash expires_at reason version created_at updated_at decided_at",
        "transfer_id",
    ),
    _table(
        "workflow_leg_transfer_packages",
        "transfer_id package_id disposition expected_version reservation_id "
        "reservation_idempotency_key starts_at ends_at reserved_minutes",
        "transfer_id package_id",
    ),
    _table(
        "workflow_leg_transfer_team_holds",
        "hold_id transfer_id package_id target_unit_id starts_at ends_at reserved_minutes "
        "state created_at released_at",
        "hold_id",
    ),
    _table(
        "workflow_leg_transfer_commands",
        "command_id actor_user_id idempotency_key transfer_id action request_hash result_state "
        "result_version occurred_at",
        "command_id",
    ),
    _table(
        "workspace_saved_views",
        "view_id owner_user_id unit_id name filters version created_at updated_at",
        "view_id",
    ),
    _table(
        "team_work_templates",
        "template_id unit_id owner_user_id name package_titles estimated_minutes priority "
        "version created_at updated_at",
        "template_id",
    ),
    _table(
        "workspace_work_updates",
        "update_id recipient_user_id event_key kind unit_id object_type object_id occurred_at "
        "acknowledged_at",
        "update_id",
    ),
    _table(
        "workspace_delivery_preferences",
        "user_id mode due_reminders version updated_at",
        "user_id",
    ),
    _table(
        "workspace_productivity_commands",
        "command_id actor_user_id idempotency_key request_hash operation result occurred_at",
        "command_id",
    ),
    _table(
        "package_lifecycle_conflicts",
        "conflict_id package_id reason_code source_type source_id status evidence observed_at "
        "resolved_at",
        "conflict_id",
    ),
    _table(
        "predecessor_cancellation_commands",
        "command_id actor_user_id idempotency_key request_hash package_id "
        "expected_package_version result_package_version dispositions occurred_at",
        "command_id",
    ),
    _table(
        "workspace_store_links",
        "link_id owner_user_id unit_id source_type source_id target_type target_id label version "
        "created_at updated_at",
        "link_id",
    ),
    _table(
        "team_workspace_policies",
        "unit_id service_target_hours planning_cadence planning_weekday planning_local_time "
        "planning_duration_minutes version updated_by_user_id updated_at",
        "unit_id",
    ),
    _table(
        # snapshot_payload and handling_marking are NOT NULL without defaults, so
        # omitting them would make a restore of this table impossible.
        "workspace_export_jobs",
        "export_id actor_user_id unit_id include_descendants authorising_grant_id "
        "authorising_grant_version command_id idempotency_key request_hash state row_count "
        "snapshot_payload handling_marking created_at expires_at",
        "export_id",
    ),
    _table(
        "organisation_cutover_manifests",
        "candidate_hash source_revision schema_head organisation_parity_hash "
        "calendar_parity_hash task_capacity_parity_hash routing_evaluation_release "
        "routing_evaluation_hash protected_checks_reference protected_checks_hash "
        "browser_evidence_hash security_review_reference security_review_hash "
        "backup_restore_hash proposed_by_user_id proposed_at",
        "candidate_hash",
    ),
    _table(
        "organisation_cutover_release",
        "singleton candidate_hash version updated_at",
        "singleton",
    ),
    _table(
        "organisation_cutover_approvals",
        "approval_id candidate_hash slice approval_role preview_hash approved_by_user_id "
        "approved_at",
        "approval_id",
    ),
    _table(
        "organisation_cutover_slice_state",
        "candidate_hash slice status preview_hash proposed_by_user_id previewed_at "
        "preview_expires_at source_snapshot_hash target_snapshot_hash visibility_hash "
        "security_approval_id security_approval_role release_approval_id "
        "release_approval_role approved_at activated_by_user_id activated_at version",
        "candidate_hash slice",
    ),
    _table(
        "organisation_cutover_evidence",
        "evidence_id candidate_hash slice evidence_kind evidence_hash source_snapshot_hash "
        "target_snapshot_hash actor_user_id payload recorded_at",
        "evidence_id",
    ),
    _table(
        "organisation_cutover_checkpoints",
        "checkpoint_id candidate_hash slice status cursor_token source_count target_count "
        "source_snapshot_hash target_snapshot_hash lease_token lease_expires_at version "
        "started_at completed_at failure_code",
        "checkpoint_id",
    ),
    _table(
        "organisation_cutover_checkpoint_events",
        "event_id checkpoint_id checkpoint_version event_type actor_user_id evidence_hash "
        "occurred_at",
        "event_id",
    ),
    _table(
        "organisation_cutover_writer_fences",
        "slice candidate_hash state fence_epoch owner_token quiesced_by_user_id quiesced_at "
        "updated_at",
        "slice",
    ),
    _table(
        "organisation_cutover_recovery_events",
        "recovery_id candidate_hash slice checkpoint_id action reason_code actor_user_id "
        "prior_state_hash result_state_hash occurred_at",
        "recovery_id",
    ),
)
