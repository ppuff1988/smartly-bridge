"""Tests for the hexagonal application layer."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from custom_components.smartly_bridge.application.control import (
    ControlCommand,
    ControlUseCase,
    SmartlyCommand,
    SmartlyCommandUseCase,
)
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
        self.service_checks: list[tuple[str, str]] = []

    def is_entity_allowed(self, entity_id: str) -> bool:
        return self.entity_allowed

    def is_service_allowed(self, entity_id: str, action: str) -> bool:
        self.service_checks.append((entity_id, action))
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


class FakeCommandTargetResolver:
    """Fake Smartly command target resolver."""

    def __init__(self, mapping: dict[tuple[str, str], str | None]) -> None:
        self.mapping = mapping
        self.lookups: list[tuple[str, str]] = []

    def resolve_command_target(self, device_id: str, capability: str) -> str | None:
        self.lookups.append((device_id, capability))
        return self.mapping.get((device_id, capability))


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
                name="Kitchen Light",
                domain="light",
                device_class="smart_light",
                capabilities=["on_off", "brightness"],
                status="online",
                presentation={"card_template": "light_card"},
            )
        ]

    def get_structure(self) -> dict[str, Any]:
        return self.structure

    async def list_states(self) -> list[EntityStateSnapshot]:
        return self.states


class FakeDiagnosticSyncGateway:
    """Fake sync port with an unsupported entity."""

    async def list_states(self) -> list[EntityStateSnapshot]:
        return [
            EntityStateSnapshot(
                entity_id="camera.porch",
                state="idle",
                attributes={"friendly_name": "Porch Camera"},
                name="Porch Camera",
                domain="camera",
                device_class="unknown_device",
                capabilities=[],
                status="online",
                presentation={"card_template": "unknown_card"},
            )
        ]


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


@pytest.mark.asyncio
async def test_control_use_case_maps_light_brightness_alias_to_turn_on() -> None:
    """Light brightness commands map to Home Assistant turn_on service data."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"brightness": 150},
        )
    )
    policy = FakeEntityPolicy()
    use_case = ControlUseCase(policy, gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "set_brightness", {"brightness": 150}),
    )

    assert result.status == 200
    assert gateway.calls == [("light.kitchen", "turn_on", {"brightness": 150})]
    assert policy.service_checks == [("light.kitchen", "turn_on")]
    assert result.body["action"] == "set_brightness"


@pytest.mark.asyncio
async def test_control_use_case_maps_canonical_brightness_value_to_pct() -> None:
    """Canonical brightness commands use Smartly 0-100 value contract."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"brightness": 204},
        )
    )
    policy = FakeEntityPolicy()
    use_case = ControlUseCase(policy, gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "set_brightness", {"value": 80}),
    )

    assert result.status == 200
    assert gateway.calls == [("light.kitchen", "turn_on", {"brightness_pct": 80})]
    assert policy.service_checks == [("light.kitchen", "turn_on")]


@pytest.mark.asyncio
async def test_control_use_case_maps_light_color_alias_to_turn_on() -> None:
    """Light color commands map color aliases to rgb_color service data."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"rgb_color": [255, 120, 40]},
        )
    )
    use_case = ControlUseCase(FakeEntityPolicy(), gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "set_color", {"color": [255, 120, 40]}),
    )

    assert result.status == 200
    assert gateway.calls == [("light.kitchen", "turn_on", {"rgb_color": [255, 120, 40]})]


@pytest.mark.asyncio
async def test_control_use_case_maps_canonical_rgb_channels_to_turn_on() -> None:
    """Canonical RGB commands map named channels to rgb_color service data."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"rgb_color": [255, 120, 40]},
        )
    )
    policy = FakeEntityPolicy()
    use_case = ControlUseCase(policy, gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "set_rgb_color", {"r": 255, "g": 120, "b": 40}),
    )

    assert result.status == 200
    assert gateway.calls == [("light.kitchen", "turn_on", {"rgb_color": [255, 120, 40]})]
    assert policy.service_checks == [("light.kitchen", "turn_on")]


@pytest.mark.asyncio
async def test_control_use_case_maps_light_color_temp_alias_to_turn_on() -> None:
    """Light color temperature commands map to turn_on service data."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"color_temp": 370},
        )
    )
    use_case = ControlUseCase(FakeEntityPolicy(), gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "set_color_temp", {"color_temperature": 370}),
    )

    assert result.status == 200
    assert gateway.calls == [("light.kitchen", "turn_on", {"color_temp": 370})]


