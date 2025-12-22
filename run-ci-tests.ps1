# Local CI Test Script
# Simulates GitHub Actions CI workflow

param(
    [switch]$Lint,
    [switch]$Test,
    [switch]$Validate,
    [switch]$Security,
    [switch]$All,
    [switch]$Fast
)

$ErrorActionPreference = "Continue"
$FailedSteps = @()

Write-Host "Smartly Bridge CI Tests" -ForegroundColor Cyan
Write-Host ("=" * 60)

# Check Python version
function Check-Python {
    Write-Host "`nChecking Python environment..." -ForegroundColor Yellow
    $pythonVersion = python --version 2>&1
    Write-Host "  $pythonVersion" -ForegroundColor Gray
    
    if (-not $?) {
        Write-Host "ERROR: Python not found" -ForegroundColor Red
        exit 1
    }
}

# Install dependencies
function Install-Dependencies {
    Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
    python -m pip install --upgrade pip --quiet
    pip install -r requirements-dev.txt --quiet
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK: Dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        $script:FailedSteps += "Dependencies"
    }
}

# Lint tests
function Run-Lint {
    Write-Host "`n" -NoNewline
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "Code Quality Checks (Lint)" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
    
    # Black - Code formatting
    Write-Host "`n1. Black (Code Formatting)" -ForegroundColor Yellow
    python -m black --check custom_components/ tests/
    if ($LASTEXITCODE -ne 0) {
        $script:FailedSteps += "Black"
        Write-Host "  Hint: Run 'python -m black custom_components/ tests/' to auto-fix" -ForegroundColor Gray
    } else {
        Write-Host "  OK: Black check passed" -ForegroundColor Green
    }
    
    # isort - Import sorting
    Write-Host "`n2. isort (Import Sorting)" -ForegroundColor Yellow
    python -m isort --check-only custom_components/ tests/
    if ($LASTEXITCODE -ne 0) {
        $script:FailedSteps += "isort"
        Write-Host "  Hint: Run 'python -m isort custom_components/ tests/' to auto-fix" -ForegroundColor Gray
    } else {
        Write-Host "  OK: isort check passed" -ForegroundColor Green
    }
    
    # Flake8 - Code linting
    Write-Host "`n3. Flake8 (Code Linting)" -ForegroundColor Yellow
    python -m flake8 custom_components/ tests/ --max-line-length=100 --extend-ignore=E203,W503
    if ($LASTEXITCODE -ne 0) {
        $script:FailedSteps += "Flake8"
    } else {
        Write-Host "  OK: Flake8 check passed" -ForegroundColor Green
    }
    
    # MyPy - Type checking
    Write-Host "`n4. MyPy (Type Checking)" -ForegroundColor Yellow
    python -m mypy custom_components/ --ignore-missing-imports --no-strict-optional
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: MyPy found issues (non-blocking)" -ForegroundColor DarkYellow
    } else {
        Write-Host "  OK: MyPy check passed" -ForegroundColor Green
    }
}

# Unit tests
function Run-Tests {
    Write-Host "`n" -NoNewline
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "Unit Tests" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
    
    if ($Fast) {
        Write-Host "`nFast mode - No coverage report" -ForegroundColor Yellow
        python -m pytest tests/ -v
    } else {
        Write-Host "`nFull mode - With coverage report" -ForegroundColor Yellow
        python -m pytest tests/ `
            --cov=custom_components/smartly_bridge `
            --cov-report=xml `
            --cov-report=term-missing `
            --cov-report=html `
            --junitxml=test-results.xml `
            -v
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "`nCoverage reports generated:" -ForegroundColor Green
            Write-Host "  - coverage.xml (for Codecov)" -ForegroundColor Gray
            Write-Host "  - htmlcov/index.html (browser view)" -ForegroundColor Gray
            Write-Host "  - test-results.xml (test results)" -ForegroundColor Gray
        }
    }
    
    if ($LASTEXITCODE -ne 0) {
        $script:FailedSteps += "Tests"
    } else {
        Write-Host "`nOK: All tests passed" -ForegroundColor Green
    }
}

