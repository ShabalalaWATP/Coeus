param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("LocalProcesses", "FullDocker")]
    [string]$Mode,
    [switch]$ConfirmReset
)

$ErrorActionPreference = "Stop"

if (-not $ConfirmReset) {
    throw "This deletes the local PostgreSQL and object data together. Re-run with -ConfirmReset."
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$localData = [System.IO.Path]::GetFullPath((Join-Path $projectRoot ".local-data"))
$expectedPrefix = $projectRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
    [System.IO.Path]::DirectorySeparatorChar
if (-not $localData.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to reset a path outside the repository."
}

function Test-LocalPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync("127.0.0.1", $Port)
        return $connect.Wait(250) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

Push-Location $projectRoot
$quarantinedLocalData = $null
$postgresRemoved = $false
try {
    if (Test-LocalPort -Port 8001) {
        throw "The local-process API is still listening on port 8001. Stop it before resetting."
    }
    if ($Mode -eq "FullDocker") {
        & docker compose down --volumes --remove-orphans
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Compose could not remove the full-stack data volumes."
        }
    }
    else {
        if (Test-Path -LiteralPath $localData) {
            $quarantinedLocalData = "$localData.reset-$([guid]::NewGuid().ToString('N'))"
            Move-Item -LiteralPath $localData -Destination $quarantinedLocalData
        }
        & docker compose down --remove-orphans
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Compose could not stop the local infrastructure."
        }
        & docker volume inspect coeus_coeus-postgres *> $null
        if ($LASTEXITCODE -eq 0) {
            & docker volume rm coeus_coeus-postgres
            if ($LASTEXITCODE -ne 0) {
                throw "Docker could not remove the local PostgreSQL volume."
            }
        }
        $postgresRemoved = $true
    }
    if ($null -ne $quarantinedLocalData -and (Test-Path -LiteralPath $quarantinedLocalData)) {
        Remove-Item -LiteralPath $quarantinedLocalData -Recurse -Force
    }
}
catch {
    if (
        $null -ne $quarantinedLocalData -and
        -not $postgresRemoved -and
        (Test-Path -LiteralPath $quarantinedLocalData) -and
        -not (Test-Path -LiteralPath $localData)
    ) {
        Move-Item -LiteralPath $quarantinedLocalData -Destination $localData
    }
    throw
}
finally {
    Pop-Location
}

Write-Host "Local $Mode state was reset. PostgreSQL metadata and object bytes were removed together."
