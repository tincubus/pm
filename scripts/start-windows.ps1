$ErrorActionPreference = "Stop"

$ImageName = "pm-mvp"
$ContainerName = "pm-mvp"
$Port = if ($env:PORT) { $env:PORT } else { "8000" }

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RootDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "Docker is required but not installed."
}

try { docker rm -f $ContainerName | Out-Null } catch {}

docker build -t $ImageName .

$EnvArgs = @()
if (Test-Path ".env") {
  $EnvArgs += @("--env-file", ".env")
}

docker run -d --name $ContainerName -p "${Port}:8000" @EnvArgs $ImageName

Write-Host "Container started: $ContainerName"
Write-Host "Open http://localhost:$Port"
