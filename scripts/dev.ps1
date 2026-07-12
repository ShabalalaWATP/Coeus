param(
    [switch]$Detached
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $projectRoot
try {
    $postgresArgs = @("compose", "up", "-d", "--force-recreate", "postgres")
    & docker @postgresArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Could not recreate the local PostgreSQL container."
    }

    $postgresBinding = (& docker compose port postgres 5432 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $postgresBinding -notmatch "^127\.0\.0\.1:\d+$") {
        throw "PostgreSQL is not bound only to 127.0.0.1 (reported: '$postgresBinding')."
    }

    $composeArgs = @("compose", "up", "--build")
    if ($Detached) {
        $composeArgs += "-d"
    }
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed to start the local stack."
    }
}
finally {
    Pop-Location
}
