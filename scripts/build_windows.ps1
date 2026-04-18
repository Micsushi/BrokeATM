param(
  [string[]]$Python,
  [switch]$Installer,
  [switch]$Clean = $true,
  [string]$IsccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"

if (-not $Python) {
  $candidates = @(
    @("py", "-3.13"),
    @("py", "-3.12"),
    @("py", "-3.11"),
    @("py"),
    @("python")
  )
  foreach ($candidate in $candidates) {
    $cmd     = $candidate[0]
    $cmdArgs = if ($candidate.Length -gt 1) { $candidate[1..($candidate.Length - 1)] } else { @() }
    $ver     = & $cmd @cmdArgs --version 2>$null
    if ($LASTEXITCODE -eq 0 -and $ver) {
      $Python = $candidate
      Write-Host "Detected Python: $ver (using: $($Python -join ' '))"
      break
    }
  }
  if (-not $Python) {
    throw "Python 3.11+ not found. Install from https://www.python.org/ and ensure 'py' or 'python' is on PATH."
  }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonCmd = $Python[0]
$pythonArgs = @()
if ($Python.Length -gt 1) {
  $pythonArgs = $Python[1..($Python.Length - 1)]
}

Push-Location $repoRoot

try {
  & $pythonCmd @pythonArgs -m pip install -e ".[build]"

  $pyInstallerArgs = @("-m", "PyInstaller", "brokeatm.spec", "--noconfirm")
  if ($Clean) {
    $pyInstallerArgs += "--clean"
  }

  & $pythonCmd @pythonArgs @pyInstallerArgs

  if ($Installer) {
    if (-not (Test-Path $IsccPath)) {
      throw "Inno Setup compiler not found at '$IsccPath'. Install Inno Setup 6 or pass -IsccPath."
    }

    & $IsccPath "packaging/windows/BrokeATM.iss"
  }
}
finally {
  Pop-Location
}
