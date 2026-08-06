import { groupOpenRequests, requestGroupKey, sortRequests } from "./ticket-collection";

type Row = Parameters<typeof requestGroupKey>[0] & { reference: string };

function row(overrides: Partial<Row> & Pick<Row, "reference">): Row {
  return {
    state: "ANALYST_IN_PROGRESS",
    updatedAt: "2026-08-01T00:00:00Z",
    ...overrides,
  } as Row;
}

test("anything waiting on the requester is grouped first", () => {
  const groups = groupOpenRequests([
    row({ reference: "TCK-0003" }),
    row({ reference: "TCK-0002", state: "DRAFT_INTAKE" }),
    row({ reference: "TCK-0001", state: "RFI_MATCH_OFFERED" }),
  ]);

  expect(groups.map((group) => group.key)).toEqual(["action", "draft", "progress"]);
  expect(groups[0].title).toBe("Needs your action");
  expect(groups[0].tickets[0].reference).toBe("TCK-0001");
});

test("groups with nothing in them are left out entirely", () => {
  const groups = groupOpenRequests([row({ reference: "TCK-0001", state: "DRAFT_INTAKE" })]);

  expect(groups).toHaveLength(1);
  expect(groups[0].key).toBe("draft");
});

test("the API decides who owes an action, not the state alone", () => {
  // A collaborator sees actionRequired false on a state that would otherwise
  // read as theirs to answer, so it must not sit in their action group.
  const collaborator = row({
    reference: "TCK-0001",
    state: "RFI_MATCH_OFFERED",
    customerStatus: { actionRequired: false } as Row["customerStatus"],
  });

  expect(requestGroupKey(collaborator)).toBe("progress");
});

test("a request needing more information counts as needing action, not a draft", () => {
  expect(requestGroupKey(row({ reference: "TCK-0001", state: "INFO_REQUIRED" }))).toBe("action");
});

test("each sort orders on a value the system sets", () => {
  const tickets = [
    row({ reference: "TCK-0002", updatedAt: "2026-08-03T00:00:00Z" }),
    row({ reference: "TCK-0001", updatedAt: "2026-08-05T00:00:00Z" }),
    row({ reference: "TCK-0003", updatedAt: "2026-08-01T00:00:00Z" }),
  ];

  expect(sortRequests(tickets, "recent").map((item) => item.reference)).toEqual([
    "TCK-0001",
    "TCK-0002",
    "TCK-0003",
  ]);
  expect(sortRequests(tickets, "oldest").map((item) => item.reference)).toEqual([
    "TCK-0003",
    "TCK-0002",
    "TCK-0001",
  ]);
  expect(sortRequests(tickets, "reference").map((item) => item.reference)).toEqual([
    "TCK-0001",
    "TCK-0002",
    "TCK-0003",
  ]);
});

test("sorting does not mutate the list it was given", () => {
  const tickets = [
    row({ reference: "TCK-0002", updatedAt: "2026-08-01T00:00:00Z" }),
    row({ reference: "TCK-0001", updatedAt: "2026-08-05T00:00:00Z" }),
  ];

  sortRequests(tickets, "recent");

  expect(tickets.map((item) => item.reference)).toEqual(["TCK-0002", "TCK-0001"]);
});

test("the chosen sort applies inside every group", () => {
  const groups = groupOpenRequests(
    [
      row({ reference: "TCK-0002", state: "RFI_MATCH_OFFERED", updatedAt: "2026-08-01T00:00:00Z" }),
      row({ reference: "TCK-0001", state: "RFI_MATCH_OFFERED", updatedAt: "2026-08-05T00:00:00Z" }),
    ],
    "oldest",
  );

  expect(groups[0].tickets.map((item) => item.reference)).toEqual(["TCK-0002", "TCK-0001"]);
});
