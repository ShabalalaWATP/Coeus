# Spec: Synthetic Intelligence Library and Search Assurance

## Goal

Make the local Intelligence Store useful for realistic demonstrations by adding
a broad, deterministic and public-repository-safe PDF corpus, then prove that
both Store browse search and the RFI Search Agent retrieve only products the
requesting user is authorised to see.

## Scope

- Add 144 multi-page PDF products to the local demo catalogue.
- Cover synthetic Russia, Iran and China reporting together with Army, armour,
  tanks, missiles, artillery, drones, electronic warfare, SIGINT and cyber
  themes.
- Add 15 specialist ACGs for country and capability need-to-know boundaries.
- Give the synthetic Billy Gilmour customer membership of almost every active
  demo ACG while retaining a small deny-test set.
- Generate real PDF bytes at local seed time. Generated binaries remain outside
  Git in local object storage.
- Improve military-domain semantic labels and add scenario-level search tests.
- Preserve the existing hybrid retrieval, access filtering and explainable
  match reasons.

## Public Repository Safety

- Every title, summary, description and PDF page must say `MOCK DATA ONLY` or
  clearly identify the content as a synthetic exercise product.
- Products may use real country and generic equipment-category names for search
  realism, but must not assert real intelligence, identify real units, include
  precise operational locations or reproduce real reports.
- PDF narratives use fictional observations, approximate training-area language
  and explicitly synthetic judgements.
- Runtime object-store binaries are generated from deterministic metadata and
  code. A synthetic-only export is versioned under
  `demo-assets/intelligence-store/` for demonstrations and review.

## Demo Corpus

The corpus contains 144 products across 15 synthetic reporting scenarios and
ten report variants. Each product has:

- a stable product ID, reference and asset ID;
- one real multi-page PDF asset with a stable hash;
- title, summary, description, region, coverage dates and classification level;
- tags and semantic labels that mirror the important PDF terminology;
- one or more active ACGs;
- `MOCK` releasability and `MOCK DATA ONLY` handling caveats;
- published status so it can participate in authorised search.

## Specialist ACGs

The demo adds:

- `ACG-RU-LAND`, `ACG-RU-EW`, `ACG-RU-SIGINT`, `ACG-RU-MISSILE`,
  `ACG-RU-UAS`;
- `ACG-IR-LAND`, `ACG-IR-EW`, `ACG-IR-SIGINT`, `ACG-IR-MISSILE`,
  `ACG-IR-CYBER`;
- `ACG-CN-LAND`, `ACG-CN-EW`, `ACG-CN-SIGINT`, `ACG-CN-UAS`,
  `ACG-CN-CYBER`.

Each ACG is active, has a synthetic description and an existing synthetic
administrator as owner. Existing persisted local stores receive missing demo
ACGs without overwriting user-managed ACG records.

Billy Gilmour receives membership of all active demo ACGs except
`ACG-RU-SIGINT` and `ACG-CN-CYBER`. Those exclusions retain meaningful negative
access tests while making this account useful for Store and RFI demonstrations.

## Search Quality

Both search paths continue to use product metadata as the retrieval document.
The generated PDF's salient terminology is mirrored in the product title,
summary, description, tags and semantic labels so the index and PDF remain
consistent without introducing an unbounded document-extraction pipeline.

Military-domain labels cover:

- Russia, Iran and China;
- land warfare, armour, tanks and artillery;
- missiles and air defence;
- drones, UAS and counter-UAS;
- electronic warfare, spectrum activity and SIGINT;
- cyber operations and network defence.

Regular Store search must return relevant ranked products for representative
queries. RFI Search must offer relevant products when the requester has the
required ACG and must return no hidden product, hidden count or hidden match
reason when the requester lacks it.

## Access-Control Invariants

- Every Store product must have at least one active ACG.
- Product creation and QC publication continue to reject zero, inactive or
  unauthorised ACG assignments.
- Store browse, detail, preview, asset grants and downloads continue to enforce
  active membership, clearance, product state and role permissions.
- RFI candidates are retrieved in the requester's visibility scope, not the
  operator's broader scope, and service-layer policy rechecks remain mandatory.
- A product assigned to multiple ACGs is visible when the requester belongs to
  at least one of them and meets every other policy check.

## PDF Layout

Generated PDFs contain a cover, executive summary, key judgements, synthetic
indicator table, assessment, implications, collection gaps and methodology.
Every page has a visible mock banner, stable reference and page number. Layout
must render without clipping, overlap, broken tables or unreadable glyphs.

## Acceptance Criteria

- The live local Store contains at least 144 new PDF products and all generated
  assets begin with a valid PDF header.
- Representative PDFs render cleanly to PNG and contain three or more pages.
- The corpus contains the requested country and military-domain vocabulary in
  both PDF text and indexed metadata.
- A fresh local demo contains exactly 189 products and 58 ACGs.
- All 15 specialist ACGs exist after local demo seeding.
- Billy Gilmour belongs to 13 of the 15 specialist ACGs and all 43 baseline
  groups, for 56 of 58 active demo ACGs.
- Every demo product has one or more active ACGs.
- Store searches for representative Russia/EW, Iran/missile and China/cyber
  queries return relevant products in ranked results.
- An RFI about drones, artillery or SIGINT offers relevant permitted products.
- Negative tests prove hidden products do not affect Store or RFI results.
- Generation is deterministic and idempotent across repeated local starts.
- Backend and frontend coverage remain at or above 95 percent for lines and
  branches, and all repository quality gates pass.
