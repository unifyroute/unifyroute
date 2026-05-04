<#
.SYNOPSIS
  UnifyRoute — One-command install for Windows (PowerShell)
.DESCRIPTION
  Installs UnifyRoute on Windows — checks prerequisites, clones the repo,
  runs setup, and starts the app.
.USAGE
  irm https://raw.githubusercontent.com/unifyroute/UnifyRoute/main/scripts/install.ps1 | iex

  Or if already cloned:
  .\scripts\install.ps1

.PARAMETER InstallDir
  Where to install UnifyRoute (default: $env:USERPROFILE\UnifyRoute)
.PARAMETER Branch
  Git branch to clone (default: main)
.PARAMETER Port
  App port (default: 6565)
.PARAMETER Host
  App host (default: localhost)
.PARAMETER MasterPassword
  Master password (default: auto-generated)
.PARAMETER Skip
  Comma-separated: prereqs,clone,setup,build,start
#>

param(
  [string]$InstallDir = "$env:USERPROFILE\UnifyRoute",
  [string]$Branch = "main",
  [string]$Port = "6565",
  [string]$Host = "localhost",
  [string]$MasterPassword = "",
  [string]$Skip = ""
)

$Repo = "https://github.com/unifyroute/UnifyRoute.git"

# ── Helpers ───────────────────────────────────────────────────────────────────
function Write-Info  { Write-Host "ℹ  $args" -ForegroundColor Cyan }
function Write-Ok    { Write-Host "✅ $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "⚠  $args" -ForegroundColor Yellow }
function Write-Err   { Write-Host "❌ $args" -ForegroundColor Red }
function Write-Banner{ Write-Host "`n━━━ $args ━━━" -ForegroundColor White }
function Test-Command($cmd) { Get-Command $cmd -ErrorAction SilentlyContinue }

function Skip-Step($name) {
  if (-not $Skip) { return $false }
  return ($Skip -split ',').Trim() -contains $name
}

# ── Header ─────────────────────────────────────────────────────────────────────
Clear-Host
Write-Host @"

  _    _       _  __  _____ _____   ____  _   _ _______
 | |  | |     | | \ \/ /_   _|  __ \|  _ \| | | |__   __|
 | |  | |_ __ | |  \  /  | | | |__) | |_) | | | |  | |
 | |  | | '_ \| |  /  \  | | |  _  /|  _ <| | | |  | |
 | |__| | | | | | / /\ \_| |_| | \ \| |_) | |_| |  | |
  \____/|_| |_|_|/_/  \_\___|_|  \_\____/ \___/   |_|

"@ -ForegroundColor Cyan
Write-Host "                           One-command install" -ForegroundColor Cyan
Write-Host ""

# ── Check: running in PowerShell ──────────────────────────────────────────────
if ($Host.Name -notlike "*PowerShell*" -and $Host.Name -notlike "*pwsh*") {
  Write-Err "This script needs PowerShell 5.1+ or PowerShell 7+"
  Write-Info "Install: winget install Microsoft.PowerShell"
  exit 1
}

# ── Prerequisites ─────────────────────────────────────────────────────────────
Write-Banner "Prerequisites"

# Python
$pythonPath = ""
if (Test-Command python3) {
  $pythonPath = "python3"
} elseif (Test-Command python) {
  $pythonPath = "python"
}

if ($pythonPath) {
  $pyVer = & $pythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
  $pyMajorMinor = if ($pyVer) { [version]"$($pyVer.Split('.')[0]).$($pyVer.Split('.')[1])" } else { [version]"0.0" }
  if ($pyMajorMinor -ge [version]"3.11") {
    Write-Ok "Python $pyVer"
  } else {
    Write-Warn "Python $pyVer is too old. Installing Python 3.12..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements 2>$null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $pythonPath = "python"
    Write-Ok "Python installed: $(& $pythonPath --version 2>&1)"
  }
} else {
  Write-Info "Installing Python 3.12..."
  winget install -e --id Python.Python.3.12 --accept-package-agreements 2>$null
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  $pythonPath = "python"
  Write-Ok "Python installed: $(& $pythonPath --version 2>&1)"
}

# uv
if (Test-Command uv) {
  Write-Ok "uv $(& uv --version 2>&1)"
} else {
  Write-Info "Installing uv..."
  & $pythonPath -m pip install uv -q 2>$null
  if (-not (Test-Command uv)) {
    $env:Path += ";$env:USERPROFILE\.local\bin;$env:APPDATA\Python\Scripts"
    if (-not (Test-Command uv)) {
      Write-Warn "uv not in PATH after install. Trying pip in user scope..."
      & $pythonPath -m pip install --user uv -q 2>$null
    }
  }
  if (Test-Command uv) {
    Write-Ok "uv installed: $(& uv --version 2>&1)"
  } else {
    Write-Warn "Could not install uv automatically. Continuing with pip as fallback."
  }
}

