"""HTTP API endpoints for Smartly Bridge integration.

This module now delegates to the views package for better organization.
All views are organized by functional domain:
- control.py: Device control API
- sync.py: Structure and state synchronization
- camera.py: IP camera snapshot and streaming

For backward compatibility, register_views() is re-exported from views package.
"""

from __future__ import annotations

# Import register_views from views package for backward compatibility
from .views import register_views

__all__ = ["register_views"]