@pytest.mark.asyncio
async def test_control_use_case_maps_canonical_color_temperature_value_to_kelvin() -> None:
    """Canonical color temperature commands use Smartly kelvin value contract."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"color_temp": 250},
        )
    )
    policy = FakeEntityPolicy()
    use_case = ControlUseCase(policy, gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "set_color_temperature", {"value": 4000}),
    )

    assert result.status == 200
    assert gateway.calls == [("light.kitchen", "turn_on", {"color_temp_kelvin": 4000})]
    assert policy.service_checks == [("light.kitchen", "turn_on")]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_canonical_brightness_command() -> None:
    """SmartlyCommand resolves logical devices before invoking source control."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"brightness": 204},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "brightness"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-1",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="set_brightness",
            params={"value": 80},
            source={"user_id": "user-1"},
        ),
    )

    assert result.status == 200
    assert result.body == {
        "success": True,
        "command_id": "cmd-1",
        "status": "completed",
        "device_id": "ldev_light_kitchen",
        "capability": "brightness",
        "command": "set_brightness",
        "entity_id": "light.kitchen",
        "expected_state": {"brightness": {"value": 80, "unit": "percent"}},
        "new_state": "on",
        "new_attributes": {"brightness": 204},
    }
    assert resolver.lookups == [("ldev_light_kitchen", "brightness")]
    assert gateway.calls == [("light.kitchen", "turn_on", {"brightness_pct": 80})]
    assert audit.controls == [
        (
            "client-1",
            "light.kitchen",
            "set_brightness",
            "success",
            {
                "user_id": "user-1",
                "command_id": "cmd-1",
                "logical_device_id": "ldev_light_kitchen",
                "capability": "brightness",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_returns_power_expected_state() -> None:
    """Power commands expose expected capability state for correlation."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="switch.fan",
            state="on",
            attributes={},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_switch_fan", "power"): "switch.fan"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-power",
            device_id="ldev_switch_fan",
            capability="power",
            command="turn_on",
            params={},
        ),
    )

    assert result.status == 200
    assert result.body["expected_state"] == {"power": {"value": True}}
    assert gateway.calls == [("switch.fan", "turn_on", {})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_returns_color_temperature_expected_state() -> None:
    """Color temperature commands expose expected kelvin state for correlation."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"color_temp": 250},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_light_kitchen", "color_temperature"): "light.kitchen"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-color-temp",
            device_id="ldev_light_kitchen",
            capability="color_temperature",
            command="set_color_temperature",
            params={"value": 4000},
        ),
    )

    assert result.status == 200
    assert result.body["expected_state"] == {
        "color_temperature": {"value": 4000, "unit": "kelvin"}
    }
    assert gateway.calls == [("light.kitchen", "turn_on", {"color_temp_kelvin": 4000})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_returns_rgb_color_expected_state() -> None:
    """RGB color commands expose expected channel state for correlation."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"rgb_color": [255, 120, 40]},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "rgb_color"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-rgb",
            device_id="ldev_light_kitchen",
            capability="rgb_color",
            command="set_rgb_color",
            params={"r": 255, "g": 120, "b": 40},
        ),
    )

    assert result.status == 200
    assert result.body["expected_state"] == {
        "rgb_color": {"value": {"r": 255, "g": 120, "b": 40}}
    }
    assert gateway.calls == [("light.kitchen", "turn_on", {"rgb_color": [255, 120, 40]})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_cover_position_command() -> None:
    """Cover position commands map canonical position to Home Assistant services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="cover.living_curtain",
            state="open",
            attributes={"current_position": 55},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_cover_living_curtain", "position"): "cover.living_curtain"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-cover-position",
            device_id="ldev_cover_living_curtain",
            capability="position",
            command="set_position",
            params={"value": 55},
        ),
    )

    assert result.status == 200
    assert result.body["expected_state"] == {
        "position": {"value": 55, "unit": "percent"}
    }
    assert gateway.calls == [
        ("cover.living_curtain", "set_cover_position", {"position": 55})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_cover_open_command() -> None:
    """Cover open commands map canonical names to Home Assistant services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="cover.living_curtain",
            state="open",
            attributes={},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_cover_living_curtain", "position"): "cover.living_curtain"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-cover-open",
            device_id="ldev_cover_living_curtain",
            capability="position",
            command="open",
            params={},
        ),
    )

    assert result.status == 200
    assert result.body["expected_state"] == {"position": {"value": 100, "unit": "percent"}}
    assert gateway.calls == [("cover.living_curtain", "open_cover", {})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_fan_speed_command() -> None:
    """Fan speed commands map canonical percentage to Home Assistant services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="fan.bedroom",
            state="on",
            attributes={"percentage": 75},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_fan_bedroom", "fan_speed"): "fan.bedroom"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-fan-speed",
            device_id="ldev_fan_bedroom",
            capability="fan_speed",
            command="set_fan_speed",
            params={"percentage": 75},
        ),
    )

    assert result.status == 200
    assert result.body["expected_state"] == {
        "fan_speed": {"percentage": 75, "unit": "percent"}
    }
    assert gateway.calls == [("fan.bedroom", "set_percentage", {"percentage": 75})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_unresolved_target() -> None:
    """Canonical commands fail before source control when no source target exists."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-404",
            device_id="ldev_unknown",
            capability="power",
            command="turn_on",
            params={},
        ),
    )

    assert result.status == 404
    assert result.body == {
        "success": False,
        "command_id": "cmd-404",
        "status": "rejected",
        "error": "command_target_not_found",
        "device_id": "ldev_unknown",
        "capability": "power",
        "command": "turn_on",
        "entity_id": None,
        "expected_state": {},
    }
    assert resolver.lookups == [("ldev_unknown", "power")]
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "ldev_unknown",
            "turn_on",
            "command_target_not_found",
            {"command_id": "cmd-404", "capability": "power"},
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_unsupported_command() -> None:
    """Canonical commands fail before source control when unsupported by capability."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "brightness"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-unsupported",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="turn_on",
            params={},
        ),
    )

    assert result.status == 400
    assert result.body == {
        "success": False,
        "command_id": "cmd-unsupported",
        "status": "rejected",
        "error": "command_not_supported",
        "device_id": "ldev_light_kitchen",
        "capability": "brightness",
        "command": "turn_on",
        "entity_id": "light.kitchen",
        "expected_state": {},
    }
    assert resolver.lookups == [("ldev_light_kitchen", "brightness")]
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "ldev_light_kitchen",
            "turn_on",
            "command_not_supported",
            {"command_id": "cmd-unsupported", "capability": "brightness"},
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_brightness_params() -> None:
    """Canonical commands fail before source control when params violate schema."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "brightness"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="set_brightness",
            params={"value": 150},
        ),
    )

    assert result.status == 400
    assert result.body == {
        "success": False,
        "command_id": "cmd-invalid",
        "status": "rejected",
        "error": "invalid_params",
        "device_id": "ldev_light_kitchen",
        "capability": "brightness",
        "command": "set_brightness",
        "entity_id": "light.kitchen",
        "expected_state": {},
    }
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "ldev_light_kitchen",
            "set_brightness",
            "invalid_params",
            {"command_id": "cmd-invalid", "capability": "brightness"},
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_rgb_params() -> None:
    """RGB color commands require all channels to satisfy the channel range."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "rgb_color"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-rgb",
            device_id="ldev_light_kitchen",
            capability="rgb_color",
            command="set_rgb_color",
            params={"r": 255, "g": 120, "b": 300},
        ),
    )

    assert result.status == 400
    assert result.body["error"] == "invalid_params"
    assert result.body["entity_id"] == "light.kitchen"
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "ldev_light_kitchen",
            "set_rgb_color",
            "invalid_params",
            {"command_id": "cmd-invalid-rgb", "capability": "rgb_color"},
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_color_temperature_params() -> None:
    """Color temperature commands require a positive kelvin value."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {("ldev_light_kitchen", "color_temperature"): "light.kitchen"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-color-temp",
            device_id="ldev_light_kitchen",
            capability="color_temperature",
            command="set_color_temperature",
            params={"value": 0},
        ),
    )

    assert result.status == 400
    assert result.body["error"] == "invalid_params"
    assert result.body["entity_id"] == "light.kitchen"
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "ldev_light_kitchen",
            "set_color_temperature",
            "invalid_params",
            {"command_id": "cmd-invalid-color-temp", "capability": "color_temperature"},
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_position_params() -> None:
    """Position commands require a percentage value in range."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {("ldev_cover_living_curtain", "position"): "cover.living_curtain"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-position",
            device_id="ldev_cover_living_curtain",
            capability="position",
            command="set_position",
            params={"value": 120},
        ),
    )

    assert result.status == 400
    assert result.body["error"] == "invalid_params"
    assert result.body["entity_id"] == "cover.living_curtain"
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "ldev_cover_living_curtain",
            "set_position",
            "invalid_params",
            {"command_id": "cmd-invalid-position", "capability": "position"},
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_fan_speed_params() -> None:
    """Fan speed commands require a percentage value in range."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_fan_bedroom", "fan_speed"): "fan.bedroom"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-fan-speed",
            device_id="ldev_fan_bedroom",
            capability="fan_speed",
            command="set_fan_speed",
            params={"percentage": 125},
        ),
    )

    assert result.status == 400
    assert result.body["error"] == "invalid_params"
    assert result.body["entity_id"] == "fan.bedroom"
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "ldev_fan_bedroom",
            "set_fan_speed",
            "invalid_params",
            {"command_id": "cmd-invalid-fan-speed", "capability": "fan_speed"},
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_returns_rejected_service_error() -> None:
    """Denied source services use the canonical command error shape."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "power"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(
        FakeEntityPolicy(service_allowed=False),
        gateway,
        audit,
        resolver,
    )

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-denied",
            device_id="ldev_light_kitchen",
            capability="power",
            command="turn_on",
            params={},
        ),
    )

    assert result.status == 403
    assert result.body == {
        "success": False,
        "command_id": "cmd-denied",
        "status": "rejected",
        "error": "service_not_allowed",
        "device_id": "ldev_light_kitchen",
        "capability": "power",
        "command": "turn_on",
        "entity_id": "light.kitchen",
        "expected_state": {},
    }
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_smartly_command_use_case_returns_failed_source_error() -> None:
    """Source execution failures use the canonical command error shape."""
    audit = FakeAudit()
    gateway = FakeControlGateway(exc=RuntimeError("source unavailable"))
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "power"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-failed",
            device_id="ldev_light_kitchen",
            capability="power",
            command="turn_on",
            params={},
        ),
    )

    assert result.status == 500
    assert result.body == {
        "success": False,
        "command_id": "cmd-failed",
        "status": "failed",
        "error": "service_call_failed",
        "device_id": "ldev_light_kitchen",
        "capability": "power",
        "command": "turn_on",
        "entity_id": "light.kitchen",
        "expected_state": {},
    }


