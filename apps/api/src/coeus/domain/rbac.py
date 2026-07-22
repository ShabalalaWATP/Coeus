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
        Permission.TICKET_ADD_COMMENT,
        Permission.ACG_VIEW,
        Permission.PRODUCT_READ,
        Permission.PRODUCT_SEARCH,
        Permission.PRODUCT_UPDATE_METADATA,
        Permission.PRODUCT_MANAGE_ASSETS,
    }
)

# Team managers lead their team: they approve analyst work and manage the
# team roster and calendar.
MANAGER_TEAM_LEAD_PERMISSIONS = frozenset(
    {
        Permission.TICKET_CONSOLIDATE,
        Permission.PRODUCT_APPROVE,
        Permission.TEAM_MANAGE,
        Permission.ANALYTICS_VIEW_TEAM,
    }
)

STORE_MANAGER_PERMISSIONS = SELF_SERVICE | frozenset(
    {
        # Curators may browse the whole catalogue; everyone else searches.
        Permission.STORE_BROWSE_ALL,
        Permission.ACG_VIEW,
        Permission.ACG_ASSIGN_USER,
        Permission.ACG_ASSIGN_PRODUCT,
        Permission.PRODUCT_CREATE_EXISTING,
        Permission.PRODUCT_READ,
        Permission.PRODUCT_SEARCH,
        Permission.PRODUCT_UPDATE_METADATA,
        Permission.PRODUCT_MANAGE_ASSETS,
        Permission.PRODUCT_DOWNLOAD,
        Permission.PRODUCT_PUBLISH,
        Permission.PRODUCT_ARCHIVE,
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
    RoleName.JIOC_TEAM_MEMBER: RoleDefinition(
        name=RoleName.JIOC_TEAM_MEMBER,
        default_route="/jioc/queue",
        permissions=SELF_SERVICE
        | frozenset(
            {
                Permission.JIOC_REVIEW,
                Permission.JIOC_RESOLVE_CUSTOMER_DISPUTE,
                Permission.TICKET_CONSOLIDATE,
                Permission.TICKET_ADD_COMMENT,
                Permission.ANALYTICS_VIEW_TEAM,
            }
        ),
    ),
    RoleName.JIOC_MANAGER: RoleDefinition(
        name=RoleName.JIOC_MANAGER,
        default_route="/jioc/oversight",
        permissions=SELF_SERVICE
        | frozenset(
            {
                Permission.JIOC_REVIEW,
                Permission.JIOC_OVERSIGHT,
                Permission.JIOC_INTERVENE,
                Permission.JIOC_RESOLVE_CUSTOMER_DISPUTE,
                Permission.TICKET_CONSOLIDATE,
                Permission.TICKET_ADD_COMMENT,
                Permission.ANALYTICS_VIEW_GLOBAL,
                Permission.AUDIT_READ,
            }
        ),
    ),
    RoleName.RFA_MANAGER: RoleDefinition(
        name=RoleName.RFA_MANAGER,
        default_route="/rfa/queue",
        permissions=PRODUCT_TEAM_PERMISSIONS
        | MANAGER_TEAM_LEAD_PERMISSIONS
        | frozenset(
            {
                Permission.RFA_REVIEW,
                Permission.RFA_ASSIGN,
                Permission.RFA_ADD_PRODUCT,
                # Store uploads of existing team products; the release powers
                # (publish, disseminate) belong to Quality Control.
                Permission.PRODUCT_CREATE_EXISTING,
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
        | MANAGER_TEAM_LEAD_PERMISSIONS
        | frozenset(
            {
                Permission.COLLECTION_REVIEW,
                Permission.COLLECTION_ASSIGN,
                Permission.COLLECTION_ADD_PRODUCT,
                # Store uploads of existing team products; the release powers
                # (publish, disseminate) belong to Quality Control.
                Permission.PRODUCT_CREATE_EXISTING,
            }
        ),
    ),
    RoleName.COLLECTION_TEAM_MEMBER: RoleDefinition(
        name=RoleName.COLLECTION_TEAM_MEMBER,
        default_route="/collection/products",
        permissions=PRODUCT_TEAM_PERMISSIONS | frozenset({Permission.COLLECTION_ADD_PRODUCT}),
    ),
    RoleName.INTELLIGENCE_STORE_MANAGER: RoleDefinition(
        name=RoleName.INTELLIGENCE_STORE_MANAGER,
        default_route="/store",
        permissions=STORE_MANAGER_PERMISSIONS,
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
                Permission.PRODUCT_CREATE_EXISTING,
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
