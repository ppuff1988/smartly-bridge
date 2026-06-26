"""Framework-independent domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BridgeResponse:
    """Application response returned to HTTP adapters."""

    body: dict[str, Any]
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityStateSnapshot:
    """Serializable entity state snapshot."""

    entity_id: str
    state: str | None
    attributes: dict[str, Any] | None
    last_changed: str | None = None
    last_updated: str | None = None
    icon: str | None = None
    name: str | None = None
    domain: str | None = None
    device_class: str | None = None
    capabilities: list[str] = field(default_factory=list)
    status: str | None = None
    presentation: dict[str, Any] = field(default_factory=dict)

    def to_sync_dict(self) -> dict[str, Any]:
        """Serialize for the sync states API."""
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self.attributes,
            "last_changed": self.last_changed,
            "last_updated": self.last_updated,
            "icon": self.icon,
            "name": self.name,
            "domain": self.domain,
            "device_class": self.device_class,
            "capabilities": self.capabilities,
            "status": self.status,
            "presentation": self.presentation,
        }


@dataclass(frozen=True)
class CameraSnapshot:
    """Camera snapshot payload returned by the camera port."""

    entity_id: str
    image_data: bytes
    content_type: str
    timestamp: float
    etag: str


@dataclass(frozen=True)
class CameraStreamInfo:
    """Camera streaming capability information."""

    entity_id: str
    name: str
    supports_snapshot: bool = False
    supports_mjpeg: bool = False
    supports_hls: bool = False
    supports_webrtc: bool = False
    is_streaming: bool = False

    def capabilities_dict(self) -> dict[str, bool]:
        """Return capability flags for API responses."""
        return {
            "snapshot": self.supports_snapshot,
            "mjpeg": self.supports_mjpeg,
            "hls": self.supports_hls,
            "webrtc": self.supports_webrtc,
        }

    def endpoints_dict(self) -> dict[str, str | None]:
        """Return endpoint paths for supported stream capabilities."""
        return {
            "snapshot": f"/api/smartly/camera/{self.entity_id}/snapshot",
            "mjpeg": f"/api/smartly/camera/{self.entity_id}/stream",
            "hls": (
                f"/api/smartly/camera/{self.entity_id}/stream/hls" if self.supports_hls else None
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize stream information."""
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "capabilities": self.capabilities_dict(),
            "endpoints": self.endpoints_dict(),
            "is_streaming": self.is_streaming,
        }
