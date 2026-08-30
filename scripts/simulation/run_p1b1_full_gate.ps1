$ErrorActionPreference = "Stop"
$B1Root = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $B1Root
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Code = Join-Path $B1Root "03_src\p1_portability_simulation_b1.py"
$Out = Join-Path $B1Root "05_outputs\p1b1_full_gate"
if (-not (Test-Path $Python)) { throw "Parent project .venv not found: $Python" }
New-Item -ItemType Directory -Force -Path $Out | Out-Null
& $Python $Code --mode full --outdir $Out --reps 1000 --stress-reps 500 --workers 4 --bootstrap-draws 2000 --epsilon 0.005 --seed-base 202608271
