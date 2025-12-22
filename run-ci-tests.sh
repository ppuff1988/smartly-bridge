#!/bin/bash
# Local CI Test Script
# Simulates GitHub Actions CI workflow

set +e  # Continue on errors

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
DARK_YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Variables
FAILED_STEPS=()
RUN_LINT=false
RUN_TEST=false
RUN_VALIDATE=false
RUN_SECURITY=false
RUN_ALL=false
FAST_MODE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --lint|-l)
            RUN_LINT=true
            shift
            ;;
        --test|-t)
            RUN_TEST=true
            shift
            ;;
        --validate|-v)
            RUN_VALIDATE=true
            shift
            ;;
        --security|-s)
            RUN_SECURITY=true
            shift
            ;;
        --all|-a)
            RUN_ALL=true
            shift
            ;;
        --fast|-f)
            FAST_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --lint, -l       Run linting checks"
            echo "  --test, -t       Run unit tests"
            echo "  --validate, -v   Run validation checks"
            echo "  --security, -s   Run security scans"
            echo "  --all, -a        Run all checks (default)"
            echo "  --fast, -f       Fast mode (no coverage)"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}Smartly Bridge CI Tests${NC}"
echo "============================================================"

# Check Python version
check_python() {
    echo -e "\n${YELLOW}Checking Python environment...${NC}"
    local python_version=$(python --version 2>&1)
    echo -e "  ${GRAY}$python_version${NC}"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Python not found${NC}"
        exit 1
    fi
}

# Install dependencies
install_dependencies() {
    echo -e "\n${YELLOW}Installing dependencies...${NC}"
    python -m pip install --upgrade pip --quiet
    pip install -r requirements-dev.txt --quiet
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}OK: Dependencies installed${NC}"
    else
        echo -e "${RED}ERROR: Failed to install dependencies${NC}"
        FAILED_STEPS+=("Dependencies")
    fi
}

# Lint tests
run_lint() {
    echo -e "\n============================================================"
    echo -e "${CYAN}Code Quality Checks (Lint)${NC}"
    echo -e "============================================================"
    
    # Black - Code formatting
    echo -e "\n${YELLOW}1. Black (Code Formatting)${NC}"
    python -m black --check custom_components/ tests/
    if [ $? -ne 0 ]; then
        FAILED_STEPS+=("Black")
        echo -e "  ${GRAY}Hint: Run 'python -m black custom_components/ tests/' to auto-fix${NC}"
    else
        echo -e "  ${GREEN}OK: Black check passed${NC}"
    fi
    
    # isort - Import sorting
    echo -e "\n${YELLOW}2. isort (Import Sorting)${NC}"
    python -m isort --check-only custom_components/ tests/
    if [ $? -ne 0 ]; then
        FAILED_STEPS+=("isort")
        echo -e "  ${GRAY}Hint: Run 'python -m isort custom_components/ tests/' to auto-fix${NC}"
    else
        echo -e "  ${GREEN}OK: isort check passed${NC}"
    fi
    
    # Flake8 - Code linting
    echo -e "\n${YELLOW}3. Flake8 (Code Linting)${NC}"
    python -m flake8 custom_components/ tests/ --max-line-length=100 --extend-ignore=E203,W503
    if [ $? -ne 0 ]; then
        FAILED_STEPS+=("Flake8")
    else
        echo -e "  ${GREEN}OK: Flake8 check passed${NC}"
    fi
    
    # MyPy - Type checking
    echo -e "\n${YELLOW}4. MyPy (Type Checking)${NC}"
    python -m mypy custom_components/ --ignore-missing-imports --no-strict-optional
    if [ $? -ne 0 ]; then
        echo -e "  ${DARK_YELLOW}WARNING: MyPy found issues (non-blocking)${NC}"
    else
        echo -e "  ${GREEN}OK: MyPy check passed${NC}"
    fi
}

# Unit tests
run_tests() {
    echo -e "\n============================================================"
    echo -e "${CYAN}Unit Tests${NC}"
    echo -e "============================================================"
    
    if [ "$FAST_MODE" = true ]; then
        echo -e "\n${YELLOW}Fast mode - No coverage report${NC}"
        python -m pytest tests/ -v
    else
        echo -e "\n${YELLOW}Full mode - With coverage report${NC}"
        python -m pytest tests/ \
            --cov=custom_components/smartly_bridge \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-report=html \
            --junitxml=test-results.xml \
            -v
        
        if [ $? -eq 0 ]; then
            echo -e "\n${GREEN}Coverage reports generated:${NC}"
            echo -e "  ${GRAY}- coverage.xml (for Codecov)${NC}"
            echo -e "  ${GRAY}- htmlcov/index.html (browser view)${NC}"
            echo -e "  ${GRAY}- test-results.xml (test results)${NC}"
        fi
    fi
    
    if [ $? -ne 0 ]; then
        FAILED_STEPS+=("Tests")
    else
        echo -e "\n${GREEN}OK: All tests passed${NC}"
    fi
}

