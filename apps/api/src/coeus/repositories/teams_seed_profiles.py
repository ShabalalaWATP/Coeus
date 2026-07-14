"""Synthetic personal profiles for the local demonstration workforce.

Display names are borrowed from Scottish footballers, but every role and
biography below is fictional and makes no claim about the real person.
"""

ProfileSpec = tuple[str, tuple[str, ...], str]

# username -> (title, specialisms, bio)
PROFILE_SPECS: dict[str, ProfileSpec] = {
    "admin@example.test": (
        "Platform Security Administrator",
        ("Identity administration", "Access control", "Audit review"),
        "Synthetic exercise persona responsible for account administration, "
        "role assurance and audit review across the intelligence workspace. "
        "Coordinates access incidents and keeps local demonstration controls "
        "aligned with the approved security model.",
    ),
    "user@example.test": (
        "Operational Intelligence Requirements Officer",
        ("Requirement definition", "Operational liaison", "Priority setting"),
        "Synthetic exercise persona working on an operational headquarters "
        "watch floor. Converts command questions into bounded intelligence "
        "requirements, records decision deadlines and confirms whether the "
        "delivered assessment answered the original need.",
    ),
    "colleague@example.test": (
        "Joint Operations Liaison Officer",
        ("Partner liaison", "Requirement coordination", "Release caveats"),
        "Synthetic exercise persona coordinating intelligence requirements "
        "between joint staff branches. Checks intended audiences and handling "
        "constraints before requests enter the assessment workflow.",
    ),
    "jioc.team@example.test": (
        "JIOC Intelligence Watch Officer",
        ("Tasking triage", "Route adjudication", "Operational monitoring"),
        "Synthetic exercise persona maintaining the intelligence operations "
        "picture, triaging incoming requirements and routing each task to an "
        "assessment or collection team without changing the underlying need.",
    ),
    "rfa.manager@example.test": (
        "Senior Assessment Manager",
        ("Assessment leadership", "Analytic standards", "Workload balancing"),
        "Synthetic exercise persona leading the assessment team. Selects an "
        "appropriate team, assigns available generic analysts and reviews "
        "scope, sourcing and confidence before work moves to quality control.",
    ),
    "rfa.team@example.test": (
        "Assessment Coordination Officer",
        ("Queue management", "Customer clarification", "Workflow tracking"),
        "Synthetic exercise persona coordinating the assessment queue, "
        "obtaining missing context from requesters and maintaining a clear "
        "record of deadlines, ownership and outstanding decisions.",
    ),
    "collection.manager@example.test": (
        "Collection Requirements Manager",
        ("Collection planning", "Source evaluation", "Risk management"),
        "Synthetic exercise persona translating approved intelligence gaps "
        "into proportionate collection plans. Balances timeliness, source "
        "suitability and risk before assigning work to the collection team.",
    ),
    "collection.team@example.test": (
        "Collection Requirements Officer",
        ("Requirement drafting", "Collection coordination", "Source validation"),
        "Synthetic exercise persona drafting and tracking collection "
        "requirements across imagery, signals and open sources, then checking "
        "that returned material is usable by the assigned analyst.",
    ),
    "store.manager@example.test": (
        "Intelligence Library Manager",
        ("Product curation", "Metadata standards", "Review scheduling"),
        "Synthetic exercise persona maintaining the intelligence product "
        "library, enforcing metadata quality and review dates, and helping "
        "teams find releasable existing work before commissioning new output.",
    ),
    "analyst@example.test": (
        "Military Intelligence Analyst",
        ("All-source assessment", "Structured analysis", "Strategic warning"),
        "Synthetic exercise persona producing balanced all-source assessments "
        "for operational and strategic decision-makers. Tests competing "
        "hypotheses, records confidence and separates evidence from judgement.",
    ),
    "analyst.2@example.test": (
        "Military Intelligence Analyst",
        ("Maritime security", "Geospatial reasoning", "Pattern analysis"),
        "Synthetic exercise persona assessing maritime activity, port access "
        "and sea-line risk. Uses location, timing and behavioural patterns to "
        "explain anomalies while making collection gaps explicit.",
    ),
    "analyst.3@example.test": (
        "Military Intelligence Analyst",
        ("Cyber threat analysis", "Infrastructure mapping", "Technical reporting"),
        "Synthetic exercise persona assessing hostile cyber capability and "
        "intent. Correlates technical indicators with wider intelligence and "
        "writes conclusions that non-technical commanders can act upon.",
    ),
    "analyst.4@example.test": (
        "Military Intelligence Analyst",
        ("Land forces", "Order of battle", "Terrain assessment"),
        "Synthetic exercise persona analysing force posture, readiness and "
        "terrain constraints. Builds traceable order-of-battle judgements and "
        "states assumptions where reporting is incomplete.",
    ),
    "qc.manager@example.test": (
        "Senior Intelligence Review Officer",
        ("Analytic review", "Source assurance", "Release governance"),
        "Synthetic exercise persona providing an independent quality-control "
        "gate. Reviews sourcing, argument strength, uncertainty, presentation "
        "and authorised audience before approving a product for release.",
    ),
    "disabled@example.test": (
        "Former Military Intelligence Analyst",
        (),
        "Synthetic exercise persona retained in inactive status solely to "
        "preserve workflow and audit-history demonstrations.",
    ),
}


