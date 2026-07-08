# Threat Model: Hybrid Search And Duplicate Detection

## Scope

Hybrid RFI search, product embeddings, similar-request detection and the
no-match consent journey.

## Assets

- Store product metadata, derived embeddings and semantic labels.
- Ticket intake text, related-ticket links and similarity metadata.
- ACG membership, clearance and product or ticket visibility decisions.
- Gemini API keys and any text sent to external embedding providers.
- Search reasons, scores and counts shown to customers or managers.

## Threats And Controls

| Threat                                                               | Control                                                                                                                                        |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Vector search reveals products outside a requester's ACG.            | Both lexical and vector SQL legs apply status, clearance and ACG predicates before ranking. The ranking layer never sees hidden products.      |
| Product counts reveal hidden products.                               | Candidate totals come from the scoped Store query only. Offers and reasons are built after scope filtering.                                    |
| A configured Gemini key silently exfiltrates Store text.             | `COEUS_EMBEDDING_PROVIDER` is authoritative. `gemini_api` is the only provider that can call Gemini, and keys are never logged or returned.    |
| Local model or package is missing and breaks RFI search.             | Non-mock provider failures log once and degrade to lexical-only retrieval.                                                                     |
| Similar-request notices reveal another customer's ticket.            | Customer-facing disclosure reuses `get_visible_ticket`. Hidden matches can only produce a neutral notice with no references, titles or counts. |
| Manager duplicate panels create unaudited consolidation decisions.   | Link actions write reciprocal related-ticket IDs, timeline entries on both tickets and a `tickets_linked` audit event.                         |
| Similarity scores reveal sensitive ticket text through explanations. | Customer explanations are returned only for tickets the requester can already read. Managers require workflow read permissions.                |
| No-match automation tasks work without consent.                      | Zero-offer searches enter `RFI_NO_MATCH`; only the requester can confirm route assessment or cancel.                                          |
| No-match decline text becomes an injection or audit sink.             | The decline path records a fixed reason, `customer declined tasking after no-match`, instead of accepting free text.                           |

## Accepted Risks

- Mock embeddings are deterministic approximations, not production semantic
  quality. They are deliberately used for local repeatability and tests.
- Embeddings are derived from synthetic marked text in this repository. Real
  deployments must classify embeddings as sensitive derived data.
- Gemini embedding calls are operator-controlled but still send query/product
  text to an external provider when enabled.
