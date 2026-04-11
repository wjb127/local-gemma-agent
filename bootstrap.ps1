Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$defaultModel = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "gemma3:4b" }

Write-Host "[1/4] Creating virtual environment if needed..."
if (-not (Test-Path $venvPython)) {
    python -m venv (Join-Path $projectRoot ".venv")
}

Write-Host "[2/4] Upgrading pip..."
& $venvPython -m pip install --upgrade pip

Write-Host "[3/4] Installing the local package..."
& $venvPython -m pip install -e $projectRoot

Write-Host "[4/4] Checking Ollama..."
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Warning "Ollama is not installed yet."
    Write-Host "Install it with: winget install --id Ollama.Ollama -e"
    Write-Host "Then run: ollama pull $defaultModel"
    exit 0
}

Write-Host "Pulling model $defaultModel ..."
& ollama pull $defaultModel

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Run the agent with:"
Write-Host "  .\run-agent.ps1"
