"""Framework-independent domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils import build_bridge_chart


@dataclass(frozen=True)
class BridgeResponse:
    """Application response returned to HTTP adapters."""

    body: dict[str, Any]
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SmartlyCapability:
    """Canonical capability exposed by the new Smartly device abstraction."""

    type: str
    role: str = "primary"
    readable: bool = True
    writable: bool = True
    event_only: bool = False
    state: dict[str, Any] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    presentation: dict[str, Any] = field(default_factory=dict)
    source_refs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize as the API vNext capability contract."""
        return {
            "type": self.type,
            "role": self.role,
            "readable": self.readable,
            "writable": self.writable,
            "event_only": self.event_only,
            "state": self.state,
            "commands": self.commands,
            "events": self.events,
            "constraints": self.constraints,
            "presentation": self.presentation,
            "source_refs": self.source_refs,
        }


@dataclass(frozen=True)
class SmartlyLogicalDevice:
    """Logical device shadow payload used during capability-based migration."""

    id: str
    name: str
    primary_type: str
    device_class: str
    status: str | None
    source_entities: list[str]
    capabilities: list[SmartlyCapability]
    presentation: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "2026.06"

    def to_dict(self) -> dict[str, Any]:
        """Serialize as the logical-device contract."""
        return {
            "id": self.id,
            "name": self.name,
            "primary_type": self.primary_type,
            "device_class": self.device_class,
            "status": self.status,
            "source_entities": self.source_entities,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
            "presentation": self.presentation,
            "schema_version": self.schema_version,
        }


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
    bridge_chart: dict[str, Any] | None = None

    def to_sync_dict(self) -> dict[str, Any]:
        """Serialize for the sync states API."""
        attributes = dict(self.attributes or {})
        payload = {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": attributes,
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
        sensor_device_class = attributes.get("device_class")
        unit = attributes.get("unit_of_measurement")

        chart = self.bridge_chart or build_bridge_chart(
            self.state,
            self.last_updated,
            sensor_device_class,
            unit,
        )
        if chart is not None:
            attributes["bridge_chart"] = chart

        return payload


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
