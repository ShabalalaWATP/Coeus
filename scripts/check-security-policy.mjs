import { readFileSync } from "node:fs";

const workflow = readFileSync(".github/workflows/security-dast.yml", "utf8");
const rules = readFileSync(".zap/rules.tsv", "utf8");
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
  failures.push("The ZAP rules file must contain explicit, justified decisions.");
}

if (failures.length > 0) {
  for (const failure of failures) console.error(failure);
  process.exit(1);
}

console.log("DAST policy is fail-closed and uses reviewed ZAP rules.");
