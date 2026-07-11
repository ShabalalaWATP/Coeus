param(
    [switch]$Detached
)

$ErrorActionPreference = "Stop"

$composeArgs = @("compose", "up", "--build")
if ($Detached) {
    $composeArgs += "-d"
}

& docker @composeArgs
