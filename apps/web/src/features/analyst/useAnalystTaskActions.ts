import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  addAnalystNote,
  linkAnalystProduct,
  saveDraftProduct,
  submitTaskToQc,
  updateWorkPackage,
  type AnalystTask,
} from "../../lib/api-client/analyst";
import { searchStoreProducts, type StoreSearchResponse } from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

export type AnalystDraftState = {
  title: string;
  summary: string;
  productType: string;
  content: string;
  assetName: string;
};

const EMPTY_SEARCH: StoreSearchResponse = {
  products: [],
  total: 0,
  page: 1,
  pageSize: 0,
  totalPages: 0,
  facets: { productTypes: [], regions: [], tags: [] },
};

const EMPTY_DRAFT: AnalystDraftState = {
  title: "",
  summary: "",
  productType: "finished_output",
  content: "",
  assetName: "assessment-draft.pdf",
};

export function useAnalystTaskActions(
  task: AnalystTask | undefined,
  onTaskChange: (task: AnalystTask) => void,
) {
  const { session } = useAuth();
  const csrfToken = session?.csrfToken ?? "";
  const ticketId = task?.ticketId ?? "";
  const [noteBody, setNoteBody] = useState("");
  const [productQuery, setProductQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [draft, setDraft] = useState<AnalystDraftState>(EMPTY_DRAFT);
  const { actionError, clearActionError, failActionWith } = useActionError();
  const productsQuery = useQuery({
    queryKey: ["analyst-product-search", submittedQuery],
    queryFn: () => searchStoreProducts({ query: submittedQuery }),
    enabled: ticketId.length > 0 && submittedQuery.trim().length > 0,
    placeholderData: EMPTY_SEARCH,
    retry: false,
  });
  const noteMutation = useMutation({
    mutationFn: (body: string) => addAnalystNote(ticketId, body, csrfToken),
    onError: failActionWith("The note could not be added. Try again."),
    onMutate: clearActionError,
    onSuccess: (nextTask) => {
      setNoteBody("");
      onTaskChange(nextTask);
    },
  });
  const linkMutation = useMutation({
    mutationFn: (productId: string) => linkAnalystProduct(ticketId, productId, csrfToken),
    onError: failActionWith("The product could not be linked. Try again."),
    onMutate: clearActionError,
    onSuccess: onTaskChange,
  });
  const packageMutation = useMutation({
    mutationFn: (packageId: string) =>
      updateWorkPackage(ticketId, packageId, "complete", csrfToken),
    onError: failActionWith("The work package could not be updated. Try again."),
    onMutate: clearActionError,
    onSuccess: onTaskChange,
  });
  const draftMutation = useMutation({
    mutationFn: () => saveDraftProduct(ticketId, draftPayload(draft), csrfToken),
    onError: failActionWith("The draft could not be saved. Try again."),
    onMutate: clearActionError,
    onSuccess: (nextTask) => {
      setDraft((current) => ({ ...current, title: "", summary: "", content: "" }));
      onTaskChange(nextTask);
    },
  });
  const submitMutation = useMutation({
    mutationFn: () => submitTaskToQc(ticketId, csrfToken),
    onError: failActionWith("The task could not be submitted to QC. Try again."),
    onMutate: clearActionError,
    onSuccess: onTaskChange,
  });

  return {
    actionError,
    completePackage: (packageId: string) => packageMutation.mutate(packageId),
    draft,
    linkProduct: (productId: string) => linkMutation.mutate(productId),
    noteBody,
    productsQuery,
    productQuery,
    retryProductSearch: () => void productsQuery.refetch(),
    saveDraft: () => draftMutation.mutate(),
    searchProducts: () => setSubmittedQuery(productQuery.trim()),
    setDraft,
    setNoteBody,
    setProductQuery,
    submit: () => submitMutation.mutate(),
    submitPending: submitMutation.isPending,
    submitNote: () => noteMutation.mutate(noteBody),
  };
}

function draftPayload(draft: AnalystDraftState) {
  return {
    title: draft.title,
    summary: draft.summary,
    productType: draft.productType,
    content: draft.content,
    assets: draft.assetName.trim()
      ? [
          {
            name: draft.assetName,
            assetType: "pdf",
            mimeType: "application/pdf",
            sizeBytes: 512,
            sha256: "e".repeat(64),
          },
        ]
      : [],
  };
}
