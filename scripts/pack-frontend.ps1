param(
  [string]$ReleaseTag = "",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ReleaseTag)) {
  $ReleaseTag = Get-Date -Format "yyyyMMdd_HHmmss"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"
$distDir = Join-Path $frontendDir "dist"
$artifactDir = Join-Path $repoRoot "release-artifacts"
$artifactName = "sqtoimage-frontend-$ReleaseTag.zip"
$artifactPath = Join-Path $artifactDir $artifactName
$shaPath = "$artifactPath.sha256"

if (!(Test-Path $frontendDir)) {
  throw "frontend directory not found: $frontendDir"
}

if (!(Get-Command node -ErrorAction SilentlyContinue)) {
  throw "node not found in PATH. Please reopen PowerShell and run again."
}

if (!(Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm not found in PATH. Please reopen PowerShell and run again."
}

Push-Location $frontendDir
try {
  if (-not $SkipInstall) {
    if (Test-Path "package-lock.json") {
      npm ci
    } else {
      npm install
    }
  }

  npm run build
}
finally {
  Pop-Location
}

New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null

if (Test-Path $artifactPath) {
  Remove-Item -Force $artifactPath
}
if (Test-Path $shaPath) {
  Remove-Item -Force $shaPath
}

Compress-Archive -Path (Join-Path $distDir "*") -DestinationPath $artifactPath -CompressionLevel Optimal
$hash = (Get-FileHash -Path $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path $shaPath -Value "$hash  $artifactName" -Encoding UTF8

Write-Host ""
Write-Host "Frontend package created:"
Write-Host "  $artifactPath"
Write-Host "SHA256:"
Write-Host "  $shaPath"
Write-Host ""
Write-Host "Upload and extract on server, then switch Nginx root/symlink to new dist."
