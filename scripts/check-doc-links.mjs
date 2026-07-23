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

function closingDelimiter(value, start, opening, closing) {
  let depth = 0;
  for (let index = start; index < value.length; index += 1) {
    if (value[index] === "\\") {
      index += 1;
      continue;
    }
    if (value[index] === opening) depth += 1;
    if (value[index] === closing) {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return -1;
}

function closingAngle(value, start) {
  let quote = null;
  for (let index = start + 1; index < value.length; index += 1) {
    const character = value[index];
    if (quote !== null) {
      if (character === quote) quote = null;
    } else if (character === '"' || character === "'") {
      quote = character;
    } else if (character === ">") {
      return index;
    }
  }
  return -1;
}

function visibleEntityText(entity) {
  const normalised = entity.toLowerCase();
  if (normalised === "nbsp") return " ";
  if (["amp", "apos", "gt", "lt", "quot"].includes(normalised)) return "";

  const radix = normalised.startsWith("#x") ? 16 : 10;
  const digits = normalised.startsWith("#x")
    ? normalised.slice(2)
    : normalised.startsWith("#")
      ? normalised.slice(1)
      : "";
  if (!digits) return "";
  const codePoint = Number.parseInt(digits, radix);
  if (!Number.isInteger(codePoint) || codePoint > 0x10ffff) return "";
  const character = String.fromCodePoint(codePoint);
  return /^[\p{L}\p{N}\s_-]$/u.test(character) ? character : "";
}

function visibleHeadingText(markdown) {
  let visible = "";
  for (let index = 0; index < markdown.length; index += 1) {
    const character = markdown[index];
    if (character === "\\" && index + 1 < markdown.length) {
      visible += markdown[index + 1];
      index += 1;
      continue;
    }
    if (character === "`") {
      const marker = markdown.slice(index).match(/^`+/)?.[0] ?? "`";
      const closing = markdown.indexOf(marker, index + marker.length);
      if (closing !== -1) {
        visible += markdown.slice(index + marker.length, closing);
        index = closing + marker.length - 1;
        continue;
      }
    }

    const bracketStart =
      character === "["
        ? index
        : character === "!" && markdown[index + 1] === "["
          ? index + 1
          : -1;
    if (bracketStart !== -1) {
      const labelEnd = closingDelimiter(markdown, bracketStart, "[", "]");
      if (labelEnd !== -1) {
        visible += visibleHeadingText(
          markdown.slice(bracketStart + 1, labelEnd),
        );
        index = labelEnd;
        const destinationStart = markdown[index + 1];
        if (destinationStart === "(" || destinationStart === "[") {
          const destinationEnd = closingDelimiter(
            markdown,
            index + 1,
            destinationStart,
            destinationStart === "(" ? ")" : "]",
          );
          if (destinationEnd !== -1) index = destinationEnd;
        }
        continue;
      }
    }

    if (character === "<") {
      const closing = closingAngle(markdown, index);
      if (closing !== -1) {
        const content = markdown.slice(index + 1, closing);
        const isTag =
          /^!--/.test(content) ||
          /^\/?[a-z][a-z0-9-]*(?:\s|\/|$)/i.test(content);
        if (!isTag) visible += content;
        index = closing;
        continue;
      }
    }

    if (character === "&") {
      const entity = markdown
        .slice(index)
        .match(/^&(#x?[\da-f]+|[a-z][\da-z]+);/i);
      if (entity) {
        visible += visibleEntityText(entity[1]);
        index += entity[0].length - 1;
        continue;
      }
    }
    visible += character;
  }
  return visible;
}

function headingSlug(heading) {
  return visibleHeadingText(heading)
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
