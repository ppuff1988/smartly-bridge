# CI/CD Configuration Summary

This document provides an overview of the CI/CD pipeline configuration for Smartly Bridge.

## Workflows Overview

### 1. **CI Workflow** (`.github/workflows/ci.yml`)
Runs on every push and pull request to `main` and `develop` branches.

**Jobs:**
- **Lint**: Code formatting (Black, isort), linting (Flake8), type checking (MyPy)
- **Test**: Run pytest on Python 3.11, 3.12, 3.13 with coverage reporting
- **Validate**: Check manifest.json, translations, and JSON files
- **Security**: Bandit security scanning, dependency vulnerability checks
- **Build**: Create release packages (tar.gz and zip)
- **Quality Gate**: Final check that all jobs passed

### 2. **Release Workflow** (`.github/workflows/release.yml`)
Triggers on version tags (v*.*.*) or manual dispatch.

**Jobs:**
- Validate version format and consistency
- Run full test suite
- Create GitHub release with changelog
- Upload release artifacts
- Notify HACS (if applicable)

### 3. **Code Quality** (`.github/workflows/code-quality.yml`)
Runs on pull requests and pushes.

**Jobs:**
- Code complexity analysis (Radon)
- Pylint checks
- Coverage validation (minimum 80%)
- Documentation checks
- Translation completeness

### 4. **PR Checks** (`.github/workflows/pr-checks.yml`)
Runs on pull request events.

**Jobs:**
- Validate PR title (semantic commits)
- Check for CHANGELOG updates
- Detect large files
- Path-based conditional testing
- Auto-label PR size

### 5. **Auto Format** (`.github/workflows/auto-format.yml`)
Automatically formats code on pull requests.

**Jobs:**
- Remove unused imports (autoflake)
- Sort imports (isort)
- Format code (Black)
- Auto-commit changes

### 6. **Dependency Updates** (`.github/workflows/dependency-update.yml`)
Weekly automated dependency checks.

**Jobs:**
- Check for outdated packages
- Create PR with updates
- Security audit (pip-audit, safety)

## Configuration Files

### **pyproject.toml**
Central configuration for:
- Black formatting
- pytest options
- Coverage settings
- MyPy type checking
- isort import sorting

### **.flake8**
Linting configuration:
- Max line length: 100
- Max complexity: 10
- Black compatibility settings

### **.isort.cfg**
Import sorting configuration:
- Black profile
- Custom section ordering

### **dependabot.yml**
Automated dependency updates:
- GitHub Actions weekly updates
- Python packages weekly updates
- Grouped minor/patch updates

## Quality Standards

### Code Coverage
- Minimum: 80%
- Reported to Codecov
- HTML reports available as artifacts

### Code Complexity
- Maximum cyclomatic complexity: 10
- Monitored with Radon
- Reported on PRs

### Security
- Bandit security linting
- Dependency vulnerability scanning
- Weekly security audits

### Documentation
- All public functions require docstrings
- README.md required
- Translation completeness checks

## Secrets Required

Configure these in GitHub Settings → Secrets:

- `CODECOV_TOKEN` (optional): For coverage reporting
- `GITHUB_TOKEN`: Auto-provided by GitHub Actions

## Branch Protection Rules

Recommended settings for `main` branch:

```yaml
Require pull request reviews: 1
Require status checks to pass:
  - lint
  - test (Python 3.12)
  - validate
  - quality-gate
Require branches to be up to date: true
Do not allow bypassing the above settings: true
```

## Release Process

1. Update version in `custom_components/smartly_bridge/manifest.json`
2. Update `CHANGELOG.md` with changes
3. Commit: `git commit -m "chore: bump version to 1.0.1"`
4. Create and push tag:
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```
5. GitHub Actions will automatically:
   - Run full test suite
   - Create GitHub release
   - Upload artifacts
   - Generate changelog

## Local Development

### Setup
```bash
# Install dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks (optional)
pre-commit install
```

### Run Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=custom_components/smartly_bridge

# Specific file
pytest tests/test_auth.py -v
```

### Format Code
```bash
# Format with Black
black custom_components/ tests/

# Sort imports
isort custom_components/ tests/

# Check linting
flake8 custom_components/ tests/

# Type checking
mypy custom_components/
```

### Run All Checks
```bash
# One command to rule them all
black custom_components/ tests/ && \
isort custom_components/ tests/ && \
flake8 custom_components/ tests/ && \
mypy custom_components/ && \
pytest --cov=custom_components/smartly_bridge
```

## Troubleshooting

### Tests Failing
- Check Python version matches CI (3.11+)
- Ensure all dependencies installed
- Clear pytest cache: `pytest --cache-clear`

### Formatting Issues
- Run Black and isort locally
- Check `.flake8` and `.isort.cfg` settings
- Auto-format will run on PR

### Coverage Too Low
- Add tests for uncovered code
- Check `htmlcov/index.html` for report
- Exclude files if needed in `pyproject.toml`

### Type Errors
- Add type hints to functions
- Use `# type: ignore` for external libs
- Check MyPy documentation

## Performance Optimization

- **Caching**: pip cache enabled on all workflows
- **Parallel Jobs**: Tests run in matrix for multiple Python versions
- **Conditional Execution**: Only run affected tests on PR changes
- **Artifact Retention**: Limited to 7-30 days

## Monitoring

- Check Actions tab for workflow runs
- Review failed jobs for errors
- Monitor Codecov for coverage trends
- Review Dependabot PRs weekly

## Future Enhancements

- [ ] Add integration tests with Home Assistant
- [ ] Implement E2E testing
- [ ] Add performance benchmarking
- [ ] Set up Sonarcloud integration
- [ ] Add semantic release automation
- [ ] Implement canary deployments
- [ ] Add visual regression testing
