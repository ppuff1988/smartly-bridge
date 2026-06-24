"""Tests for the hexagonal application layer."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from custom_components.smartly_bridge.application.control import ControlCommand, ControlUseCase
from custom_components.smartly_bridge.application.sync import (
    SyncStatesUseCase,
    SyncStructureUseCase,
)
from custom_components.smartly_bridge.domain.models import EntityStateSnapshot


class FakeEntityPolicy:
    """Fake entity/service policy port."""

    def __init__(self, *, entity_allowed: bool = True, service_allowed: bool = True) -> None:
        self.entity_allowed = entity_allowed
        self.service_allowed = service_allowed

    def is_entity_allowed(self, entity_id: str) -> bool:
        return self.entity_allowed

    def is_service_allowed(self, entity_id: str, action: str) -> bool:
        return self.service_allowed


class FakeControlGateway:
    """Fake control port."""

    def __init__(
        self,
        state: EntityStateSnapshot | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.state = state
        self.exc = exc
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def call_service(
        self, entity_id: str, action: str, service_data: dict[str, Any]
    ) -> EntityStateSnapshot | None:
        if self.exc:
            raise self.exc
        self.calls.append((entity_id, action, service_data))
        return self.state


class FakeAudit:
    """Fake audit port."""

    def __init__(self) -> None:
        self.denials: list[tuple[str, str, str, str, dict[str, Any] | None]] = []
        self.controls: list[tuple[str, str, str, str, dict[str, Any] | None]] = []

    def deny(
        self,
        client_id: str,
        entity_id: str,
        service: str,
        reason: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        self.denials.append((client_id, entity_id, service, reason, actor))

    def control(
        self,
        client_id: str,
        entity_id: str,
        service: str,
        result: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        self.controls.append((client_id, entity_id, service, result, actor))


class FakeSyncGateway:
    """Fake sync port."""

    def __init__(self) -> None:
        self.structure = {
            "floors": [],
            "areas": [],
            "devices": [],
            "entities": [{"entity_id": "light.kitchen"}],
        }
        self.states = [
            EntityStateSnapshot(
                entity_id="light.kitchen",
                state="on",
                attributes={"brightness": 128},
                last_changed="2026-06-24T00:00:00+00:00",
                last_updated="2026-06-24T00:00:00+00:00",
                icon="mdi:lightbulb",
            )
        ]

    def get_structure(self) -> dict[str, Any]:
        return self.structure

    def list_states(self) -> list[EntityStateSnapshot]:
        return self.states


@pytest.mark.asyncio
async def test_control_use_case_denies_entity_before_service_call() -> None:
    """Disallowed entities are denied by the use case without touching HA services."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    use_case = ControlUseCase(FakeEntityPolicy(entity_allowed=False), gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.private", "turn_on", {}, {"user_id": "support-1"}),
    )

    assert result.status == 403
    assert result.body == {"error": "entity_not_allowed"}
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "light.private",
            "turn_on",
            "entity_not_allowed",
            {"user_id": "support-1"},
        )
    ]


@pytest.mark.asyncio
async def test_control_use_case_calls_allowed_service_and_returns_new_state() -> None:
    """Allowed commands go through the control port and return the resulting state."""
    audit = FakeAudit()
    state = EntityStateSnapshot(
        entity_id="light.kitchen",
        state="on",
        attributes={"brightness": 255},
        last_changed=None,
        last_updated=None,
        icon=None,
    )
    gateway = FakeControlGateway(state)
    use_case = ControlUseCase(FakeEntityPolicy(), gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "turn_on", {"brightness": 255}, {"role": "admin"}),
    )

    assert result.status == 200
    assert result.body == {
        "success": True,
        "entity_id": "light.kitchen",
        "action": "turn_on",
        "new_state": "on",
        "new_attributes": {"brightness": 255},
    }
    assert gateway.calls == [("light.kitchen", "turn_on", {"brightness": 255})]
    assert audit.controls == [
        ("client-1", "light.kitchen", "turn_on", "success", {"role": "admin"})
    ]


def test_sync_structure_use_case_returns_gateway_structure() -> None:
    """Structure sync uses a sync port instead of reading Home Assistant directly."""
    gateway = FakeSyncGateway()
    result = SyncStructureUseCase(gateway).execute()

    assert result.status == 200
    assert result.body == gateway.structure


def test_sync_states_use_case_returns_states_with_count() -> None:
    """State sync serializes state snapshots returned by the port."""
    result = SyncStatesUseCase(FakeSyncGateway()).execute()

    assert result.status == 200
    assert result.body == {
        "states": [
            {
                "entity_id": "light.kitchen",
                "state": "on",
                "attributes": {"brightness": 128},
                "last_changed": "2026-06-24T00:00:00+00:00",
                "last_updated": "2026-06-24T00:00:00+00:00",
                "icon": "mdi:lightbulb",
            }
        ],
        "count": 1,
    }


def test_inner_layers_do_not_import_framework_adapters() -> None:
    """Domain and application code must not import HTTP or Home Assistant frameworks."""
    package_root = Path(__file__).resolve().parents[1] / "custom_components/smartly_bridge"
    inner_dirs = [package_root / "domain", package_root / "application"]
    forbidden_roots = {"aiohttp", "homeassistant"}

    for directory in inner_dirs:
        assert directory.exists(), f"Missing inner layer directory: {directory}"
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                imported: list[str] = []
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = [node.module]

                assert not forbidden_roots.intersection(
                    name.split(".")[0] for name in imported
                ), f"{path} imports framework code: {imported}"


def test_package_init_does_not_import_outer_adapters_at_module_load() -> None:
    """Importing inner layers must not require HTTP/Home Assistant dependencies."""
    package_root = Path(__file__).resolve().parents[1] / "custom_components/smartly_bridge"
    path = package_root / "__init__.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    forbidden_relative_imports = {"auth", "camera", "http", "push", "webrtc"}

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue
        assert node.module not in forbidden_relative_imports, (
            f"{path} imports adapter module at package load: {node.module}"
        )


def test_webrtc_views_do_not_lookup_sessions_directly() -> None:
    """WebRTC views should delegate session lookup to the application use cases."""
    package_root = Path(__file__).resolve().parents[1] / "custom_components/smartly_bridge"
    path = package_root / "views/webrtc.py"

    assert "get_session_by_partial_token(" not in path.read_text()
