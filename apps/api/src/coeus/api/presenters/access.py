from coeus.domain.access import AccessControlGroup, AcgAccessApplication
from coeus.domain.auth import UserAccount
from coeus.schemas.access import (
    AccessControlGroupResponse,
    AcgApplicationResponse,
    DirectoryUserResponse,
)
from coeus.services.access import AccessServices


def to_acg_response(
    access_services: AccessServices, acg: AccessControlGroup
) -> AccessControlGroupResponse:
    member_ids = access_services.acgs.list_member_ids(acg.acg_id)
    members = (access_services.repository.get_user(user_id) for user_id in member_ids)
    return AccessControlGroupResponse(
        acg_id=acg.acg_id,
        code=acg.code,
        name=acg.name,
        description=acg.description,
        owner_user_id=acg.owner_user_id,
        is_active=acg.is_active,
        member_user_ids=list(member_ids),
        members=[to_directory_user(user) for user in members if user is not None],
    )


def to_directory_user(user: UserAccount) -> DirectoryUserResponse:
    return DirectoryUserResponse(
        user_id=user.user_id,
        display_name=user.display_name,
        username=user.username,
    )


def to_application_response(
    access_services: AccessServices, application: AcgAccessApplication
) -> AcgApplicationResponse:
    acg = access_services.repository.get_acg(application.acg_id)
    applicant = access_services.repository.get_user(application.applicant_user_id)
    if acg is None or applicant is None:
        raise RuntimeError("Persisted ACG application references missing data.")
    return AcgApplicationResponse(
        application_id=application.application_id,
        acg_id=application.acg_id,
        acg_code=acg.code,
        acg_name=acg.name,
        applicant_user_id=application.applicant_user_id,
        applicant_display_name=applicant.display_name,
        justification=application.justification,
        status=application.status,
        submitted_at=application.submitted_at,
    )
