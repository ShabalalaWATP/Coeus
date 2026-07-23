import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const root = process.cwd();
const markdownLink = /!?\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\)/g;
const referenceLink = /^\s*\[[^\]]+\]:\s*(?:<([^>]+)>|([^\s]+))/gm;

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
    {
      cwd: root,
      encoding: "utf8",
    },
  );
  return output
    .split("\0")
    .filter(Boolean)
    .map((name) => path.join(root, name));
}

function decode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function localReference(rawTarget, source) {
  if (/^[a-z][a-z0-9+.-]*:/i.test(rawTarget) || rawTarget.startsWith("//")) {
    return null;
  }

  const [withoutFragment, rawFragment] = rawTarget.split("#", 2);
  const pathPart = decode(withoutFragment.split("?", 1)[0]);
  const target = pathPart
    ? pathPart.startsWith("/")
      ? path.join(root, pathPart.slice(1))
      : path.resolve(path.dirname(source), pathPart)
    : source;
  return {
    target,
    fragment: rawFragment ? decode(rawFragment.split("?", 1)[0]) : null,
  };
}

function headingText(markdown) {
  return markdown
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, "")
    .replace(/[`*_~]/g, "")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">");
}

function headingSlug(heading) {
  return headingText(heading)
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .replace(/\s/g, "-");
}

export function isInsideRepository(target) {
  const relative = path.relative(root, target);
  return (
    relative === "" ||
    (relative !== ".." &&
      !relative.startsWith(`..${path.sep}`) &&
      !path.isAbsolute(relative))
  );
}

export function anchorsFor(markdown) {
  const anchors = new Set();
  const duplicates = new Map();
  let fence = null;
  for (const line of markdown.split(/\r?\n/)) {
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})/);
    if (marker) {
      const candidate = marker[1];
      if (fence === null) {
        fence = { character: candidate[0], length: candidate.length };
      } else if (
        candidate[0] === fence.character &&
        candidate.length >= fence.length
      ) {
        fence = null;
      }
      continue;
    }
    if (fence !== null) continue;

    const heading = line.match(/^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$/);
    if (heading) {
      const base = headingSlug(heading[1]);
      const duplicate = duplicates.get(base) ?? 0;
      anchors.add(duplicate === 0 ? base : `${base}-${duplicate}`);
      duplicates.set(base, duplicate + 1);
    }
    for (const match of line.matchAll(
      /<(?:a|span)\s+(?:name|id)=["']([^"']+)["'][^>]*>/gi,
    )) {
      anchors.add(match[1]);
    }
  }
  return anchors;
}

function main() {
  const files = trackedMarkdownFiles();
  const contentByFile = new Map(
    files.map((file) => [file, fs.readFileSync(file, "utf8")]),
  );
  const anchorsByFile = new Map();
  const failures = [];

  for (const source of files) {
    const content = contentByFile.get(source);
    for (const expression of [markdownLink, referenceLink]) {
      expression.lastIndex = 0;
      for (const match of content.matchAll(expression)) {
        const rawTarget = match[1] ?? match[2];
        const reference = localReference(rawTarget, source);
        if (!reference) continue;

        const line = content.slice(0, match.index).split("\n").length;
        if (!isInsideRepository(reference.target)) {
          failures.push(
            `${path.relative(root, source)}:${line} -> ${rawTarget} (outside repository)`,
          );
          continue;
        }
        if (!fs.existsSync(reference.target)) {
          failures.push(
            `${path.relative(root, source)}:${line} -> ${rawTarget}`,
          );
          continue;
        }
        if (
          reference.fragment &&
          path.extname(reference.target).toLowerCase() === ".md"
        ) {
          const targetAnchors =
            anchorsByFile.get(reference.target) ??
            anchorsFor(
              contentByFile.get(reference.target) ??
                fs.readFileSync(reference.target, "utf8"),
            );
          anchorsByFile.set(reference.target, targetAnchors);
          if (!targetAnchors.has(reference.fragment)) {
            failures.push(
              `${path.relative(root, source)}:${line} -> ${rawTarget} (missing heading anchor)`,
            );
          }
        }
      }
    }
  }

  if (failures.length > 0) {
    console.error("Broken local Markdown links, images or heading anchors:");
    failures.forEach((failure) => console.error(`- ${failure}`));
    process.exitCode = 1;
    return;
  }
  console.log(
    `Validated local links, images and heading anchors in ${files.length} Git-known Markdown files.`,
  );
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  main();
}
