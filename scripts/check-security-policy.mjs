import { readFileSync } from "node:fs";

const workflow = readFileSync(".github/workflows/security-dast.yml", "utf8");
const rules = readFileSync(".zap/rules.tsv", "utf8");
const airGapRunbook = readFileSync(
  "docs/runbooks/air-gapped-deployment.md",
  "utf8",
);
const dockerIgnore = new Set(
  readFileSync(".dockerignore", "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean),
);
const failures = [];

if (/cmd_options:\s*["'][^"']*(?:^|\s)-I(?:\s|$)/m.test(workflow)) {
  failures.push("ZAP must not ignore warning exit codes with -I.");
}
if (!/fail_action:\s*true/.test(workflow)) {
  failures.push("ZAP must fail the workflow when the policy reports an issue.");
}
if (!/rules_file_name:\s*\.zap\/rules\.tsv/.test(workflow)) {
  failures.push("ZAP must use the reviewed repository rules file.");
}
if (!/^\d+\t(?:FAIL|WARN|IGNORE)\t\S.+$/m.test(rules)) {
  failures.push(
    "The ZAP rules file must contain explicit, justified decisions.",
  );
}
for (const required of [
  ".local",
  ".local-data",
  "**/data",
  "**/tmp",
  "**/.terraform",
  "**/*.tfvars",
  "**/*.tfvars.json",
  "**/*.tfstate",
  "**/*.tfstate.*",
  "**/*.tfplan",
  "**/override.tf",
  "**/override.tf.json",
  "**/*_override.tf",
  "**/*_override.tf.json",
]) {
  if (!dockerIgnore.has(required)) {
    failures.push(`Docker build contexts must ignore ${required}.`);
  }
}
for (const [pattern, requirement] of [
  [
    /\$ErrorActionPreference\s*=\s*"Stop"/,
    "stop when a PowerShell packaging command fails",
  ],
  [
    /\$PSNativeCommandUseErrorActionPreference\s*=\s*\$true/,
    "stop when a native packaging command fails",
  ],
  [/git\s+-C\s+\$repoRoot\s+archive/, "export the reviewed Git commit"],
  [
    /docker build[\s\S]*?-t "coeus-api:\$releaseSha" \$buildDir/,
    "build the API image from the exported source",
  ],
  [
    /docker build --build-arg[\s\S]*?-t "coeus-web:\$releaseSha" \$buildDir/,
    "build the web image from the exported source",
  ],
  [
    /docker-archive:\$releaseDir\/coeus-api\.tar/,
    "generate the API SBOM from the transferred image archive",
  ],
  [
    /docker-archive:\$releaseDir\/coeus-web\.tar/,
    "generate the web SBOM from the transferred image archive",
  ],
  [/gitleaks dir \$buildDir/, "scan the exported source directory"],
  [/-Force -File -Recurse/, "include hidden exported source files"],
  [
    /\$exportedFiles\.Count\s+-eq\s+0\)\s*\{\s*throw/,
    "reject an empty exported source tree",
  ],
  [
    /Get-ChildItem[^\r\n]*\$releaseDir -Force -Recurse/,
    "enumerate hidden and nested transfer artefacts",
  ],
  [
    /\$allEntries[\s\S]*?FileAttributes\]::ReparsePoint/,
    "reject file and directory reparse points",
  ],
  [/GetRelativePath/, "record canonical relative manifest paths"],
]) {
  if (!pattern.test(airGapRunbook)) {
    failures.push(`The air-gapped runbook must ${requirement}.`);
  }
}

if (failures.length > 0) {
  for (const failure of failures) console.error(failure);
  process.exit(1);
}

console.log("DAST and Docker-context policies are fail-closed.");
