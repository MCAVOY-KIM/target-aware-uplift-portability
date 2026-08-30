$ErrorActionPreference = "Stop"

$P1CRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $P1CRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Code = Join-Path $P1CRoot "03_src\p1c_rare_binary_simulation.py"
$Out = Join-Path $P1CRoot "05_outputs\p1c_full_gate"

if (-not (Test-Path $Python)) { throw "Parent project .venv was not found: $Python" }
if (-not (Test-Path $Code)) { throw "P1-C code was not found: $Code" }

New-Item -ItemType Directory -Force -Path $Out | Out-Null

& $Python $Code `
  --mode full `
  --outdir $Out `
  --reps 500 `
  --stress-reps 300 `
  --workers 4 `
  --bootstrap-draws 1500 `
  --epsilon 0.005 `
  --seed-base 202608272