# Exact previous seed values permit a one-time, non-destructive upgrade while
# preserving any profile that a local user has edited.
LEGACY_PROFILE_SPECS: dict[str, ProfileSpec] = {
    "admin@example.test": (
        "Platform Administrator",
        ("Account management", "Access control", "Audit review"),
        "Runs the Istari platform day to day: accounts, roles and access groups. "
        "First port of call when a queue looks wrong or a permission needs changing. "
        "Keeps an eye on the audit trail so nobody else has to.",
    ),
    "user@example.test": (
        "Operations Desk Officer",
        ("Maritime operations", "Request drafting"),
        "Front-line requester on the operations desk. Raises RFIs for the maritime "
        "watch floor and tracks them through to delivery. Prefers a quick call-back "
        "over a long clarification thread.",
    ),
    "colleague@example.test": (
        "Regional Liaison Officer",
        ("Partner liaison", "Reporting standards"),
        "Liaison officer for regional partners. Submits requests on behalf of partner "
        "desks and checks released products meet their reporting standards before they "
        "are passed on.",
    ),
    "jioc.team@example.test": (
        "JIOC Routing Officer",
        ("Tasking triage", "Collection requirements", "Route adjudication"),
        "Sits in the JIOC routing cell deciding whether new requests need fresh "
        "collection or can go straight to assessment. Ten years across tasking desks, "
        "so very hard to surprise with an unusual request.",
    ),
    "rfa.manager@example.test": (
        "Head of RFA Assessment",
        ("Team leadership", "Assessment tradecraft", "Analytic standards"),
        "Leads the RFA assessment team: assigns analysts, balances workload against "
        "the team calendar and approves work before it reaches quality control. "
        "Champions structured analytic techniques and short sentences.",
    ),
    "rfa.team@example.test": (
        "RFA Desk Coordinator",
        ("Queue management", "Customer clarifications", "Workflow tracking"),
        "Coordinates the RFA desk: keeps the queue honest, chases clarifications with "
        "customers and makes sure nothing sits unassigned for long. The team's "
        "institutional memory for past requests.",
    ),
    "collection.manager@example.test": (
        "Head of Collection Management",
        ("Collection planning", "Sensor tasking", "Source evaluation"),
        "Runs the collection management team. Turns approved requirements into sensor "
        "tasking, weighs collect options against risk and cost, and approves collect "
        "products before quality control review.",
    ),
    "collection.team@example.test": (
        "Collection Requirements Officer",
        ("Requirements drafting", "Imagery tasking", "SIGINT liaison"),
        "Drafts and tracks collection requirements. Works the seams between imagery, "
        "signals and open-source collect so a tasked requirement comes back as a "
        "usable product, not a surprise.",
    ),
    "store.manager@example.test": (
        "Intelligence Store Curator",
        ("Product curation", "Metadata standards", "Release hygiene"),
        "Curates the intelligence store: catalogues new products, keeps metadata and "
        "tagging consistent and retires stale holdings. If a search misses something "
        "useful, the curator wants to know why.",
    ),
    "analyst@example.test": (
        "All-Source Intelligence Analyst",
        ("All-source fusion", "Threat assessment", "Report writing"),
        "General duties analyst working across the RFA and collection teams. "
        "Comfortable fusing imagery, signals and open-source reporting into a single "
        "balanced assessment under deadline.",
    ),
    "analyst.2@example.test": (
        "Maritime Assessment Analyst",
        ("Maritime domain awareness", "AIS analysis", "Port infrastructure"),
        "Tracks shipping behaviour, dark fleet activity and port infrastructure. "
        "Happiest with a plot of AIS tracks and a suspicious gap to explain. Duty "
        "analyst for maritime surge tasking.",
    ),
    "analyst.3@example.test": (
        "Cyber Threat Analyst",
        ("Intrusion analysis", "Malware triage", "Infrastructure mapping"),
        "Covers hostile cyber activity: intrusion sets, tooling and the infrastructure "
        "behind them. Writes assessments that a non-technical customer can act on "
        "without a glossary.",
    ),
    "analyst.4@example.test": (
        "Geospatial Assessment Analyst",
        ("Imagery analysis", "Geospatial products", "Change detection"),
        "Produces geospatial assessments: annotated imagery, change detection and "
        "terrain products. Believes every claim in a report should be traceable to a "
        "coordinate.",
    ),
    "qc.manager@example.test": (
        "Head of Quality Control",
        ("Analytic review", "Release authority", "Tradecraft standards"),
        "Final gate before anything reaches a customer. Reviews products for sourcing, "
        "argumentation and presentation, and owns the release decision. Fair, "
        "thorough and immune to deadline pressure.",
    ),
    "disabled@example.test": (
        "Former Desk Officer",
        (),
        "Account retained for audit history only.",
    ),
}
