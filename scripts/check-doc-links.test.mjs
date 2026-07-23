import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { anchorsFor, isInsideRepository } from "./check-doc-links.mjs";

test("collects GitHub-style headings and duplicate suffixes", () => {
  const anchors = anchorsFor(
    "# Title\n## Repeated\n## Repeated\n## Access groups (ACGs)\n",
  );

  assert.deepEqual(
    [...anchors],
    ["title", "repeated", "repeated-1", "access-groups-acgs"],
  );
});

test("ignores headings inside backtick and tilde fences", () => {
  const anchors = anchorsFor(
    "# Visible\n```powershell\n# Hidden\n```\n~~~text\n## Also hidden\n~~~\n## Visible too\n",
  );

  assert.deepEqual([...anchors], ["visible", "visible-too"]);
});

test("rejects the repository parent and its descendants", () => {
  const repository = process.cwd();

  assert.equal(isInsideRepository(repository), true);
  assert.equal(
    isInsideRepository(path.join(repository, "docs", "README.md")),
    true,
  );
  assert.equal(isInsideRepository(path.dirname(repository)), false);
  assert.equal(
    isInsideRepository(path.join(repository, "..", "outside.md")),
    false,
  );
});
