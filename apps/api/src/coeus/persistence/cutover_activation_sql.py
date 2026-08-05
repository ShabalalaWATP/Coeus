"""SQL statements for exact-candidate cutover activation commands."""

INSERT_MANIFEST = """INSERT INTO organisation_cutover_manifests
(candidate_hash,source_revision,schema_head,organisation_parity_hash,calendar_parity_hash,
 task_capacity_parity_hash,routing_evaluation_release,routing_evaluation_hash,
 protected_checks_reference,protected_checks_hash,browser_evidence_hash,
 security_review_reference,security_review_hash,backup_restore_hash,
 proposed_by_user_id,proposed_at)
VALUES (:candidate,:source_revision,:schema_head,:organisation_parity_hash,
 :calendar_parity_hash,:task_capacity_parity_hash,:routing_evaluation_release,
 :routing_evaluation_hash,:protected_checks_reference,:protected_checks_hash,
 :browser_evidence_hash,:security_review_reference,:security_review_hash,
 :backup_restore_hash,:actor,:at)
ON CONFLICT (candidate_hash) DO NOTHING"""

INSERT_RELEASE = """INSERT INTO organisation_cutover_release
(singleton,candidate_hash,version,updated_at)
VALUES (true,:candidate,1,:at) ON CONFLICT (singleton) DO NOTHING"""

UPSERT_PREVIEW = """INSERT INTO organisation_cutover_slice_state
(candidate_hash,slice,status,preview_hash,proposed_by_user_id,previewed_at,
 preview_expires_at,source_snapshot_hash,target_snapshot_hash,visibility_hash,version)
VALUES (:candidate,:slice,'previewed',:preview,:actor,:at,:expires,
 :source,:target,:visibility,1)
ON CONFLICT (candidate_hash,slice) DO UPDATE SET status='previewed',preview_hash=:preview,
 proposed_by_user_id=:actor,previewed_at=:at,preview_expires_at=:expires,
 source_snapshot_hash=:source,target_snapshot_hash=:target,visibility_hash=:visibility,
 security_approval_id=NULL,release_approval_id=NULL,approved_at=NULL,
 version=organisation_cutover_slice_state.version+1"""

LOCK_PREVIEW = """SELECT * FROM organisation_cutover_slice_state
WHERE candidate_hash=:candidate AND slice=:slice FOR UPDATE"""

INSERT_APPROVAL = """INSERT INTO organisation_cutover_approvals
(approval_id,candidate_hash,slice,approval_role,preview_hash,approved_by_user_id,approved_at)
VALUES (:id,:candidate,:slice,:role,:preview,:actor,:at)"""

MARK_APPROVED = """UPDATE organisation_cutover_slice_state
SET status='approved',approved_at=:at,
 security_approval_id=(SELECT approval_id FROM organisation_cutover_approvals
   WHERE candidate_hash=:candidate AND slice=:slice
     AND approval_role='security_review'),
 release_approval_id=(SELECT approval_id FROM organisation_cutover_approvals
   WHERE candidate_hash=:candidate AND slice=:slice
     AND approval_role='release_authority'),version=version+1
WHERE candidate_hash=:candidate AND slice=:slice"""

LOCK_EXECUTION = LOCK_PREVIEW
SELECT_APPROVALS = """SELECT approval_id,approval_role,approved_by_user_id,preview_hash
FROM organisation_cutover_approvals
WHERE candidate_hash=:candidate AND slice=:slice
  AND approval_id IN (:first,:second) FOR SHARE"""

UPSERT_FENCE = """INSERT INTO organisation_cutover_writer_fences
(slice,candidate_hash,state,fence_epoch,owner_token,quiesced_by_user_id,
 quiesced_at,updated_at)
VALUES (:slice,:candidate,'quiescing',1,:owner,:actor,NULL,:at)
ON CONFLICT (slice) DO UPDATE SET candidate_hash=:candidate,state='quiescing',
 fence_epoch=organisation_cutover_writer_fences.fence_epoch+1,owner_token=:owner,
 quiesced_by_user_id=:actor,quiesced_at=NULL,updated_at=:at"""

INSERT_CHECKPOINT = """INSERT INTO organisation_cutover_checkpoints
(checkpoint_id,candidate_hash,slice,status,source_count,target_count,
 source_snapshot_hash,target_snapshot_hash,lease_token,lease_expires_at,version,started_at)
VALUES (:id,:candidate,:slice,'running',:source_count,:target_count,:source,:target,
 :lease,:at + interval '5 minutes',1,:at)"""

COMPLETE_CHECKPOINT = """UPDATE organisation_cutover_checkpoints
SET status='completed',lease_token=NULL,lease_expires_at=NULL,completed_at=:at,
 version=version+1 WHERE checkpoint_id=:id"""
ACTIVATE_SLICE = """UPDATE organisation_cutover_slice_state
SET status='active',activated_by_user_id=:actor,activated_at=:at,version=version+1
WHERE candidate_hash=:candidate AND slice=:slice"""
AUTHORITATIVE_FENCE = """UPDATE organisation_cutover_writer_fences
SET state='target_authoritative',owner_token=NULL,updated_at=:at WHERE slice=:slice"""

FENCE_SOURCE = """UPDATE organisation_cutover_writer_fences
SET state='fenced',quiesced_at=:at,updated_at=:at
WHERE slice=:slice AND owner_token=:lease"""
LOCK_CHECKPOINT = """SELECT * FROM organisation_cutover_checkpoints
WHERE candidate_hash=:candidate AND slice=:slice FOR UPDATE"""
RENEW_CHECKPOINT = """UPDATE organisation_cutover_checkpoints
SET lease_token=:lease,lease_expires_at=:at + interval '5 minutes',version=version+1
WHERE checkpoint_id=:id"""
INSERT_CHECKPOINT_EVENT = """INSERT INTO organisation_cutover_checkpoint_events
(event_id,checkpoint_id,checkpoint_version,event_type,actor_user_id,evidence_hash,occurred_at)
VALUES (:event,:id,:version,:type,:actor,:hash,:at)"""
INSERT_RECOVERY = """INSERT INTO organisation_cutover_recovery_events
(recovery_id,candidate_hash,slice,checkpoint_id,action,reason_code,actor_user_id,
 prior_state_hash,result_state_hash,occurred_at)
VALUES (:recovery,:candidate,:slice,:id,'resume','lease_expired',:actor,
 :prior,:result,:at)"""
PREDECESSORS = """SELECT count(*) FROM organisation_cutover_slice_state
WHERE candidate_hash=:candidate AND slice=ANY(CAST(:predecessors AS text[]))
  AND status='active'"""

ELIGIBLE = """SELECT manifest.source_revision,manifest.routing_evaluation_release,
manifest.organisation_parity_hash,manifest.calendar_parity_hash,
manifest.task_capacity_parity_hash,
(SELECT count(*) FROM organisation_cutover_slice_state state
 WHERE state.candidate_hash=release.candidate_hash AND state.status='active') active_slices,
(SELECT count(*) FROM organisation_cutover_writer_fences fence
 WHERE fence.candidate_hash=release.candidate_hash
   AND fence.state='target_authoritative') authoritative_fences
FROM organisation_cutover_release release
JOIN organisation_cutover_manifests manifest USING (candidate_hash)
WHERE release.candidate_hash=:candidate"""
