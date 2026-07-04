param(
    [switch]$Detached
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

$composeArgs = @("compose", "up", "--build")
if ($Detached) {
    $composeArgs += "-d"
}

& docker @composeArgs

