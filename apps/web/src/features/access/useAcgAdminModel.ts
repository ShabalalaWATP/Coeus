import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import {
  addAcgMember,
  createAcg,
  listAcgs,
  removeAcgMember,
  updateAcg,
  type AccessControlGroup,
  type CreateAccessControlGroupRequest,
} from "../../lib/api-client/access";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";
import { hasPermissions } from "../../lib/permissions/route-access";

const emptyCreateForm: CreateAccessControlGroupRequest = { code: "", name: "", description: "" };

export function useAcgAdminModel() {
  const { acgId } = useParams();
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [editName, setEditName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [memberUserId, setMemberUserId] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const acgsQuery = useQuery({ queryKey: ["acgs"], queryFn: listAcgs });
  const acgs = useMemo(() => acgsQuery.data ?? [], [acgsQuery.data]);
  const routedAcgExists = acgId !== undefined && acgs.some((acg) => acg.id === acgId);
  const requestedId = selectedId ?? (routedAcgExists ? acgId : undefined) ?? acgs[0]?.id;
  const selectedAcg = useMemo(
    () => acgs.find((acg) => acg.id === requestedId),
    [acgs, requestedId],
  );

  useEffect(() => {
    setEditName(selectedAcg?.name ?? "");
    setIsActive(selectedAcg?.isActive ?? true);
  }, [selectedAcg]);

  const csrfToken = session?.csrfToken ?? "";
  const invalidateAcgs = () => queryClient.invalidateQueries({ queryKey: ["acgs"] });
  const createMutation = useMutation({
    mutationFn: () => createAcg(createForm, csrfToken),
    onSuccess: async (created) => {
      setCreateForm(emptyCreateForm);
      setSelectedId(created.id);
      await invalidateAcgs();
    },
    onError: failActionWith("The access group could not be created. Try again."),
    onMutate: clearActionError,
  });
  const updateMutation = useMutation({
    mutationFn: (acg: AccessControlGroup) =>
      updateAcg(acg.id, { name: editName || acg.name, isActive }, csrfToken),
    onSuccess: async (updated) => {
      setSelectedId(updated.id);
      await invalidateAcgs();
    },
    onError: failActionWith("The access group could not be updated. Try again."),
    onMutate: clearActionError,
  });
  const addMemberMutation = useMutation({
    mutationFn: (acg: AccessControlGroup) => addAcgMember(acg.id, memberUserId, csrfToken),
    onSuccess: async () => {
      setMemberUserId("");
      await invalidateAcgs();
    },
    onError: failActionWith("The member could not be added. Try again."),
    onMutate: clearActionError,
  });
  const removeMemberMutation = useMutation({
    mutationFn: ({ acg, userId }: { acg: AccessControlGroup; userId: string }) =>
      removeAcgMember(acg.id, userId, csrfToken),
    onSuccess: invalidateAcgs,
    onError: failActionWith("The member could not be removed. Try again."),
    onMutate: clearActionError,
  });
  const submit = (action: () => void) => (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    action();
  };

  return {
    acgs,
    acgsQuery,
    actionError,
    createForm,
    editName,
    isActive,
    memberUserId,
    selectedAcg,
    routedAcgMissing:
      acgId !== undefined && acgs.length > 0 && !routedAcgExists && selectedId === null,
    canCreate: session !== null && hasPermissions(session.user, ["acg:create"]),
    canManageMembers: session !== null && hasPermissions(session.user, ["acg:assign_user"]),
    canUpdate: session !== null && hasPermissions(session.user, ["acg:update"]),
    createPending: createMutation.isPending,
    updatePending: updateMutation.isPending,
    addMemberPending: addMemberMutation.isPending,
    removeMemberPending: removeMemberMutation.isPending,
    selectAcg: setSelectedId,
    setCreateForm,
    setEditName,
    setIsActive,
    setMemberUserId,
    submitCreate: submit(() => createMutation.mutate()),
    submitUpdate: submit(() => selectedAcg && updateMutation.mutate(selectedAcg)),
    submitMember: submit(() => selectedAcg && addMemberMutation.mutate(selectedAcg)),
    removeMember: (userId: string) =>
      selectedAcg && removeMemberMutation.mutate({ acg: selectedAcg, userId }),
  };
}
