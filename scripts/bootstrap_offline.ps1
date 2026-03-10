[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [string]$Wheelhouse = "wheelhouse",
    [string]$ConfigPath = "assets/config.example.yaml",
    [switch]$SkipBrowserInstall,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $false)][string[]]$Arguments = @(),
        [string]$FriendlyName = $null
    )

    $label = if ($FriendlyName) { $FriendlyName } else { "$FilePath $($Arguments -join ' ')" }
    Write-Host "+ $label" -ForegroundColor DarkGray

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $label (exit code $LASTEXITCODE)"
    }
}

function Resolve-PythonVersion {
    param([string]$Py)

    $ver = & $Py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Cannot execute Python: $Py"
    }

    $ver = $ver.Trim()
    $parts = $ver.Split('.')
    if ($parts.Length -lt 2) {
        throw "Cannot parse Python version: $ver"
    }

    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    return @{ Version = $ver; Major = $major; Minor = $minor }
}

try {
    Write-Step "Validate Python version (>= 3.11)"
    $pyInfo = Resolve-PythonVersion -Py $PythonExe
    Write-Host "Detected Python: $($pyInfo.Version)" -ForegroundColor Green
    if ($pyInfo.Major -lt 3 -or ($pyInfo.Major -eq 3 -and $pyInfo.Minor -lt 11)) {
        throw "Python 3.11+ is required, found $($pyInfo.Version)."
    }

    Write-Step "Install dependencies from wheelhouse"
    if (-not (Test-Path $Wheelhouse)) {
        throw "Wheelhouse path not found: $Wheelhouse"
    }
    Invoke-Checked -FilePath $PythonExe -Arguments @("scripts/install_deps.py", "--wheelhouse", $Wheelhouse) -FriendlyName "Install deps from wheelhouse"

    if (-not $SkipBrowserInstall) {
        Write-Step "Install or validate Playwright Chromium"
        $msPath = Join-Path (Get-Location) "ms-playwright"
        if (Test-Path $msPath) {
            Write-Host "Found local Playwright cache: $msPath" -ForegroundColor Green
        } else {
            Write-Host "No local ./ms-playwright cache found. Will run playwright install chromium." -ForegroundColor Yellow
        }
        Invoke-Checked -FilePath $PythonExe -Arguments @("-m", "playwright", "install", "chromium") -FriendlyName "Playwright chromium install/check"
    } else {
        Write-Step "Skip browser install/check (requested)"
    }

    Write-Step "Run doctor checks"
    Invoke-Checked -FilePath $PythonExe -Arguments @("-m", "tool.main", "doctor", "-c", $ConfigPath) -FriendlyName "Tool doctor"

    if (-not $SkipBuild) {
        Write-Step "Build executable via PyInstaller"
        Invoke-Checked -FilePath $PythonExe -Arguments @("-m", "PyInstaller", "tool/flow_tool.spec", "--noconfirm") -FriendlyName "PyInstaller build"
        Write-Host "Build completed: dist/flow-tool.exe" -ForegroundColor Green
    } else {
        Write-Step "Skip build (requested)"
    }

    Write-Host "`nBootstrap offline completed successfully." -ForegroundColor Green
    exit 0
}
catch {
    Write-Host "`n[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Hint: verify wheelhouse completeness and Python 3.11+ runtime." -ForegroundColor Yellow
    exit 1
}