# Validate integration
function Run-Validate {
    Write-Host "`n" -NoNewline
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "Validate Home Assistant Integration" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
    
    # Validate manifest.json
    Write-Host "`n1. Validate manifest.json" -ForegroundColor Yellow
    $validateScript = @'
import json
import sys

required_fields = ["domain", "name", "version", "documentation", "codeowners", "integration_type"]

with open("custom_components/smartly_bridge/manifest.json") as f:
    manifest = json.load(f)

missing = [f for f in required_fields if f not in manifest]
if missing:
    print(f"ERROR: Missing fields: {missing}")
    sys.exit(1)

print("OK: manifest.json is valid")
'@
    
    $validateScript | python
    
    if ($LASTEXITCODE -ne 0) { $script:FailedSteps += "Manifest" }
    
    # Check translation files
    Write-Host "`n2. Check translation files" -ForegroundColor Yellow
    $stringsExist = Test-Path "custom_components/smartly_bridge/strings.json"
    $enExist = Test-Path "custom_components/smartly_bridge/translations/en.json"
    
    if ($stringsExist -and $enExist) {
        Write-Host "  OK: Translation files exist" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Translation files missing" -ForegroundColor Red
        $script:FailedSteps += "Translations"
    }
    
    # Validate all JSON files
    Write-Host "`n3. Validate JSON file formats" -ForegroundColor Yellow
    $jsonFiles = Get-ChildItem -Path custom_components/smartly_bridge -Filter *.json -Recurse
    $allValid = $true
    
    foreach ($file in $jsonFiles) {
        try {
            Get-Content $file.FullName | ConvertFrom-Json | Out-Null
        } catch {
            Write-Host "  ERROR: $($file.Name) invalid format" -ForegroundColor Red
            $allValid = $false
        }
    }
    
    if ($allValid) {
        Write-Host "  OK: All JSON files are valid" -ForegroundColor Green
    } else {
        $script:FailedSteps += "JSON Validation"
    }
}

# Security scan
function Run-Security {
    Write-Host "`n" -NoNewline
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "Security Scan" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
    
    # Install security tools
    Write-Host "`nInstalling security tools..." -ForegroundColor Yellow
    pip install bandit safety --quiet
    
    # Bandit - Security check
    Write-Host "`n1. Bandit (Security Check)" -ForegroundColor Yellow
    bandit -r custom_components/ -ll
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: Bandit found potential issues" -ForegroundColor DarkYellow
    } else {
        Write-Host "  OK: Bandit check passed" -ForegroundColor Green
    }
    
    # Safety - Dependency security check
    Write-Host "`n2. Safety (Dependency Security)" -ForegroundColor Yellow
    safety check --json
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: Safety found known vulnerabilities" -ForegroundColor DarkYellow
    } else {
        Write-Host "  OK: Safety check passed" -ForegroundColor Green
    }
}

# Show test summary
function Show-Summary {
    Write-Host "`n" -NoNewline
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "Test Results Summary" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
    
    if ($script:FailedSteps.Count -eq 0) {
        Write-Host "`nSUCCESS: All checks passed!" -ForegroundColor Green
        Write-Host "  Safe to push to GitHub" -ForegroundColor Gray
        return 0
    } else {
        Write-Host "`nFAILED: The following checks failed:" -ForegroundColor Red
        foreach ($step in $script:FailedSteps) {
            Write-Host "  - $step" -ForegroundColor Red
        }
        Write-Host "`nPlease fix the issues and run tests again" -ForegroundColor Yellow
        return 1
    }
}

# Main execution
Check-Python

# Determine which tests to run
$runAll = $All -or (-not ($Lint -or $Test -or $Validate -or $Security))

if ($runAll -or $Lint -or $Test) {
    Install-Dependencies
}

if ($runAll -or $Lint) {
    Run-Lint
}

if ($runAll -or $Test) {
    Run-Tests
}

if ($runAll -or $Validate) {
    Run-Validate
}

if ($runAll -or $Security) {
    Run-Security
}

# Show summary and set exit code
$exitCode = Show-Summary
exit $exitCode
