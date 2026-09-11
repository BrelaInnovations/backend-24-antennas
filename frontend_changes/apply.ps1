$ErrorActionPreference = 'Stop'
$frontendTarget = [System.IO.Path]::GetFullPath('C:/Users/prasr/Downloads/naibra-app/naibra-app')
$preparedRoot = Join-Path $PSScriptRoot 'files'
$fileManifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
# Verify every original before applying any updates, to preserve concurrent work.
foreach ($entry in $fileManifest) {
    $destination = [System.IO.Path]::GetFullPath((Join-Path $frontendTarget $entry.path))
    if (-not $destination.StartsWith($frontendTarget + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path outside frontend: $destination"
    }
    $actual = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $entry.sha256) { throw "File changed since preparation: $destination" }
}
foreach ($entry in $fileManifest) {
    $destination = Join-Path $frontendTarget $entry.path
    Copy-Item -LiteralPath (Join-Path $preparedRoot $entry.path) -Destination $destination
    $expected = (Get-FileHash -LiteralPath (Join-Path $preparedRoot $entry.path) -Algorithm SHA256).Hash
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $expected) {
        throw "Copy verification failed: $destination"
    }
}
Write-Output "Applied and verified $($fileManifest.Count) frontend files."
