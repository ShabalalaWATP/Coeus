import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const markdownLink = /!?\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\)/g;
const referenceLink = /^\s*\[[^\]]+\]:\s*(?:<([^>]+)>|([^\s]+))/gm;

function markdownFiles(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const candidate = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(candidate);
    return entry.isFile() && entry.name.endsWith(".md") ? [candidate] : [];
  });
}

function localTarget(rawTarget, source) {
  const target = decodeURIComponent(rawTarget.split("#", 1)[0].split("?", 1)[0]);
  if (
    target === "" ||
    target.startsWith("#") ||
    /^[a-z][a-z0-9+.-]*:/i.test(target) ||
    target.startsWith("//")
  ) {
    return null;
  }
  return target.startsWith("/")
    ? path.join(root, target.slice(1))
    : path.resolve(path.dirname(source), target);
}

const files = [
  ...markdownFiles(path.join(root, "docs")),
  ...["README.md", "CONTRIBUTING.md", "SECURITY.md"]
    .map((name) => path.join(root, name))
    .filter(fs.existsSync),
];
const failures = [];
for (const source of files) {
  const content = fs.readFileSync(source, "utf8");
  for (const expression of [markdownLink, referenceLink]) {
    expression.lastIndex = 0;
    for (const match of content.matchAll(expression)) {
      const rawTarget = match[1] ?? match[2];
      const target = localTarget(rawTarget, source);
      if (target && !fs.existsSync(target)) {
        const line = content.slice(0, match.index).split("\n").length;
        failures.push(`${path.relative(root, source)}:${line} -> ${rawTarget}`);
      }
    }
  }
}

if (failures.length > 0) {
  console.error("Broken local Markdown links or images:");
  failures.forEach((failure) => console.error(`- ${failure}`));
  process.exit(1);
}
console.log(`Validated local links and images in ${files.length} Markdown files.`);
