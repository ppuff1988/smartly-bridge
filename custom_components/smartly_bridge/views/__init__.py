"""HTTP API views for Smartly Bridge integration."""

from __future__ import annotations

from .camera import (
    SmartlyCameraConfigViewWrapper,
    SmartlyCameraHLSInfoViewWrapper,
    SmartlyCameraListViewWrapper,
    SmartlyCameraSnapshotViewWrapper,
    SmartlyCameraStreamViewWrapper,
)
from .control import SmartlyControlViewWrapper
from .sync import SmartlySyncStatesViewWrapper, SmartlySyncViewWrapper

__all__ = [
    "SmartlyControlViewWrapper",
    "SmartlySyncViewWrapper",
    "SmartlySyncStatesViewWrapper",
    "SmartlyCameraSnapshotViewWrapper",
    "SmartlyCameraStreamViewWrapper",
    "SmartlyCameraListViewWrapper",
    "SmartlyCameraConfigViewWrapper",
    "SmartlyCameraHLSInfoViewWrapper",
]


def register_views(hass) -> None:
    """Register all HTTP views."""
    hass.http.register_view(SmartlyControlViewWrapper)
    hass.http.register_view(SmartlySyncViewWrapper)
    hass.http.register_view(SmartlySyncStatesViewWrapper)
    # Camera views
    hass.http.register_view(SmartlyCameraSnapshotViewWrapper)
    hass.http.register_view(SmartlyCameraStreamViewWrapper)
    hass.http.register_view(SmartlyCameraListViewWrapper)
    hass.http.register_view(SmartlyCameraConfigViewWrapper)
    # HLS streaming views
    hass.http.register_view(SmartlyCameraHLSInfoViewWrapper)
