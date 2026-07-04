import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MAX_LINES = 350;
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(SCRIPT_DIR, "..");

const INCLUDED_EXTENSIONS = new Set([
  ".css",
  ".json",
  ".md",
  ".mjs",
  ".ps1",
  ".py",
  ".toml",
  ".ts",
  ".tsx",
  ".yaml",
  ".yml",
]);

const INCLUDED_FILENAMES = new Set([
  ".editorconfig",
  ".gitignore",
  "Dockerfile",
  "Makefile",
]);

const EXCLUDED_PATHS = new Set([
  "apps/api/uv.lock",
  "coeus_spec_driven_implementation_plan.md",
  "packages/contracts/openapi.json",
  "pnpm-lock.yaml",
]);

function listCandidateFiles() {
  return execFileSync(
    "git",
    ["ls-files", "--cached", "--others", "--exclude-standard"],
    {
      cwd: REPO_ROOT,
      encoding: "utf8",
    },
  )
    .split(/\r?\n/)
    .map((file) => file.trim())
    .filter(Boolean);
}

function shouldCheck(file) {
  const normalised = file.replaceAll("\\", "/");
  if (EXCLUDED_PATHS.has(normalised)) {
    return false;
  }
  const filename = normalised.split("/").at(-1) ?? "";
  return (
    INCLUDED_EXTENSIONS.has(extname(filename)) ||
    INCLUDED_FILENAMES.has(filename)
  );
}

function countLines(file) {
  const fullPath = join(REPO_ROOT, file);
  if (!existsSync(fullPath)) {
    return 0;
  }
  const text = readFileSync(fullPath, "utf8");
  if (text.length === 0) {
    return 0;
  }
  const normalised = text.replaceAll("\r\n", "\n").replaceAll("\r", "\n");
  const trailingNewline = normalised.endsWith("\n") ? 1 : 0;
  return normalised.split("\n").length - trailingNewline;
}

const violations = listCandidateFiles()
  .filter(shouldCheck)
  .map((file) => ({ file, lines: countLines(file) }))
  .filter(({ lines }) => lines > MAX_LINES)
  .sort((left, right) => right.lines - left.lines);

if (violations.length > 0) {
  console.error(`Files exceed the ${MAX_LINES}-line limit:`);
  for (const violation of violations) {
    console.error(`- ${violation.file}: ${violation.lines} lines`);
  }
  process.exit(1);
}

console.log(`All checked hand-written files are ${MAX_LINES} lines or fewer.`);
