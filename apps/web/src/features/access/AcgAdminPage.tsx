import { AcgCreateForm, AcgEditor, AcgSelector } from "./AcgAdminSections";
import { useAcgAdminModel } from "./useAcgAdminModel";
import { AdminReturnLink } from "../../components/ui/AdminReturnLink";

export default function AcgAdminPage() {
  const model = useAcgAdminModel();
  return (
    <div className="access-page">
      <section className="overview-hero" aria-labelledby="acg-title">
        <div>
          <AdminReturnLink />
          <h1 id="acg-title">Access Control Groups</h1>
          <p>MOCK DATA ONLY access groups for product visibility and team access.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      {model.routedAcgMissing ? (
        <p className="workspace-alert" role="alert">
          The requested access group was not found. Showing the first available group instead.
        </p>
      ) : null}
      {model.actionError ? (
        <p className="auth-error" role="alert">
          {model.actionError}
        </p>
      ) : null}
      {model.actionSuccess ? <p role="status">{model.actionSuccess}</p> : null}
      <section className="access-grid">
        <AcgSelector
          acgs={model.acgs}
          isError={model.acgsQuery.isError}
          isLoading={model.acgsQuery.isLoading}
          onRetry={() => void model.acgsQuery.refetch()}
          onSelect={model.selectAcg}
          selectedId={model.selectedAcg?.id}
        />
        <AcgEditor
          acg={model.selectedAcg}
          canManageMembers={model.canManageMembers}
          canUpdate={model.canUpdate}
          directoryError={model.directoryError}
          directoryLoading={model.directoryLoading}
          directorySearch={model.directorySearch}
          directoryTotal={model.directoryTotal}
          editName={model.editName}
          isActive={model.isActive}
          memberUserId={model.memberUserId}
          onAddMember={model.submitMember}
          onDirectorySearch={model.setDirectorySearch}
          onEditName={model.setEditName}
          onIsActive={model.setIsActive}
          onMemberUserId={model.setMemberUserId}
          onRemoveMember={model.removeMember}
          onUpdate={model.submitUpdate}
          addPending={model.addMemberPending}
          removePending={model.removeMemberPending}
          updatePending={model.updatePending}
          users={model.users}
        />
      </section>
      {model.canCreate ? (
        <AcgCreateForm
          form={model.createForm}
          onChange={model.setCreateForm}
          onSubmit={model.submitCreate}
          pending={model.createPending}
        />
      ) : null}
    </div>
  );
}