def test_sync_structure_use_case_returns_gateway_structure() -> None:
    """Structure sync uses a sync port instead of reading Home Assistant directly."""
    gateway = FakeSyncGateway()
    result = SyncStructureUseCase(gateway).execute()

    assert result.status == 200
    assert result.body == gateway.structure


@pytest.mark.asyncio
async def test_sync_states_use_case_returns_states_with_count() -> None:
    """State sync serializes state snapshots returned by the port."""
    result = await SyncStatesUseCase(FakeSyncGateway()).execute()

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
                "name": "Kitchen Light",
                "domain": "light",
                "device_class": "smart_light",
                "capabilities": ["on_off", "brightness"],
                "status": "online",
                "presentation": {"card_template": "light_card"},
            }
        ],
        "count": 1,
        "normalization_warnings": [],
        "logical_devices": [
            {
                "id": "ldev_light_kitchen",
                "name": "Kitchen Light",
                "primary_type": "light",
                "device_class": "light_control",
                "status": "online",
                "source_entities": ["light.kitchen"],
                "aliases": [
                    {
                        "kind": "home_assistant_entity_id",
                        "value": "light.kitchen",
                        "valid_from": None,
                        "valid_until": None,
                    }
                ],
                "capabilities": [
                    {
                        "type": "power",
                        "role": "primary",
                        "readable": True,
                        "writable": True,
                        "event_only": False,
                        "state": {"value": True},
                        "commands": ["turn_on", "turn_off", "toggle"],
                        "events": [],
                        "constraints": {},
                        "presentation": {},
                        "source_refs": [
                            {
                                "source": "home_assistant",
                                "source_device_id": None,
                                "source_entity_id": "light.kitchen",
                                "domain": "light",
                                "role": "primary_control",
                                "capability_types": ["power"],
                            }
                        ],
                    },
                    {
                        "type": "brightness",
                        "role": "primary",
                        "readable": True,
                        "writable": True,
                        "event_only": False,
                        "state": {"value": 50, "unit": "percent"},
                        "commands": ["set_brightness"],
                        "events": [],
                        "constraints": {"min": 0, "max": 100, "step": 1},
                        "presentation": {},
                        "source_refs": [
                            {
                                "source": "home_assistant",
                                "source_device_id": None,
                                "source_entity_id": "light.kitchen",
                                "domain": "light",
                                "role": "primary_control",
                                "capability_types": ["brightness"],
                            }
                        ],
                    },
                ],
                "presentation": {
                    "template": "light_control",
                    "primary_controls": ["power", "brightness"],
                    "status_badges": [],
                },
                "schema_version": "2026.06",
            }
        ],
    }