# Node.js
if (Test-Command node) {
  Write-Ok "Node.js $(& node --version 2>&1)"
} else {
  Write-Info "Installing Node.js..."
  winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements 2>$null
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

if (Test-Command npm) {
  Write-Ok "npm $(& npm --version 2>&1)"
} else {
  Write-Warn "npm not found — GUI build will be skipped"
}

# Git
if (Test-Command git) {
  Write-Ok "Git $(& git --version 2>&1)"
} else {
  Write-Info "Installing Git..."
  winget install -e --id Git.Git --accept-package-agreements 2>$null
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  Write-Ok "Git installed"
}

# ── Clone repo ─────────────────────────────────────────────────────────────────
Write-Banner "Getting UnifyRoute"

if (Test-Path "unifyroute" -PathType Leaf -and (Test-Path "scripts/setup.py")) {
  $CloneDir = (Get-Location).Path
  Write-Info "Already inside UnifyRoute repo: $CloneDir"
} elseif (Test-Path "$InstallDir\unifyroute" -PathType Leaf) {
  $CloneDir = $InstallDir
  Write-Info "Found existing install at $CloneDir"
} else {
  Write-Info "Cloning UnifyRoute into $InstallDir ..."
  if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force "$InstallDir\*" -ErrorAction SilentlyContinue
  }
  git clone --depth=1 --branch $Branch $Repo $InstallDir 2>$null
  if ($LASTEXITCODE -ne 0) {
    git clone --depth=1 $Repo $InstallDir
  }
  $CloneDir = $InstallDir
  Write-Ok "Cloned to $CloneDir"
}

Set-Location $CloneDir

# ── Setup ──────────────────────────────────────────────────────────────────────
Write-Banner "UnifyRoute Setup"

if (-not (Skip-Step "setup")) {

if (-not $MasterPassword) {
  try {
    $bytes = New-Object byte[] 16
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $MasterPassword = [Convert]::ToBase64String($bytes) -replace '[+/=]', '-'
  } catch {
    $MasterPassword = "unifyroute-$([DateTime]::Now.Ticks)"
  }
}

Write-Info "Running setup (this will take a few minutes)..."
$setupInput = @(
  "data/unifyroute.db",
  "$Port",
  "$Host",
  "http://${Host}:${Port}",
  $MasterPassword,
  $MasterPassword
) -join "`n"

$setupResult = $setupInput | & $pythonPath scripts/setup.py install 2>&1 | Out-String
Write-Host $setupResult

}

# ── Show admin token ───────────────────────────────────────────────────────────
Write-Banner "Admin Token"

$adminToken = ""
if (Test-Path ".admin_token") {
  $adminToken = Get-Content ".admin_token" -Raw -ErrorAction SilentlyContinue
} elseif (Test-Path ".api_token") {
  $adminToken = Get-Content ".api_token" -Raw -ErrorAction SilentlyContinue
}

if ($adminToken) {
  Write-Host "`n  ADMIN API TOKEN: " -NoNewline
  Write-Host "$adminToken" -ForegroundColor Cyan
  Write-Host "  Save this now — it will not be shown again.`n"
}

# ── Start ──────────────────────────────────────────────────────────────────────
if (-not (Skip-Step "start")) {
  Write-Banner "Starting UnifyRoute"
  Write-Info "Starting server on http://${Host}:${Port} ..."

  # Start the process
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = "cmd.exe"
  $psi.Arguments = "/c .\unifyroute.bat start"
  $psi.WorkingDirectory = $CloneDir
  $psi.UseShellExecute = $true
  $psi.CreateNoWindow = $true
  [System.Diagnostics.Process]::Start($psi) | Out-Null

  Start-Sleep 3

  # Health check
  $healthy = $false
  for ($i=1; $i -le 20; $i++) {
    try {
      $r = Invoke-WebRequest -Uri "http://${Host}:${Port}/api/health" -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -eq 200) {
        $healthy = $true
        break
      }
    } catch { Start-Sleep 1 }
  }
  if ($healthy) {
    Write-Ok "UnifyRoute is running!"
  } else {
    Write-Warn "Server did not respond within 20s. Check logs: $CloneDir\logs"
  }
}

# ── Done ───────────────────────────────────────────────────────────────────────
Write-Banner "Install Complete!"
Write-Host @"

  Dashboard:     http://$($Host):$Port
  API:           http://$($Host):$Port/api
  Install dir:   $CloneDir
  Run again:     cd $CloneDir && .\unifyroute.bat start

  Login with master password you set during setup.

"@
Write-Info "Thank you for installing UnifyRoute! 🚦"
