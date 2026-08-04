"""Safe domain mappings for organisation grant administration."""

from collections.abc import Callable
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.organisation import OrganisationManagementGrant
from coeus.domain.organisation_authority import (
    CreateManagementGrantCommand,
    OrganisationAuthorityConflict,
    OrganisationAuthorityDenied,
    OrganisationIdempotencyConflict,
    RevokeManagementGrantCommand,
)
from coeus.schemas.organisation_grant_admin import (
    CreateManagementGrantPayload,
    ManagementGrantResponse,
    RevokeManagementGrantPayload,
)


def create_grant_command(
    payload: CreateManagementGrantPayload, actor_user_id: UUID
) -> CreateManagementGrantCommand:
    return CreateManagementGrantCommand(
        payload.command_id,
        payload.grant_id,
        payload.idempotency_key,
        actor_user_id,
        payload.manager_user_id,
        payload.root_unit_id,
        payload.action,
        payload.include_descendants,
        payload.source_grant_id,
        payload.expected_source_version,
        payload.reason,
        payload.valid_until,
    )


def revoke_grant_command(
    grant_id: UUID, payload: RevokeManagementGrantPayload, actor_user_id: UUID
) -> RevokeManagementGrantCommand:
    return RevokeManagementGrantCommand(
        payload.command_id,
        payload.idempotency_key,
        actor_user_id,
        grant_id,
        payload.expected_version,
        payload.reason,
    )


def grant_response(grant: OrganisationManagementGrant) -> ManagementGrantResponse:
    values = vars(grant)
    return ManagementGrantResponse(
        **{
            key: values[key]
            for key in (
                "grant_id",
                "manager_user_id",
                "root_unit_id",
                "action",
                "include_descendants",
                "valid_from",
                "valid_until",
                "revoked_at",
                "source_grant_id",
                "delegation_depth",
                "version",
            )
        }
    )


def call_grant[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except OrganisationAuthorityDenied as exc:
        raise AppError(
            403,
            "organisation_grant_denied",
            "You do not have authority to manage this grant.",
        ) from exc
    except OrganisationIdempotencyConflict as exc:
        raise AppError(409, "organisation_command_conflict", str(exc)) from exc
    except OrganisationAuthorityConflict as exc:
        raise AppError(409, "organisation_grant_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "organisation_grant_invalid", str(exc)) from exc
