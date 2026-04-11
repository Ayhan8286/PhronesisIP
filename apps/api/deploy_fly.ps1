param()

Set-Location -Path $PSScriptRoot
Write-Host "Deploying PatentIQ backend to Fly.io..."

if (-not (Get-Command fly -ErrorAction SilentlyContinue)) {
  Write-Error "The fly CLI is not installed. Install it from https://fly.io/docs/hands-on/installing/"
  exit 1
}

fly deploy
Write-Host "Deployment complete."
