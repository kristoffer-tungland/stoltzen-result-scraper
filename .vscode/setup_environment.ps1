param(
    [Parameter(Mandatory = $true)]
    [string]$BootstrapPython,

    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$venvDirectory = Join-Path $WorkspaceRoot ".venv"
$venvPython = Join-Path $venvDirectory "Scripts\python.exe"
$requirements = Join-Path $WorkspaceRoot "src\requirements.txt"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Oppretter prosjektmiljø i .venv ..."
    & $BootstrapPython -m venv $venvDirectory
    if ($LASTEXITCODE -ne 0) {
        throw "Kunne ikke opprette .venv med valgt Python-tolk."
    }
}

Write-Host "Kontrollerer Python-avhengigheter ..."
& $venvPython -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) {
    throw "Kunne ikke installere Python-avhengighetene."
}
