"""Personal profile content for every seed user.

Kept apart from the team seeding logic so the people data reads like a
staff directory. Values respect the profile schema bounds (title 120,
up to 8 specialisms of 80 characters, bio 1000).
"""

# username -> (title, specialisms, bio)
PROFILE_SPECS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "admin@example.test": (
        "Platform Administrator",
        ("Account management", "Access control", "Audit review"),
        "Runs the Istari platform day to day: accounts, roles and access "
        "groups. First port of call when a queue looks wrong or a permission "
        "needs changing. Keeps an eye on the audit trail so nobody else has to.",
    ),
    "user@example.test": (
        "Operations Desk Officer",
        ("Maritime operations", "Request drafting"),
        "Front-line requester on the operations desk. Raises RFIs for the "
        "maritime watch floor and tracks them through to delivery. Prefers a "
        "quick call-back over a long clarification thread.",
    ),
    "colleague@example.test": (
        "Regional Liaison Officer",
        ("Partner liaison", "Reporting standards"),
        "Liaison officer for regional partners. Submits requests on behalf of "
        "partner desks and checks released products meet their reporting "
        "standards before they are passed on.",
    ),
    "jioc.team@example.test": (
        "JIOC Routing Officer",
        ("Tasking triage", "Collection requirements", "Route adjudication"),
        "Sits in the JIOC routing cell deciding whether new requests need "
        "fresh collection or can go straight to assessment. Ten years across "
        "tasking desks, so very hard to surprise with an unusual request.",
    ),
    "rfa.manager@example.test": (
        "Head of RFA Assessment",
        ("Team leadership", "Assessment tradecraft", "Analytic standards"),
        "Leads the RFA assessment team: assigns analysts, balances workload "
        "against the team calendar and approves work before it reaches "
        "quality control. Champions structured analytic techniques and short "
        "sentences.",
    ),
    "rfa.team@example.test": (
        "RFA Desk Coordinator",
        ("Queue management", "Customer clarifications", "Workflow tracking"),
        "Coordinates the RFA desk: keeps the queue honest, chases "
        "clarifications with customers and makes sure nothing sits unassigned "
        "for long. The team's institutional memory for past requests.",
    ),
    "collection.manager@example.test": (
        "Head of Collection Management",
        ("Collection planning", "Sensor tasking", "Source evaluation"),
        "Runs the collection management team. Turns approved requirements "
        "into sensor tasking, weighs collect options against risk and cost, "
        "and approves collect products before quality control review.",
    ),
    "collection.team@example.test": (
        "Collection Requirements Officer",
        ("Requirements drafting", "Imagery tasking", "SIGINT liaison"),
        "Drafts and tracks collection requirements. Works the seams between "
        "imagery, signals and open-source collect so a tasked requirement "
        "comes back as a usable product, not a surprise.",
    ),
    "store.manager@example.test": (
        "Intelligence Store Curator",
        ("Product curation", "Metadata standards", "Release hygiene"),
        "Curates the intelligence store: catalogues new products, keeps "
        "metadata and tagging consistent and retires stale holdings. If a "
        "search misses something useful, the curator wants to know why.",
    ),
    "analyst@example.test": (
        "All-Source Intelligence Analyst",
        ("All-source fusion", "Threat assessment", "Report writing"),
        "General duties analyst working across the RFA and collection teams. "
        "Comfortable fusing imagery, signals and open-source reporting into a "
        "single balanced assessment under deadline.",
    ),
    "analyst.maritime@example.test": (
        "Maritime Assessment Analyst",
        ("Maritime domain awareness", "AIS analysis", "Port infrastructure"),
        "Tracks shipping behaviour, dark fleet activity and port "
        "infrastructure. Happiest with a plot of AIS tracks and a suspicious "
        "gap to explain. Duty analyst for maritime surge tasking.",
    ),
    "analyst.cyber@example.test": (
        "Cyber Threat Analyst",
        ("Intrusion analysis", "Malware triage", "Infrastructure mapping"),
        "Covers hostile cyber activity: intrusion sets, tooling and the "
        "infrastructure behind them. Writes assessments that a non-technical "
        "customer can act on without a glossary.",
    ),
    "analyst.geo@example.test": (
        "Geospatial Assessment Analyst",
        ("Imagery analysis", "Geospatial products", "Change detection"),
        "Produces geospatial assessments: annotated imagery, change "
        "detection and terrain products. Believes every claim in a report "
        "should be traceable to a coordinate.",
    ),
    "qc.manager@example.test": (
        "Head of Quality Control",
        ("Analytic review", "Release authority", "Tradecraft standards"),
        "Final gate before anything reaches a customer. Reviews products for "
        "sourcing, argumentation and presentation, and owns the release "
        "decision. Fair, thorough and immune to deadline pressure.",
    ),
    "disabled@example.test": (
        "Former Desk Officer",
        (),
        "Account retained for audit history only.",
    ),
}
