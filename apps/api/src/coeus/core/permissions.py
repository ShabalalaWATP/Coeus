from enum import StrEnum


class Permission(StrEnum):
    AUTH_LOGIN = "auth:login"
    AUTH_LOGOUT = "auth:logout"
    USER_READ_SELF = "user:read_self"
    PRODUCT_READ = "product:read"
    AUDIT_READ = "audit:read"
    SYSTEM_CONFIGURE = "system:configure"
