# RFI results focus and personal Intelligence Store library

## Goal

Move the customer from conversation to evidence once an RFI search returns
products, while preserving the conversation as request context. Let every
signed-in user keep visible products in a personal, organised library.

## Experience contract

- When one or more RFI products finish loading, the conversation collapses to
  a compact summary and the product results become the main workspace.
- The user can reopen the complete conversation without losing messages or
  request state.
- Opening a product from an RFI result records only a safe, in-app navigation
  origin. Product detail then offers a return to that request. Direct Store
  visits and products opened from Store search do not show an RFI return link.
- Product detail lets the user save or remove the product and optionally place
  it in one of their personal folders.
- The Intelligence Store shows the user's saved products and supports creating,
  selecting and deleting personal folders. Deleting a folder keeps its saved
  products in the unfiled library.

## Security and data rules

- Folder and saved-product records are scoped by the authenticated user ID.
- Folder IDs supplied by a client are resolved only inside that user's records.
- Saving and listing reapply current product visibility rules. A saved record
  never preserves access after an ACG, clearance or status change.
- Mutations require the normal authenticated session and CSRF control and are
  audit logged.
- Folder names are trimmed, bounded and unique per user without regard to case.
- Each user is limited to 50 folders and 500 saved products.
- Navigation state is presentation context, not authority. Only a recognised
  `/app/requests/{id}` path can produce the request return action.

## Acceptance criteria

- Product-ready RFI workspaces render one compact conversation control above a
  full-width result panel, with accessible expand and collapse behaviour.
- Result links carry the current request origin and product detail displays a
  `Back to request` action only for that origin.
- A user can create a folder, save a visible product into it, move it, remove
  it and delete the folder without removing the product from their library.
- Another user cannot read or mutate those personal records by guessing IDs.
- Products no longer visible to the user are omitted from their library response
  and counted only as unavailable items, without revealing product metadata.
- Focused API and component tests cover ownership, visibility, limits,
  navigation context and the collapsed result layout.