@pytest.mark.asyncio
async def test_sync_states_use_case_reports_diagnostic_normalization_warnings() -> None:
    """Unsupported entities remain visible and emit diagnostic normalization warnings."""
    result = await SyncStatesUseCase(FakeDiagnosticSyncGateway()).execute()

    assert result.status == 200
    assert result.body["logical_devices"][0]["device_class"] == "diagnostic_device"
    assert result.body["logical_devices"][0]["aliases"] == [
        {
            "kind": "home_assistant_entity_id",
            "value": "camera.porch",
            "valid_from": None,
            "valid_until": None,
        }
    ]
    assert result.body["normalization_warnings"] == [
        {
            "code": "diagnostic_device",
            "message": "Entity group could not be normalized to supported capabilities",
            "logical_device_id": "ldev_camera_porch",
            "entity_ids": ["camera.porch"],
        }
    ]


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


def test_domain_models_do_not_own_legacy_normalization() -> None:
    """Domain models stay as data contracts; application services normalize legacy states."""
    package_root = Path(__file__).resolve().parents[1] / "custom_components/smartly_bridge"
    models = (package_root / "domain/models.py").read_text()

    forbidden_snippets = [
        "to_logical_device",
        "_capability_from_snapshot",
        "_logical_device_presentation",
    ]

    for snippet in forbidden_snippets:
        assert snippet not in models


def test_package_init_does_not_import_outer_adapters_at_module_load() -> None:
    """Importing inner layers must not require HTTP/Home Assistant dependencies."""
    package_root = Path(__file__).resolve().parents[1] / "custom_components/smartly_bridge"
    path = package_root / "__init__.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    forbidden_relative_imports = {"auth", "camera", "http", "push", "webrtc"}

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue
        assert (
            node.module not in forbidden_relative_imports
        ), f"{path} imports adapter module at package load: {node.module}"


def test_webrtc_views_do_not_lookup_sessions_directly() -> None:
    """WebRTC views should delegate session lookup to the application use cases."""
    package_root = Path(__file__).resolve().parents[1] / "custom_components/smartly_bridge"
    path = package_root / "views/webrtc.py"

    assert "get_session_by_partial_token(" not in path.read_text()
