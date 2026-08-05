"""Canonical hashes and atomic cutover audit/outbox evidence."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.cutover_activation import CutoverManifest, CutoverSlice
from coeus.persistence.cutover_activation_snapshots import CutoverSnapshot


def digest(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode()).hexdigest()


def preview_digest(
    manifest: CutoverManifest,
    slice: CutoverSlice,
    snapshot: CutoverSnapshot,
    actor: UUID,
    occurred_at: datetime,
) -> str:
    return digest(
        {
            "candidate_hash": manifest.candidate_hash,
            "slice": slice.value,
            "source_snapshot_hash": snapshot.source_hash,
            "target_snapshot_hash": snapshot.target_hash,
            "visibility_hash": snapshot.visibility_hash,
            "actor_user_id": str(actor),
            "previewed_at": occurred_at.isoformat(),
        }
    )


def record_evidence(
    connection: Connection,
    *,
    candidate_hash: str,
    slice: CutoverSlice,
    kind: str,
    evidence_hash: str,
    actor: UUID,
    occurred_at: datetime,
    payload: dict[str, object],
    snapshot: CutoverSnapshot | None = None,
) -> None:
    connection.execute(
        text(
            "INSERT INTO organisation_cutover_evidence"
            "(evidence_id,candidate_hash,slice,evidence_kind,evidence_hash,"
            "source_snapshot_hash,target_snapshot_hash,actor_user_id,payload,recorded_at) "
            "VALUES (:id,:candidate,:slice,:kind,:digest,:source,:target,:actor,"
            "CAST(:payload AS jsonb),:at) ON CONFLICT DO NOTHING"
        ),
        {
            "id": uuid4(),
            "candidate": candidate_hash,
            "slice": slice.value,
            "kind": kind,
            "digest": evidence_hash,
            "source": snapshot.source_hash if snapshot else None,
            "target": snapshot.target_hash if snapshot else None,
            "actor": actor,
            "payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            "at": occurred_at,
        },
    )


def record_audit_outbox(
    connection: Connection,
    *,
    event_type: str,
    candidate_hash: str,
    slice: CutoverSlice,
    actor: UUID,
    occurred_at: datetime,
    details: dict[str, object],
) -> None:
    event_id = uuid4()
    payload = {
        "candidate_hash": candidate_hash,
        "slice": slice.value,
        **details,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:id,:type,:at,:actor,CAST(:payload AS jsonb))"
        ),
        {"id": event_id, "type": event_type, "at": occurred_at, "actor": actor, "payload": encoded},
    )
    connection.execute(
        text(
            "INSERT INTO coeus_outbox"
            "(event_id,aggregate_id,aggregate_version,event_type,payload) "
            "VALUES (:id,:aggregate,1,:type,CAST(:payload AS jsonb))"
        ),
        {"id": uuid4(), "aggregate": event_id, "type": event_type, "payload": encoded},
    )
