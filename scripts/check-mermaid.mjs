import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { JSDOM } from "jsdom";

const root = process.cwd();
const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.Element = dom.window.Element;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.SVGElement = dom.window.SVGElement;
const { default: mermaid } = await import("mermaid");

function trackedMarkdownFiles() {
  const output = execFileSync(
    "git",
    [
      "ls-files",
      "-z",
      "--cached",
      "--others",
      "--exclude-standard",
      "--",
      "*.md",
    ],
    { cwd: root, encoding: "utf8" },
  );
  return output
    .split("\0")
    .filter(Boolean)
    .map((name) => path.join(root, name));
}

export function mermaidBlocks(markdown) {
  const blocks = [];
  const lines = markdown.split(/\r?\n/);
  let open = null;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (open === null) {
      const marker = line.match(/^ {0,3}(`{3,}|~{3,})\s*mermaid\s*$/i);
      if (marker) {
        open = {
          character: marker[1][0],
          length: marker[1].length,
          line: index + 1,
          content: [],
        };
      }
      continue;
    }

    const close = line.match(/^ {0,3}(`{3,}|~{3,})\s*$/);
    if (
      close &&
      close[1][0] === open.character &&
      close[1].length >= open.length
    ) {
      blocks.push({ line: open.line, source: open.content.join("\n") });
      open = null;
      continue;
    }
    open.content.push(line);
  }

  if (open !== null) {
    throw new Error(`Unclosed Mermaid fence starting at line ${open.line}`);
  }
  return blocks;
}

export function atlasBlockProblems(source) {
  const problems = [];
  const diagramType = source.match(/^\s*(\S+)/)?.[1];
  if (
    !["flowchart", "sequenceDiagram", "stateDiagram-v2", "erDiagram"].includes(
      diagramType,
    )
  ) {
    problems.push(
      `unsupported Atlas diagram type: ${diagramType ?? "missing"}`,
    );
  }
  if (!/^\s+accTitle:\s+\S/m.test(source)) {
    problems.push("missing accTitle");
  }
  if (!/^\s+accDescr:\s+\S/m.test(source)) {
    problems.push("missing accDescr");
  }
  return problems;
}

async function main() {
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    suppressErrorRendering: true,
  });

  const failures = [];
  let count = 0;
  for (const file of trackedMarkdownFiles()) {
    let blocks;
    try {
      blocks = mermaidBlocks(fs.readFileSync(file, "utf8"));
    } catch (error) {
      failures.push(`${path.relative(root, file)}: ${error.message}`);
      continue;
    }

    for (const block of blocks) {
      count += 1;
      const relative = path.relative(root, file);
      if (relative.startsWith(`docs${path.sep}architecture${path.sep}`)) {
        for (const problem of atlasBlockProblems(block.source)) {
          failures.push(`${relative}:${block.line} -> ${problem}`);
        }
      }
      try {
        await mermaid.parse(block.source, { suppressErrors: false });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        failures.push(
          `${path.relative(root, file)}:${block.line} -> ${message.replaceAll("\n", " ")}`,
        );
      }
    }
  }

  if (failures.length > 0) {
    console.error("Invalid Mermaid diagrams:");
    failures.forEach((failure) => console.error(`- ${failure}`));
    process.exitCode = 1;
    return;
  }
  console.log(`Parsed ${count} Mermaid diagrams in tracked Markdown files.`);
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  await main();
}
