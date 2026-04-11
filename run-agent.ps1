param(
    [string]$Prompt = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment not found. Run .\bootstrap.ps1 first."
}

if ($Prompt) {
    & $venvPython -m local_gemma_agent --prompt $Prompt
} else {
    & $venvPython -m local_gemma_agent
}
