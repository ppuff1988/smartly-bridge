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
from .history import (
    SmartlyHistoryBatchViewWrapper,
    SmartlyHistoryViewWrapper,
    SmartlyStatisticsViewWrapper,
)
from .sync import SmartlySyncStatesViewWrapper, SmartlySyncViewWrapper
from .webrtc import (
    SmartlyWebRTCHangupViewWrapper,
    SmartlyWebRTCICEViewWrapper,
    SmartlyWebRTCOfferViewWrapper,
    SmartlyWebRTCTokenViewWrapper,
)

__all__ = [
    "SmartlyControlViewWrapper",
    "SmartlySyncViewWrapper",
    "SmartlySyncStatesViewWrapper",
    "SmartlyCameraSnapshotViewWrapper",
    "SmartlyCameraStreamViewWrapper",
    "SmartlyCameraListViewWrapper",
    "SmartlyCameraConfigViewWrapper",
    "SmartlyCameraHLSInfoViewWrapper",
    "SmartlyHistoryViewWrapper",
    "SmartlyHistoryBatchViewWrapper",
    "SmartlyStatisticsViewWrapper",
    "SmartlyWebRTCTokenViewWrapper",
    "SmartlyWebRTCOfferViewWrapper",
    "SmartlyWebRTCICEViewWrapper",
    "SmartlyWebRTCHangupViewWrapper",
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
    # WebRTC streaming views
    hass.http.register_view(SmartlyWebRTCTokenViewWrapper)
    hass.http.register_view(SmartlyWebRTCOfferViewWrapper)
    hass.http.register_view(SmartlyWebRTCICEViewWrapper)
    hass.http.register_view(SmartlyWebRTCHangupViewWrapper)
    # History views
    hass.http.register_view(SmartlyHistoryViewWrapper)
    hass.http.register_view(SmartlyHistoryBatchViewWrapper)
    hass.http.register_view(SmartlyStatisticsViewWrapper)
