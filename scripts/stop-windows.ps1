$ErrorActionPreference = "Stop"

$ContainerName = "pm-mvp"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "Docker is required but not installed."
}

try { docker stop $ContainerName | Out-Null } catch {}
try { docker rm $ContainerName | Out-Null } catch {}

Write-Host "Container stopped and removed: $ContainerName"
