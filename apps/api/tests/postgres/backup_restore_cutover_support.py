"""Non-empty exact-candidate cutover evidence for recovery tests."""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE

CUTOVER_SLICES = ("organisation", "calendar", "task_capacity")


def seed_cutover_recovery_rows(connection: Connection, actor_id: UUID) -> None:
    candidate = "1" * 64
    connection.execute(
        text(_MANIFEST),
        {
            "candidate": candidate,
            "actor": actor_id,
            "routing_release": ROUTING_RELATIONAL_CAPACITY_RELEASE,
        },
    )
    connection.execute(text(_RELEASE), {"candidate": candidate})
    for slice_name in CUTOVER_SLICES:
        checkpoint = uuid4()
        approval_ids = (uuid4(), uuid4())
        approvers = (uuid4(), uuid4())
        for approval_id, role, approver in zip(
            approval_ids,
            ("security_review", "release_authority"),
            approvers,
            strict=True,
        ):
            connection.execute(
                text(_APPROVAL),
                {
                    "approval": approval_id,
                    "candidate": candidate,
                    "slice": slice_name,
                    "role": role,
                    "actor": approver,
                },
            )
        connection.execute(
            text(_SLICE_STATE),
            {
                "candidate": candidate,
                "slice": slice_name,
                "actor": actor_id,
                "executor": uuid4(),
                "security": approval_ids[0],
                "release": approval_ids[1],
            },
        )
        common = {"candidate": candidate, "slice": slice_name, "actor": actor_id}
        connection.execute(
            text(_EVIDENCE),
            {**common, "evidence": uuid4(), "payload": '{"synthetic":true}'},
        )
        connection.execute(text(_CHECKPOINT), {**common, "checkpoint": checkpoint})
        connection.execute(
            text(_CHECKPOINT_EVENT),
            {**common, "event": uuid4(), "checkpoint": checkpoint},
        )
        connection.execute(text(_FENCE), common)
        connection.execute(
            text(_RECOVERY),
            {**common, "recovery": uuid4(), "checkpoint": checkpoint},
        )


_MANIFEST = """
INSERT INTO organisation_cutover_manifests(
 candidate_hash,source_revision,schema_head,organisation_parity_hash,
 calendar_parity_hash,task_capacity_parity_hash,routing_evaluation_release,
 routing_evaluation_hash,protected_checks_reference,protected_checks_hash,
 browser_evidence_hash,security_review_reference,security_review_hash,
 backup_restore_hash,proposed_by_user_id,proposed_at)
VALUES (:candidate,'synthetic-revision','20260804_0045',repeat('2',64),
 repeat('3',64),repeat('4',64),:routing_release,repeat('5',64),
 'synthetic-protected-checks',repeat('6',64),repeat('7',64),
 'synthetic-security-review',repeat('8',64),repeat('9',64),:actor,now())
"""

_RELEASE = """
INSERT INTO organisation_cutover_release(singleton,candidate_hash,version,updated_at)
VALUES (true,:candidate,1,now())
"""

_APPROVAL = """
INSERT INTO organisation_cutover_approvals(
 approval_id,candidate_hash,slice,approval_role,preview_hash,approved_by_user_id,approved_at)
VALUES (:approval,:candidate,:slice,:role,repeat('a',64),:actor,now())
"""

_SLICE_STATE = """
INSERT INTO organisation_cutover_slice_state(
 candidate_hash,slice,status,preview_hash,proposed_by_user_id,previewed_at,
 preview_expires_at,source_snapshot_hash,target_snapshot_hash,visibility_hash,
 security_approval_id,release_approval_id,approved_at,activated_by_user_id,
 activated_at,version)
VALUES (:candidate,:slice,'active',repeat('a',64),:actor,now(),
 now()+interval '1 day',repeat('b',64),repeat('c',64),repeat('d',64),
 :security,:release,now(),:executor,now(),1)
"""

_EVIDENCE = """
INSERT INTO organisation_cutover_evidence(
 evidence_id,candidate_hash,slice,evidence_kind,evidence_hash,source_snapshot_hash,
 target_snapshot_hash,actor_user_id,payload,recorded_at)
VALUES (:evidence,:candidate,:slice,'preview',repeat('e',64),
 repeat('b',64),repeat('c',64),:actor,CAST(:payload AS jsonb),now())
"""

_CHECKPOINT = """
INSERT INTO organisation_cutover_checkpoints(
 checkpoint_id,candidate_hash,slice,status,source_count,target_count,
 source_snapshot_hash,target_snapshot_hash,version,started_at,completed_at)
VALUES (:checkpoint,:candidate,:slice,'completed',1,1,
 repeat('b',64),repeat('c',64),1,now(),now())
"""

_CHECKPOINT_EVENT = """
INSERT INTO organisation_cutover_checkpoint_events(
 event_id,checkpoint_id,checkpoint_version,event_type,actor_user_id,evidence_hash,occurred_at)
VALUES (:event,:checkpoint,1,'completed',:actor,repeat('f',64),now())
"""

_FENCE = """
INSERT INTO organisation_cutover_writer_fences(
 slice,candidate_hash,state,fence_epoch,quiesced_by_user_id,quiesced_at,updated_at)
VALUES (:slice,:candidate,'target_authoritative',1,:actor,now(),now())
"""

_RECOVERY = """
INSERT INTO organisation_cutover_recovery_events(
 recovery_id,candidate_hash,slice,checkpoint_id,action,reason_code,actor_user_id,
 prior_state_hash,result_state_hash,occurred_at)
VALUES (:recovery,:candidate,:slice,:checkpoint,'resume','synthetic_recovery',
 :actor,repeat('1',64),repeat('2',64),now())
"""
