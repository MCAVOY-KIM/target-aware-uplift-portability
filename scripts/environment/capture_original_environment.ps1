$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptRoot)
$ProjectRoot = Split-Path -Parent $RepoRoot

# If this script is copied into the original project repository structure,
# edit this path only if needed.
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Out = Join-Path $RepoRoot "environment"

if (-not (Test-Path $Python)) {
    throw "Project virtual-environment Python not found: $Python"
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

& $Python --version 2>&1 | Out-File -Encoding utf8 (Join-Path $Out "python_version.txt")
& $Python -m pip freeze | Out-File -Encoding utf8 (Join-Path $Out "pip_freeze.txt")
& $Python -m pip --version | Out-File -Encoding utf8 (Join-Path $Out "pip_version.txt")

Write-Host "Captured environment metadata under $Out"
