"""Dependency-ordered Sprint 24 tables for coordinated logical recovery."""

from coeus.persistence.postgres_backup_core_tables import CORE_TABLES
from coeus.persistence.postgres_backup_extension_tables import EXTENSION_TABLES
from coeus.persistence.postgres_backup_table_spec import table as _table

# Parents precede children because PostgreSQL validates non-deferrable foreign keys
# during COPY. Self-referencing grants are ordered from roots to delegates.
TABLES = (
    *CORE_TABLES,
    _table(
        "organisation_units",
        "unit_id name short_name category parent_unit_id is_active valid_from valid_until "
        "time_zone "
        "description provenance version created_at updated_at",
        "created_at unit_id",
    ),
    _table(
        "organisation_topology_revisions",
        "revision_id unit_id parent_unit_id path valid_from valid_until change_command_id "
        "changed_by_user_id created_at",
        "created_at revision_id",
    ),
    _table(
        "organisation_unit_closure",
        "ancestor_unit_id descendant_unit_id depth",
        "ancestor_unit_id descendant_unit_id",
    ),
    _table(
        "team_delivery_profiles",
        "profile_id unit_id route wip_limit weekly_hours policy_version is_active provenance "
        "created_at updated_at",
        "profile_id",
    ),
    _table(
        "team_capability_coverage",
        "coverage_id profile_id capability_id proficiency valid_from valid_until policy_version "
        "approved_by_user_id created_at",
        "coverage_id",
    ),
    _table(
        "team_memberships",
        "membership_id user_id unit_id role state assignment_eligible valid_from valid_until "
        "created_by_user_id reason provenance version created_at updated_at",
        "membership_id",
    ),
    _table(
        "team_management_grants",
        "grant_id manager_user_id root_unit_id action include_descendants valid_from valid_until "
        "revoked_at created_by_user_id reason source_grant_id delegation_depth version created_at "
        "updated_at revoked_by_user_id revocation_reason",
        "delegation_depth created_at grant_id",
    ),
    _table(
        "effective_authority_epochs",
        "principal_id scope_unit_id epoch advanced_at",
        "principal_id scope_unit_id",
    ),
    _table(
        "organisation_reconciliation_checkpoints",
        "checkpoint_id source_namespace source_digest status cursor started_at completed_at "
        "updated_at",
        "checkpoint_id",
    ),
    _table(
        "organisation_reconciliation_findings",
        "finding_id checkpoint_id finding_code severity source_identifier details created_at "
        "resolved_at disposition",
        "finding_id",
    ),
    _table(
        "organisation_bootstrap_state",
        "singleton ceremony_id completed_by_user_id completed_at root_unit_id",
        "singleton",
    ),
    _table(
        "team_task_ownership",
        "ownership_id ticket_id workflow_leg owning_unit_id manager_user_id state accepted_at "
        "target_date topology_revision_id capability_policy_version version history_reference "
        "provenance reason created_at updated_at",
        "ownership_id",
    ),
    _table(
        "team_task_ownership_history",
        "ownership_id version ticket_id workflow_leg owning_unit_id manager_user_id state "
        "accepted_at target_date topology_revision_id capability_policy_version history_reference "
        "provenance reason created_at updated_at recorded_at",
        "ownership_id version",
    ),
    _table(
        "team_delivery_profile_history",
        "profile_id policy_version unit_id route wip_limit weekly_hours is_active provenance "
        "created_at updated_at recorded_at",
        "profile_id policy_version",
    ),
    _table(
        "team_capability_coverage_history",
        "coverage_id policy_version profile_id capability_id proficiency valid_from valid_until "
        "approved_by_user_id created_at recorded_at",
        "coverage_id policy_version",
    ),
    _table(
        "organisation_grant_commands",
        "command_id idempotency_key request_hash command_type actor_user_id grant_id "
        "authorising_grant_id result_version created_at",
        "command_id",
    ),
    _table(
        "organisation_unit_commands",
        "command_id idempotency_key request_hash operation actor_user_id unit_id "
        "authorising_grant_id expected_version result_version topology_revision_id occurred_at",
        "command_id",
    ),
    _table(
        "organisation_reparent_commands",
        "command_id idempotency_key request_hash reason_hash actor_user_id unit_id "
        "source_parent_unit_id new_parent_unit_id authorising_grant_id expected_unit_version "
        "expected_parent_version result_version topology_revision_id occurred_at",
        "command_id",
    ),
    _table(
        "organisation_membership_commands",
        "command_id idempotency_key request_hash reason_hash operation actor_user_id membership_id "
        "user_id unit_id authorising_grant_id expected_version result_version role "
        "assignment_eligible valid_from valid_until occurred_at",
        "command_id",
    ),
    _table(
        "organisation_personnel_transfers",
        "command_id idempotency_key request_hash reason_hash reason actor_user_id "
        "source_membership_id target_membership_id user_id source_unit_id target_unit_id "
        "expected_membership_version expected_target_unit_version target_role assignment_eligible "
        "effective_at source_authorising_grant_id target_authorising_grant_id status "
        "source_result_version target_result_version failure_code scheduled_at applied_at",
        "command_id",
    ),
    _table(
        "organisation_deactivation_commands",
        "command_id idempotency_key request_hash reason_hash actor_user_id unit_id "
        "authorising_grant_id expected_version result_version occurred_at",
        "command_id",
    ),
    _table(
        "organisation_merge_commands",
        "command_id idempotency_key request_hash reason_hash actor_user_id source_unit_ids "
        "source_expected_versions source_result_versions successor_unit_id "
        "successor_expected_version "
        "successor_result_version authority_map occurred_at",
        "command_id",
    ),
    _table(
        "organisation_merge_dispositions",
        "command_id record_kind record_id expected_version action target_unit_id replacement_id",
        "command_id record_kind record_id",
    ),
    _table(
        "organisation_split_commands",
        "command_id idempotency_key request_hash reason_hash actor_user_id source_unit_id "
        "parent_unit_id source_expected_version parent_expected_version source_result_version "
        "parent_result_version successor_specs source_authorising_grant_id "
        "parent_authorising_grant_id occurred_at",
        "command_id",
    ),
    _table(
        "organisation_split_dispositions",
        "command_id record_kind record_id expected_version action target_unit_id replacement_id",
        "command_id record_kind record_id",
    ),
    _table(
        "calendar_events",
        "event_id owner_user_id source activity_category starts_at ends_at all_day_start "
        "all_day_end "
        "time_zone availability_effect privacy_level note recurrence_rule status "
        "manager_scope_unit_id created_by_user_id created_at updated_at cancelled_at version "
        "provenance deduplication_key",
        "event_id",
    ),
    _table(
        "calendar_commitment_responses",
        "event_id subject_user_id response_state response_version responded_at "
        "response_reason_hash updated_at",
        "event_id",
    ),
    _table(
        "calendar_commitment_notifications",
        "notification_id event_id recipient_user_id notification_type created_at read_at",
        "notification_id",
    ),
    _table(
        "calendar_event_scopes",
        "scope_id event_id scope_type subject_user_id unit_id created_at",
        "scope_id",
    ),
    _table(
        "calendar_event_exceptions",
        "exception_id event_id occurrence_key action replacement version created_by_user_id "
        "created_at",
        "exception_id",
    ),
    _table(
        "calendar_event_versions",
        "history_id event_id event_version snapshot changed_by_user_id changed_at "
        "change_reason_hash",
        "history_id",
    ),
    _table(
        "calendar_event_commands",
        "command_id actor_user_id idempotency_key command_type request_hash event_id "
        "result_version created_at future_event_id",
        "command_id",
    ),
    _table(
        "calendar_import_commands",
        "command_id actor_user_id idempotency_key request_hash preview_hash source_digest "
        "imported_count existing_count occurred_at",
        "command_id",
    ),
    _table(
        "calendar_legacy_import_records",
        "legacy_entry_id event_id team_id owner_user_id creator_user_id source_digest command_id "
        "imported_at",
        "legacy_entry_id",
    ),
    _table(
        "working_patterns",
        "pattern_id user_id time_zone monday_minutes tuesday_minutes wednesday_minutes "
        "thursday_minutes friday_minutes saturday_minutes sunday_minutes valid_from valid_until "
        "version provenance created_at updated_at",
        "pattern_id",
    ),
    _table(
        "capacity_exceptions",
        "exception_id user_id starts_at ends_at reduction_minutes reduction_percent reason_code "
        "note approved_by_user_id version created_at updated_at",
        "exception_id",
    ),
    _table(
        "canonical_work_packages",
        "package_id ticket_id workflow_leg owning_unit_id accountable_user_id title state "
        "estimated_minutes remaining_minutes due_at priority priority_override_reason blocked_code "
        "blocked_note review_at sort_order version provenance created_at updated_at",
        "package_id",
    ),
    _table(
        "work_package_participants",
        "package_id user_id role active created_at ended_at",
        "package_id user_id role",
    ),
    _table(
        "work_package_dependencies",
        "package_id predecessor_package_id created_by_user_id created_at",
        "package_id predecessor_package_id",
    ),
    _table(
        "capacity_reservations",
        "reservation_id user_id ticket_id workflow_leg package_id starts_at ends_at "
        "reserved_minutes state expires_at idempotency_key request_hash actor_user_id version "
        "created_at updated_at participant_role",
        "reservation_id",
    ),
    _table(
        "work_package_history",
        "history_id package_id version actor_user_id event_type evidence occurred_at",
        "history_id",
    ),
    _table(
        "work_package_commands",
        "command_id idempotency_key request_hash package_id actor_user_id expected_version "
        "result_version operation occurred_at",
        "command_id",
    ),
    _table(
        "work_package_contributor_commands",
        "command_id idempotency_key request_hash package_id contributor_user_id actor_user_id "
        "operation expected_package_version result_package_version result_active occurred_at",
        "command_id",
    ),
    _table(
        "work_package_dependency_commands",
        "command_id idempotency_key request_hash package_id predecessor_package_id actor_user_id "
        "operation expected_package_version expected_predecessor_version "
        "expected_ownership_version "
        "expected_grant_version result_package_version result_active occurred_at",
        "command_id",
    ),
    _table(
        "work_package_handover_commands",
        "command_id idempotency_key request_hash preview_hash package_id source_user_id "
        "target_user_id actor_user_id expected_package_version result_package_version "
        "released_reservation_count replacement_reservation_count occurred_at",
        "command_id",
    ),
    _table(
        "assignment_competencies",
        "competency_id user_id capability_id proficiency verified_by_user_id verified_at "
        "expires_at "
        "evidence_reference version provenance created_at updated_at",
        "competency_id",
    ),
    _table(
        "identity_account_projection",
        "user_id is_active roles credential_version source_hash projected_at",
        "user_id",
    ),
    _table(
        "assignment_demand_estimates",
        "estimate_id ticket_id workflow_leg version effort_min_minutes effort_max_minutes "
        "window_start deadline capability_ids created_by_user_id source_hash created_at",
        "ticket_id workflow_leg version estimate_id",
    ),
    _table(
        "assignment_recommendations",
        "recommendation_id estimate_id actor_user_id ticket_version preview_hash "
        "exclusion_counts state expires_at created_at updated_at",
        "estimate_id recommendation_id",
    ),
    _table(
        "assignment_recommendation_candidates",
        "recommendation_id unit_id analyst_user_id rank assignable_minutes active_wip "
        "explanation_codes evidence_hash",
        "recommendation_id rank analyst_user_id",
    ),
    _table(
        "assignment_demand_holds",
        "hold_id recommendation_id ticket_id unit_id held_minutes starts_at ends_at state "
        "expires_at created_at updated_at",
        "recommendation_id hold_id",
    ),
    _table(
        "assignment_recommendation_decisions",
        "decision_id recommendation_id actor_user_id selected_unit_id selected_analyst_user_id "
        "recommended_analyst_user_id decision_type reason reason_hash occurred_at",
        "recommendation_id decision_id",
    ),
    _table(
        "synthetic_organisation_fixture_commands",
        "command_id idempotency_key request_hash actor_user_id manifest_version result occurred_at",
        "command_id",
    ),
    *EXTENSION_TABLES,
)
