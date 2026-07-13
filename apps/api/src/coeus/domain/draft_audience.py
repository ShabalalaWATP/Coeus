"""Explicit reasons a principal may receive a draft product audience."""

from enum import StrEnum


class DraftAudienceReason(StrEnum):
    CREATOR = "creator"
    ASSIGNED_ANALYST = "assigned_analyst"
    RESPONSIBLE_MANAGER = "responsible_manager"
    QUALITY_CONTROL = "quality_control"
    ADMINISTRATOR = "administrator"
    STORE_MANAGER = "store_manager"