# Validate integration
run_validate() {
    echo -e "\n============================================================"
    echo -e "${CYAN}Validate Home Assistant Integration${NC}"
    echo -e "============================================================"
    
    # Validate manifest.json
    echo -e "\n${YELLOW}1. Validate manifest.json${NC}"
    python << 'EOF'
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
EOF
    
    if [ $? -ne 0 ]; then
        FAILED_STEPS+=("Manifest")
    fi
    
    # Check translation files
    echo -e "\n${YELLOW}2. Check translation files${NC}"
    if [ -f "custom_components/smartly_bridge/strings.json" ] && \
       [ -f "custom_components/smartly_bridge/translations/en.json" ]; then
        echo -e "  ${GREEN}OK: Translation files exist${NC}"
    else
        echo -e "  ${RED}ERROR: Translation files missing${NC}"
        FAILED_STEPS+=("Translations")
    fi
    
    # Validate all JSON files
    echo -e "\n${YELLOW}3. Validate JSON file formats${NC}"
    local all_valid=true
    
    while IFS= read -r -d '' file; do
        if ! python -m json.tool "$file" > /dev/null 2>&1; then
            echo -e "  ${RED}ERROR: $(basename "$file") invalid format${NC}"
            all_valid=false
        fi
    done < <(find custom_components/smartly_bridge -name "*.json" -print0)
    
    if [ "$all_valid" = true ]; then
        echo -e "  ${GREEN}OK: All JSON files are valid${NC}"
    else
        FAILED_STEPS+=("JSON Validation")
    fi
}

# Security scan
run_security() {
    echo -e "\n============================================================"
    echo -e "${CYAN}Security Scan${NC}"
    echo -e "============================================================"
    
    # Install security tools
    echo -e "\n${YELLOW}Installing security tools...${NC}"
    pip install bandit safety --quiet
    
    # Bandit - Security check
    echo -e "\n${YELLOW}1. Bandit (Security Check)${NC}"
    bandit -r custom_components/ -ll
    if [ $? -ne 0 ]; then
        echo -e "  ${DARK_YELLOW}WARNING: Bandit found potential issues${NC}"
    else
        echo -e "  ${GREEN}OK: Bandit check passed${NC}"
    fi
    
    # Safety - Dependency security check
    echo -e "\n${YELLOW}2. Safety (Dependency Security)${NC}"
    safety check --json
    if [ $? -ne 0 ]; then
        echo -e "  ${DARK_YELLOW}WARNING: Safety found known vulnerabilities${NC}"
    else
        echo -e "  ${GREEN}OK: Safety check passed${NC}"
    fi
}

# Show test summary
show_summary() {
    echo -e "\n============================================================"
    echo -e "${CYAN}Test Results Summary${NC}"
    echo -e "============================================================"
    
    if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
        echo -e "\n${GREEN}SUCCESS: All checks passed!${NC}"
        echo -e "  ${GRAY}Safe to push to GitHub${NC}"
        return 0
    else
        echo -e "\n${RED}FAILED: The following checks failed:${NC}"
        for step in "${FAILED_STEPS[@]}"; do
            echo -e "  ${RED}- $step${NC}"
        done
        echo -e "\n${YELLOW}Please fix the issues and run tests again${NC}"
        return 1
    fi
}

# Main execution
check_python

# Determine which tests to run
if [ "$RUN_ALL" = false ] && \
   [ "$RUN_LINT" = false ] && \
   [ "$RUN_TEST" = false ] && \
   [ "$RUN_VALIDATE" = false ] && \
   [ "$RUN_SECURITY" = false ]; then
    RUN_ALL=true
fi

if [ "$RUN_ALL" = true ] || [ "$RUN_LINT" = true ] || [ "$RUN_TEST" = true ]; then
    install_dependencies
fi

if [ "$RUN_ALL" = true ] || [ "$RUN_LINT" = true ]; then
    run_lint
fi

if [ "$RUN_ALL" = true ] || [ "$RUN_TEST" = true ]; then
    run_tests
fi

if [ "$RUN_ALL" = true ] || [ "$RUN_VALIDATE" = true ]; then
    run_validate
fi

if [ "$RUN_ALL" = true ] || [ "$RUN_SECURITY" = true ]; then
    run_security
fi

# Show summary and set exit code
show_summary
exit $?
