# Air-gapped deployment runbook

## Purpose

This runbook packages Istari for a restricted or disconnected environment. It
is a preparation guide, not production accreditation. The target remains
subject to the current single-process, local-object and release gates.

## Package contents

Prepare these artefacts from one clean, reviewed Git revision:

- source archive and release note bound to the exact Git SHA;
- API and web container archives;
- one CycloneDX SBOM for each transferred image archive;
- enforcing Trivy reports for both images;
- Checkov, CodeQL, Semgrep and ZAP evidence from that revision; and
- a SHA-256 manifest for every transferred file.

Do not include `.env`, Terraform state or variables, credentials, database
dumps, browser screenshots or real intelligence content.

## Build

The final restricted-environment API origin must be known before building the
web image because Vite embeds it at build time. Export the reviewed commit with
`git archive`, then use only that export as the Docker build context. This
prevents ignored or untracked working-copy files from entering an image labelled
with the reviewed SHA. Build into the ignored `.local` area, never the working
tree. Run every PowerShell block below in the same PowerShell 7.3 or later
session so native-command failures stop packaging:

```powershell
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$releaseSha = (git rev-parse --verify HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $releaseSha -notmatch "^[0-9a-f]{40}$") {
  throw "Resolve an exact release commit before packaging."
}
$repoRoot = (git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0) { throw "Run this command from the reviewed repository." }
$releaseDir = Join-Path $repoRoot ".local/release/$releaseSha"
$buildDir = Join-Path $repoRoot ".local/build/$releaseSha"
$sourceArchive = Join-Path $releaseDir "source.zip"
$apiOrigin = "https://<final-internal-api-origin>"
$treeState = @(git status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $treeState.Count -ne 0) { throw "Use a clean reviewed worktree." }
if ((Test-Path -LiteralPath $releaseDir) -or (Test-Path -LiteralPath $buildDir)) {
  throw "Use new release and build directories."
}
if ($apiOrigin -match "[<>]") { throw "Set the final internal API origin." }
New-Item -ItemType Directory -Path $releaseDir, $buildDir | Out-Null
git -C $repoRoot archive --format=zip --output=$sourceArchive $releaseSha
if ($LASTEXITCODE -ne 0) { throw "Git archive creation failed." }
Expand-Archive -LiteralPath $sourceArchive -DestinationPath $buildDir
docker build -f "$buildDir/infra/docker/api.Dockerfile" `
  -t "coeus-api:$releaseSha" $buildDir
docker build --build-arg "VITE_API_BASE_URL=$apiOrigin" `
  -f "$buildDir/infra/docker/web-prod.Dockerfile" `
  -t "coeus-web:$releaseSha" $buildDir
docker save -o "$releaseDir/coeus-api.tar" "coeus-api:$releaseSha"
docker save -o "$releaseDir/coeus-web.tar" "coeus-web:$releaseSha"
```

## Verification before transfer

Install and verify dependencies inside the exported source tree, not the
working tree. Run the same independent line and branch coverage gate used by
the repository:

```powershell
Push-Location $buildDir
try {
  pnpm install --frozen-lockfile
  uv sync --project apps/api --frozen --all-groups
  uv run --directory apps/api pytest --cov-report=json:coverage.json
  uv run --project apps/api python scripts/check_backend_coverage.py apps/api/coverage.json
  uv run --directory apps/api bandit -r src
  uv run --directory apps/api pip-audit
  pnpm --filter @coeus/web lint
  pnpm --filter @coeus/web test
  pnpm --filter @coeus/web build
  pnpm docs:check
  pnpm line-limit
} finally {
  Pop-Location
}
```

Run local packaging checks with report output and an enforcing Trivy pass:

```powershell
$exportedFiles = @(Get-ChildItem -LiteralPath $buildDir -Force -File -Recurse)
if ($exportedFiles.Count -eq 0) { throw "The exported source tree is empty." }
gitleaks dir $buildDir --redact --verbose
uvx --from checkov checkov -d "$buildDir/infra/gcp" --framework terraform --compact `
  --output cli --output sarif --output-file-path "console,$releaseDir/checkov.sarif"
trivy image --format json --output "$releaseDir/trivy-api.json" `
  --severity HIGH,CRITICAL --ignore-unfixed "coeus-api:$releaseSha"
trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 "coeus-api:$releaseSha"
trivy image --format json --output "$releaseDir/trivy-web.json" `
  --severity HIGH,CRITICAL --ignore-unfixed "coeus-web:$releaseSha"
trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 "coeus-web:$releaseSha"
syft scan "docker-archive:$releaseDir/coeus-api.tar" `
  -o "cyclonedx-json=$releaseDir/coeus-api-sbom.cdx.json"
syft scan "docker-archive:$releaseDir/coeus-web.tar" `
  -o "cyclonedx-json=$releaseDir/coeus-web-sbom.cdx.json"
```

Confirm that each SBOM identifies its corresponding image archive, is not
empty, and contains the expected base operating-system and application runtime
packages. Record the Syft and Docker versions alongside the evidence.

CodeQL, Semgrep and ZAP are repository workflows rather than equivalent local
commands. Download their successful evidence for the exact SHA from GitHub and
place it in the release directory. If a required scanner is unavailable, record
that as a packaging blocker rather than presenting the bundle as verified.

After every local and downloaded artefact is present, create the transfer
manifest. It covers every other file in the directory:

```powershell
$manifestPath = Join-Path $releaseDir "SHA256SUMS.json"
$allEntries = @(Get-ChildItem -LiteralPath $releaseDir -Force -Recurse)
$reparsePoints = @(
  $allEntries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }
)
if ($reparsePoints.Count -ne 0) {
  throw "Release artefacts must not contain links or reparse points."
}
$manifest = $allEntries |
  Where-Object { -not $_.PSIsContainer -and $_.FullName -ne $manifestPath } |
  ForEach-Object {
    $digest = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    $relativePath = [IO.Path]::GetRelativePath($releaseDir, $_.FullName).Replace("\", "/")
    [ordered]@{ path = $relativePath; algorithm = $digest.Algorithm; hash = $digest.Hash.ToLower() }
  } | Sort-Object path
$manifest | ConvertTo-Json | Set-Content -Encoding utf8 $manifestPath
```

After transfer, recompute every SHA-256 digest before loading an image. Sign the
manifest using the organisation's approved signing process; this repository
does not prescribe or invent a key-management scheme.

## Restricted-environment notes

- Configure runtime secrets inside the target environment, never in an image.
- Use an internal registry and pinned image digests after import.
- Disable external model providers unless an approved internal endpoint exists.
- Keep seed users limited to local or explicitly approved development use.
- Repeat SBOM and scan evidence after any rebuild in the target environment.
- Record imported digests, source SHA, API origin and scanner versions in the
  deployment log.
