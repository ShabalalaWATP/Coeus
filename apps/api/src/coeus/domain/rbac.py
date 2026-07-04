from coeus.core.permissions import ALL_PERMISSIONS, Permission
from coeus.domain.auth import RoleDefinition, RoleName

SELF_SERVICE = frozenset(
    {
        Permission.AUTH_LOGIN,
        Permission.AUTH_LOGOUT,
        Permission.USER_READ_SELF,
        Permission.USER_UPDATE_SELF,
    }
)

CUSTOMER_PERMISSIONS = SELF_SERVICE | frozenset(
    {
        Permission.TICKET_CREATE,
        Permission.TICKET_READ_OWN,
        Permission.TICKET_ADD_INFORMATION,
        Permission.TICKET_ADD_COMMENT,
        Permission.CHAT_USE,
        Permission.RFI_SEARCH,
        Permission.RFI_ACCEPT_PRODUCT,
        Permission.RFI_REJECT_PRODUCT,
        Permission.PRODUCT_READ,
        Permission.PRODUCT_SEARCH,
        Permission.PRODUCT_DOWNLOAD,
        Permission.FEEDBACK_CREATE,
        Permission.ANALYTICS_VIEW_OWN,
    }
)

PRODUCT_TEAM_PERMISSIONS = SELF_SERVICE | frozenset(
    {
        Permission.PROJECT_READ,
        Permission.TICKET_READ_ASSIGNED,
        Permission.TICKET_ADD_COMMENT,
        Permission.PRODUCT_READ,
        Permission.PRODUCT_SEARCH,
        Permission.PRODUCT_CREATE_EXISTING,
        Permission.PRODUCT_UPDATE_METADATA,
        Permission.PRODUCT_MANAGE_ASSETS,
    }
)

ROLE_DEFINITIONS: dict[RoleName, RoleDefinition] = {
    RoleName.ADMINISTRATOR: RoleDefinition(
        name=RoleName.ADMINISTRATOR,
        default_route="/admin/overview",
        permissions=ALL_PERMISSIONS,
    ),
    RoleName.USER: RoleDefinition(
        name=RoleName.USER,
        default_route="/app/requests",
        permissions=CUSTOMER_PERMISSIONS,
    ),
    RoleName.RFA_MANAGER: RoleDefinition(
        name=RoleName.RFA_MANAGER,
        default_route="/rfa/queue",
        permissions=PRODUCT_TEAM_PERMISSIONS
        | frozenset(
            {
                Permission.RFA_REVIEW,
                Permission.RFA_ASSIGN,
                Permission.RFA_ADD_PRODUCT,
                Permission.ANALYTICS_VIEW_TEAM,
            }
        ),
    ),
    RoleName.RFA_TEAM_MEMBER: RoleDefinition(
        name=RoleName.RFA_TEAM_MEMBER,
        default_route="/rfa/products",
        permissions=PRODUCT_TEAM_PERMISSIONS | frozenset({Permission.RFA_ADD_PRODUCT}),
    ),
    RoleName.COLLECTION_MANAGER: RoleDefinition(
        name=RoleName.COLLECTION_MANAGER,
        default_route="/collection/queue",
        permissions=PRODUCT_TEAM_PERMISSIONS
        | frozenset(
            {
                Permission.COLLECTION_REVIEW,
                Permission.COLLECTION_ASSIGN,
                Permission.COLLECTION_ADD_PRODUCT,
                Permission.ANALYTICS_VIEW_TEAM,
            }
        ),
    ),
    RoleName.COLLECTION_TEAM_MEMBER: RoleDefinition(
        name=RoleName.COLLECTION_TEAM_MEMBER,
        default_route="/collection/products",
        permissions=PRODUCT_TEAM_PERMISSIONS | frozenset({Permission.COLLECTION_ADD_PRODUCT}),
    ),
    RoleName.INTELLIGENCE_ANALYST: RoleDefinition(
        name=RoleName.INTELLIGENCE_ANALYST,
        default_route="/analyst/workbench",
        permissions=PRODUCT_TEAM_PERMISSIONS
        | frozenset({Permission.ANALYST_WORK, Permission.ANALYST_SUBMIT_PRODUCT}),
    ),
    RoleName.QUALITY_CONTROL_MANAGER: RoleDefinition(
        name=RoleName.QUALITY_CONTROL_MANAGER,
        default_route="/qc/queue",
        permissions=PRODUCT_TEAM_PERMISSIONS
        | frozenset(
            {
                Permission.QC_REVIEW,
                Permission.QC_APPROVE,
                Permission.QC_REJECT,
                Permission.PRODUCT_CREATE_FROM_QC,
                Permission.PRODUCT_PUBLISH,
                Permission.PRODUCT_DISSEMINATE,
                Permission.FEEDBACK_READ,
            }
        ),
    ),
}


def permissions_for_roles(roles: frozenset[RoleName]) -> frozenset[Permission]:
    permissions: set[Permission] = set()
    for role in roles:
        permissions.update(ROLE_DEFINITIONS[role].permissions)
    return frozenset(permissions)


def default_route_for_roles(roles: frozenset[RoleName]) -> str:
    for role in ROLE_DEFINITIONS:
        if role in roles:
            return ROLE_DEFINITIONS[role].default_route
    return "/app/requests"
