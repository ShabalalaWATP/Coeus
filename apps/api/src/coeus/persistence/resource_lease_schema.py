"""Shared relational schema for durable resource-admission leases."""

RESOURCE_LEASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS coeus_resource_leases (
    lease_id uuid PRIMARY KEY,
    resource_type text NOT NULL,
    principal_id uuid NOT NULL,
    units bigint NOT NULL CHECK (units > 0),
    acquired_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    committed boolean NOT NULL DEFAULT false,
    released_at timestamptz
)
"""
