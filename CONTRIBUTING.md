# Contributing to Smartly Bridge

Thank you for your interest in contributing to Smartly Bridge! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/platform-bridge.git
   cd platform-bridge
   ```

2. **Set up development environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

3. **Configure pre-commit hooks** (optional but recommended)
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**
   - Write clear, documented code
   - Follow the existing code style
   - Add tests for new functionality

3. **Run tests locally**
   ```bash
   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=custom_components/smartly_bridge

   # Run specific test file
   pytest tests/test_auth.py
   ```

4. **Format and lint your code**
   ```bash
   # Auto-format code
   black custom_components/ tests/
   isort custom_components/ tests/

   # Check linting
   flake8 custom_components/ tests/
   mypy custom_components/
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New features
   - `fix:` - Bug fixes
   - `docs:` - Documentation changes
   - `style:` - Code style changes (formatting, etc.)
   - `refactor:` - Code refactoring
   - `test:` - Adding or updating tests
   - `chore:` - Maintenance tasks

6. **Push and create a Pull Request**
   ```bash
   git push origin feat/your-feature-name
   ```

## Code Style Guidelines

- **Python Version**: Support Python 3.11+
- **Line Length**: Max 100 characters
- **Formatting**: Use Black and isort
- **Type Hints**: Add type hints to all functions
- **Docstrings**: Use Google-style docstrings

### Example Code

```python
"""Module docstring."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def example_function(
    hass: HomeAssistant,
    entity_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Example function with proper formatting.

    Args:
        hass: Home Assistant instance.
        entity_id: The entity ID to process.
        **kwargs: Additional keyword arguments.

    Returns:
        Dictionary containing the result.

    Raises:
        ValueError: If entity_id is invalid.
    """
    if not entity_id:
        raise ValueError("entity_id cannot be empty")

    result = {"entity_id": entity_id, **kwargs}
    _LOGGER.debug("Processed entity: %s", entity_id)

    return result
```

## Testing Guidelines

- Write unit tests for all new functions
- Use pytest fixtures for common setup
- Mock external dependencies
- Aim for >80% code coverage

### Example Test

```python
"""Test example module."""
import pytest
from unittest.mock import Mock, patch


@pytest.mark.asyncio
async def test_example_function():
    """Test example function."""
    hass = Mock()
    entity_id = "light.living_room"

    result = await example_function(hass, entity_id, state="on")

    assert result["entity_id"] == entity_id
    assert result["state"] == "on"
```

## Pull Request Process

1. **Ensure CI passes** - All tests and checks must pass
2. **Update documentation** - Update README.md if needed
3. **Update CHANGELOG** - Add entry under [Unreleased]
4. **Request review** - Tag maintainers for review
5. **Address feedback** - Make requested changes
6. **Squash commits** - Keep PR history clean (optional)

## PR Checklist

- [ ] Tests added/updated and passing
- [ ] Code formatted with Black and isort
- [ ] Type hints added
- [ ] Docstrings added/updated
- [ ] CHANGELOG.md updated
- [ ] No breaking changes (or clearly documented)
- [ ] Translations updated if UI changes

## Reporting Bugs

Use GitHub Issues with the bug template:

1. **Description** - Clear description of the bug
2. **Steps to Reproduce** - Detailed steps
3. **Expected Behavior** - What should happen
4. **Actual Behavior** - What actually happens
5. **Environment** - Home Assistant version, Python version
6. **Logs** - Relevant log entries

## Feature Requests

Use GitHub Issues with the feature template:

1. **Problem Statement** - What problem does this solve?
2. **Proposed Solution** - How should it work?
3. **Alternatives** - Other solutions considered
4. **Additional Context** - Screenshots, examples, etc.

## Code Review Guidelines

As a reviewer:
- Be constructive and respectful
- Explain reasoning for requested changes
- Approve if changes look good
- Request changes if issues found

As an author:
- Respond to all comments
- Ask questions if unclear
- Make requested changes promptly

## Release Process

1. Update version in `manifest.json`
2. Update CHANGELOG.md
3. Create git tag: `git tag v1.0.0`
4. Push tag: `git push origin v1.0.0`
5. GitHub Actions will create the release

## Getting Help

- **Documentation**: Check README.md first
- **Issues**: Search existing issues
- **Discussions**: Use GitHub Discussions for questions
- **Discord/Slack**: Join community channels

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
