"""Deterministic values shared by synthetic fixture inspection and writes."""

from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.organisation import ManagementAction

MANIFEST_VERSION = "synthetic-organisation-v2"
PROVENANCE = "synthetic-fixture:v2"
TIME_ZONE = "Europe/London"
UNIT_DESCRIPTION = "Synthetic exercise unit. No real-world organisational relationship is asserted."
MEMBERSHIP_REASON = "Synthetic exercise workforce fixture."


def delivery_profile_id(unit_id: UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-delivery-profile:v2:{unit_id}")


def bootstrap_ceremony_id() -> UUID:
    return uuid5(NAMESPACE_URL, "coeus:synthetic-organisation-bootstrap:v2")


def fixture_grant_id(action: ManagementAction) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-organisation-grant:v2:{action.value}")


def topology_revision_id(unit_id: UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-topology-revision:v2:{unit_id}")


def topology_command_id(unit_id: UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-topology-command:v2:{unit_id}")
