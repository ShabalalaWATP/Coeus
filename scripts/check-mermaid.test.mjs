import assert from "node:assert/strict";
import test from "node:test";

import { atlasBlockProblems, mermaidBlocks } from "./check-mermaid.mjs";

test("extracts backtick and tilde Mermaid blocks with source lines", () => {
  const blocks = mermaidBlocks(
    "# Views\n```mermaid\nflowchart LR\n    A --> B\n```\n\n~~~MERMAID\nsequenceDiagram\n    A->>B: event\n~~~\n",
  );

  assert.deepEqual(blocks, [
    { line: 2, source: "flowchart LR\n    A --> B" },
    { line: 7, source: "sequenceDiagram\n    A->>B: event" },
  ]);
});

test("requires stable Atlas types and accessible metadata", () => {
  assert.deepEqual(
    atlasBlockProblems(
      "flowchart LR\n    accTitle: Accessible view\n    accDescr: A useful description\n    A --> B",
    ),
    [],
  );
  assert.deepEqual(atlasBlockProblems("architecture-beta\n    service api"), [
    "unsupported Atlas diagram type: architecture-beta",
    "missing accTitle",
    "missing accDescr",
  ]);
});

test("rejects an unclosed Mermaid fence", () => {
  assert.throws(
    () => mermaidBlocks("```mermaid\nflowchart LR\n    A --> B"),
    /Unclosed Mermaid fence starting at line 1/,
  );
});
