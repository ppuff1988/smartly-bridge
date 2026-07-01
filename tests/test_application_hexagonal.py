"""Tests for the hexagonal application layer."""

from __future__ import annotations

import ast
import json
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
from custom_components.smartly_bridge.acl import is_service_allowed
from custom_components.smartly_bridge.domain.models import BridgeResponse, EntityStateSnapshot


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

    def get_state(self, entity_id: str) -> EntityStateSnapshot | None:
        if self.state is None or self.state.entity_id != entity_id:
            return None
        return self.state


class FakeCommandTargetResolver:
    """Fake Smartly command target resolver."""

    def __init__(self, mapping: dict[tuple[str, str], str | None]) -> None:
        self.mapping = mapping
        self.lookups: list[tuple[str, str]] = []
        self.lookup_params: list[dict[str, Any] | None] = []

    def resolve_command_target(
        self,
        device_id: str,
        capability: str,
        params: dict[str, Any] | None = None,
    ) -> str | None:
        self.lookups.append((device_id, capability))
        self.lookup_params.append(params)
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


class FakeResolvedControlUseCase:
    """Fake resolved source command use case."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ControlCommand]] = []

    async def execute(self, client_id: str, command: ControlCommand) -> BridgeResponse:
        """Record the source command and return a successful control response."""
        self.calls.append((client_id, command))
        return BridgeResponse(
            {
                "schema_version": "2026.06",
                "data": {
                    "status": "completed",
                    "source_entity_id": command.entity_id,
                    "source_action": command.action,
                    "new_state": "on",
                    "new_attributes": {"brightness": 204},
                },
                "warnings": [],
                "errors": [],
            }
        )


def assert_smartly_command_error(
    result: BridgeResponse, error_code: str, source_entity_id: str | None
) -> None:
    """Assert SmartlyCommand errors use API vNext fields for client correlation."""
    assert result.body["errors"][0]["code"] == error_code.upper()
    assert result.body["data"]["source_entity_id"] == source_entity_id


def assert_control_error(result: BridgeResponse, error_code: str) -> None:
    """Assert source control errors use API vNext fields only."""
    assert "error" not in result.body
    assert result.body["errors"][0]["code"] == error_code.upper()


def test_cover_tilt_position_service_is_allowed() -> None:
    """Cover tilt commands are allowed by the real service whitelist."""
    assert is_service_allowed("cover", "set_cover_tilt_position") is True


def test_climate_preset_mode_service_is_allowed() -> None:
    """Climate preset commands are allowed by the real service whitelist."""
    assert is_service_allowed("climate", "set_preset_mode") is True


def test_climate_swing_mode_service_is_allowed() -> None:
    """Climate swing commands are allowed by the real service whitelist."""
    assert is_service_allowed("climate", "set_swing_mode") is True


def test_fan_direction_service_is_allowed() -> None:
    """Fan direction commands are allowed by the real service whitelist."""
    assert is_service_allowed("fan", "set_direction") is True


def test_fan_oscillation_service_is_allowed() -> None:
    """Fan oscillation commands are allowed by the real service whitelist."""
    assert is_service_allowed("fan", "oscillate") is True


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


class FakeRawDiagnosticRecorder:
    """Fake raw diagnostic recorder port."""

    def __init__(self) -> None:
        self.payloads: dict[str, dict[str, Any]] = {}

    def record_raw_diagnostic(self, raw_ref: str, payload: dict[str, Any]) -> None:
        """Record raw diagnostic payloads by reference."""
        self.payloads[raw_ref] = payload


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
    assert_control_error(result, "entity_not_allowed")
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "ENTITY_NOT_ALLOWED",
            "message": "Resolved source entity is not allowed.",
            "target": "source.entity_id",
            "retryable": False,
        }
    ]
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
async def test_control_use_case_denies_service_before_service_call() -> None:
    """Disallowed services are denied by the use case without touching HA services."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    policy = FakeEntityPolicy(service_allowed=False)
    use_case = ControlUseCase(policy, gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "turn_on", {}, {"role": "viewer"}),
    )

    assert result.status == 403
    assert_control_error(result, "service_not_allowed")
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "SERVICE_NOT_ALLOWED",
            "message": "Resolved source service is not allowed.",
            "target": "source.service",
            "retryable": False,
        }
    ]
    assert policy.service_checks == [("light.kitchen", "turn_on")]
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "light.kitchen",
            "turn_on",
            "service_not_allowed",
            {"role": "viewer"},
        )
    ]


@pytest.mark.asyncio
async def test_control_use_case_calls_allowed_service_and_returns_new_state() -> None:
    """Allowed source commands return vNext data without legacy top-level fields."""
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
    assert not {
        "success",
        "entity_id",
        "action",
        "new_state",
        "new_attributes",
    } & result.body.keys()
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {
        "status": "completed",
        "source_entity_id": "light.kitchen",
        "source_action": "turn_on",
        "new_state": "on",
        "new_attributes": {"brightness": 255},
    }
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert gateway.calls == [("light.kitchen", "turn_on", {"brightness": 255})]
    assert audit.controls == [
        ("client-1", "light.kitchen", "turn_on", "success", {"role": "admin"})
    ]


@pytest.mark.asyncio
async def test_control_use_case_reports_service_call_failure() -> None:
    """Source service failures use API vNext error envelope fields."""
    audit = FakeAudit()
    gateway = FakeControlGateway(exc=RuntimeError("source unavailable"))
    use_case = ControlUseCase(FakeEntityPolicy(), gateway, audit)

    result = await use_case.execute(
        "client-1",
        ControlCommand("light.kitchen", "turn_on", {}, {"role": "admin"}),
    )

    assert result.status == 500
    assert_control_error(result, "service_call_failed")
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {"status": "rejected"}
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "SERVICE_CALL_FAILED",
            "message": "Source service call failed.",
            "target": "source.service",
            "retryable": True,
        }
    ]
    assert gateway.calls == []
    assert audit.controls == [
        (
            "client-1",
            "light.kitchen",
            "turn_on",
            "error: RuntimeError",
            {"role": "admin"},
        )
    ]


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
    assert result.body["data"]["source_action"] == "set_brightness"


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
async def test_smartly_command_use_case_dispatches_light_effect_command() -> None:
    """Effect commands map canonical effect values to Home Assistant light services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"effect": "rainbow"},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "effect"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-effect",
            device_id="ldev_light_kitchen",
            capability="effect",
            command="set_effect",
            params={"effect": "rainbow"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"effect": {"value": "rainbow"}}
    assert gateway.calls == [("light.kitchen", "turn_on", {"effect": "rainbow"})]


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
        "schema_version": "2026.06",
        "data": {
            "command_id": "cmd-1",
            "status": "completed",
            "device_id": "ldev_light_kitchen",
            "capability": "brightness",
            "command": "set_brightness",
            "adapter_id": "home_assistant",
            "correlation_id": "cmd-1",
            "source_entity_id": "light.kitchen",
            "expected_state": {"brightness": {"value": 80, "unit": "percent"}},
            "new_state": "on",
            "new_attributes": {"brightness": 204},
        },
        "warnings": [],
        "errors": [],
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
                "source_entity_id": "light.kitchen",
                "capability": "brightness",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_uses_injected_control_use_case_factory() -> None:
    """SmartlyCommand dispatches resolved source commands through an injected seam."""
    audit = FakeAudit()
    policy = FakeEntityPolicy()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"brightness": 204},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "brightness"): "light.kitchen"})
    resolved_control = FakeResolvedControlUseCase()
    factory_calls: list[tuple[object, object, object]] = []

    def control_use_case_factory(
        policy_arg: object,
        gateway_arg: object,
        audit_arg: object,
    ) -> FakeResolvedControlUseCase:
        factory_calls.append((policy_arg, gateway_arg, audit_arg))
        return resolved_control

    use_case = SmartlyCommandUseCase(
        policy,
        gateway,
        audit,
        resolver,
        control_use_case_factory=control_use_case_factory,
    )

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-factory",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="set_brightness",
            params={"value": 80},
            source={"user_id": "user-1"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["source_entity_id"] == "light.kitchen"
    assert factory_calls == [(policy, gateway, audit)]
    assert len(resolved_control.calls) == 1
    client_id, control_command = resolved_control.calls[0]
    assert client_id == "client-1"
    assert control_command == ControlCommand(
        entity_id="light.kitchen",
        action="set_brightness",
        service_data={"value": 80},
        actor={
            "user_id": "user-1",
            "command_id": "cmd-factory",
            "logical_device_id": "ldev_light_kitchen",
            "source_entity_id": "light.kitchen",
            "capability": "brightness",
        },
    )
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_smartly_command_success_response_uses_vnext_envelope_only() -> None:
    """Command success responses expose source result only through vNext data."""
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
            command_id="cmd-vnext",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="set_brightness",
            params={"value": 80},
        ),
    )

    assert result.status == 200
    assert not {
        "success",
        "command_id",
        "status",
        "adapter_id",
        "correlation_id",
        "device_id",
        "capability",
        "command",
        "entity_id",
        "expected_state",
        "new_state",
        "new_attributes",
    } & result.body.keys()
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "command_id": "cmd-vnext",
        "status": "completed",
        "device_id": "ldev_light_kitchen",
        "capability": "brightness",
        "command": "set_brightness",
        "adapter_id": "home_assistant",
        "correlation_id": "cmd-vnext",
        "source_entity_id": "light.kitchen",
        "expected_state": {"brightness": {"value": 80, "unit": "percent"}},
        "new_state": "on",
        "new_attributes": {"brightness": 204},
    }


@pytest.mark.asyncio
async def test_smartly_command_success_matches_api_vnext_fixture() -> None:
    """Command success full response matches the API vNext envelope contract."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "api-vnext" / "command-success.json"
    )
    expected_body = json.loads(fixture_path.read_text())
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
            command_id="cmd-fixture-success",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="set_brightness",
            params={"value": 80},
        ),
    )

    assert result.body == expected_body


@pytest.mark.parametrize(
    ("command_name", "delta", "expected_step"),
    [
        ("increase_brightness", 12, 12),
        ("decrease_brightness", 7, -7),
    ],
)
@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_brightness_delta_commands(
    command_name: str,
    delta: int,
    expected_step: int,
) -> None:
    """Brightness delta commands map to Home Assistant step percentages."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="light.kitchen",
            state="on",
            attributes={"brightness": 128},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "brightness"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-brightness-delta",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command=command_name,
            params={"delta": delta},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {}
    assert gateway.calls == [
        ("light.kitchen", "turn_on", {"brightness_step_pct": expected_step})
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
    assert result.body["data"]["expected_state"] == {"power": {"value": True}}
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
    assert result.body["data"]["expected_state"] == {
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
    assert result.body["data"]["expected_state"] == {
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
    assert result.body["data"]["expected_state"] == {
        "position": {"value": 55, "unit": "percent"}
    }
    assert gateway.calls == [
        ("cover.living_curtain", "set_cover_position", {"position": 55})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_cover_tilt_position_command() -> None:
    """Cover tilt commands map canonical tilt position to Home Assistant services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="cover.living_blind",
            state="open",
            attributes={"current_tilt_position": 35},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_cover_living_blind", "tilt_position"): "cover.living_blind"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-cover-tilt-position",
            device_id="ldev_cover_living_blind",
            capability="tilt_position",
            command="set_tilt_position",
            params={"value": 35},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {
        "tilt_position": {"value": 35, "unit": "percent"}
    }
    assert gateway.calls == [
        ("cover.living_blind", "set_cover_tilt_position", {"tilt_position": 35})
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
    assert result.body["data"]["expected_state"] == {"position": {"value": 100, "unit": "percent"}}
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
    assert result.body["data"]["expected_state"] == {
        "fan_speed": {"percentage": 75, "unit": "percent"}
    }
    assert gateway.calls == [("fan.bedroom", "set_percentage", {"percentage": 75})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_fan_preset_speed_command() -> None:
    """Fan speed commands map canonical speed to Home Assistant preset mode."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="fan.bedroom",
            state="on",
            attributes={"preset_mode": "sleep"},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_fan_bedroom", "fan_speed"): "fan.bedroom"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-fan-preset",
            device_id="ldev_fan_bedroom",
            capability="fan_speed",
            command="set_fan_speed",
            params={"speed": "sleep"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"fan_speed": {"speed": "sleep"}}
    assert gateway.calls == [("fan.bedroom", "set_preset_mode", {"preset_mode": "sleep"})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_fan_direction_command() -> None:
    """Fan direction commands map canonical direction to Home Assistant services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="fan.bedroom",
            state="on",
            attributes={"direction": "forward"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_fan_bedroom", "fan_direction"): "fan.bedroom"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-fan-direction",
            device_id="ldev_fan_bedroom",
            capability="fan_direction",
            command="set_direction",
            params={"direction": "reverse"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"fan_direction": {"value": "reverse"}}
    assert gateway.calls == [
        ("fan.bedroom", "set_direction", {"direction": "reverse"})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_fan_oscillation_command() -> None:
    """Fan oscillation commands map canonical oscillation to Home Assistant services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="fan.bedroom",
            state="on",
            attributes={"oscillating": False},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_fan_bedroom", "fan_oscillation"): "fan.bedroom"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-fan-oscillation",
            device_id="ldev_fan_bedroom",
            capability="fan_oscillation",
            command="set_oscillation",
            params={"oscillating": True},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"fan_oscillation": {"value": True}}
    assert gateway.calls == [
        ("fan.bedroom", "oscillate", {"oscillating": True})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_climate_fan_speed_command() -> None:
    """Climate fan speed commands map canonical speed to Home Assistant fan mode."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="climate.living_room",
            state="cool",
            attributes={"fan_mode": "auto"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_climate_living_room", "fan_speed"): "climate.living_room"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-climate-fan-speed",
            device_id="ldev_climate_living_room",
            capability="fan_speed",
            command="set_fan_speed",
            params={"speed": "auto"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"fan_speed": {"speed": "auto"}}
    assert gateway.calls == [
        ("climate.living_room", "set_fan_mode", {"fan_mode": "auto"})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_climate_preset_mode_command() -> None:
    """Climate preset commands map canonical preset mode to Home Assistant services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="climate.living_room",
            state="cool",
            attributes={"preset_mode": "eco"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_climate_living_room", "preset_mode"): "climate.living_room"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-climate-preset-mode",
            device_id="ldev_climate_living_room",
            capability="preset_mode",
            command="set_preset_mode",
            params={"mode": "eco"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"preset_mode": {"value": "eco"}}
    assert gateway.calls == [
        ("climate.living_room", "set_preset_mode", {"preset_mode": "eco"})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_climate_swing_mode_command() -> None:
    """Climate swing commands map canonical swing mode to Home Assistant services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="climate.living_room",
            state="cool",
            attributes={"swing_mode": "vertical"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_climate_living_room", "swing_mode"): "climate.living_room"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-climate-swing-mode",
            device_id="ldev_climate_living_room",
            capability="swing_mode",
            command="set_swing_mode",
            params={"mode": "vertical"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"swing_mode": {"value": "vertical"}}
    assert gateway.calls == [
        ("climate.living_room", "set_swing_mode", {"swing_mode": "vertical"})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_returns_lock_expected_state() -> None:
    """Lock commands expose expected lock state for correlation."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="lock.front_door",
            state="locked",
            attributes={},
        )
    )
    resolver = FakeCommandTargetResolver({("ldev_lock_front_door", "lock"): "lock.front_door"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-lock",
            device_id="ldev_lock_front_door",
            capability="lock",
            command="lock",
            params={},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"lock": {"value": "locked"}}
    assert gateway.calls == [("lock.front_door", "lock", {})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_scene_run_command() -> None:
    """Run commands map scene trigger capabilities to Home Assistant turn_on."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="scene.movie_night",
            state="2026-06-29T12:00:00+00:00",
            attributes={},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_scene_movie_night", "run"): "scene.movie_night"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-run",
            device_id="ldev_scene_movie_night",
            capability="run",
            command="run",
            params={"transition": 3},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {}
    assert gateway.calls == [("scene.movie_night", "turn_on", {"transition": 3})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_script_run_command() -> None:
    """Run commands map script trigger capabilities to Home Assistant turn_on."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="script.notify_user",
            state="off",
            attributes={},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_script_notify_user", "run"): "script.notify_user"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-script-run",
            device_id="ldev_script_notify_user",
            capability="run",
            command="run",
            params={"variables": {"message": "Hello from API"}},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {}
    assert gateway.calls == [
        (
            "script.notify_user",
            "turn_on",
            {"variables": {"message": "Hello from API"}},
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_button_press_command() -> None:
    """Button press commands map canonical button triggers to Home Assistant button.press."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="button.desk_scene",
            state="idle",
            attributes={},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_button_desk_scene", "button_press"): "button.desk_scene"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-button-press",
            device_id="ldev_button_desk_scene",
            capability="button_press",
            command="press",
            params={},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {}
    assert result.body["data"] == {
        "command_id": "cmd-button-press",
        "status": "completed",
        "device_id": "ldev_button_desk_scene",
        "capability": "button_press",
        "command": "press",
        "adapter_id": "home_assistant",
        "correlation_id": "cmd-button-press",
        "source_entity_id": "button.desk_scene",
        "expected_state": {},
        "new_state": "idle",
        "new_attributes": {},
    }
    assert gateway.calls == [("button.desk_scene", "press", {})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_climate_mode_command() -> None:
    """Mode select commands map canonical mode to Home Assistant climate services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="climate.living_room",
            state="cool",
            attributes={"hvac_mode": "cool"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_climate_living_room", "mode_select"): "climate.living_room"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-mode",
            device_id="ldev_climate_living_room",
            capability="mode_select",
            command="set_mode",
            params={"mode": "cool"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"mode_select": {"value": "cool"}}
    assert gateway.calls == [("climate.living_room", "set_hvac_mode", {"hvac_mode": "cool"})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_numeric_setting_command() -> None:
    """Numeric setting commands map canonical setting values to number services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="number.presence_detection_delay",
            state="20",
            attributes={"unit_of_measurement": "s"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_zigbee_presence_1", "numeric_setting"): "number.presence_detection_delay"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-setting-delay",
            device_id="ldev_zigbee_presence_1",
            capability="numeric_setting",
            command="set_value",
            params={"value": 20},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"numeric_setting": {"value": 20}}
    assert gateway.calls == [("number.presence_detection_delay", "set_value", {"value": 20})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_numeric_setting_outside_range() -> None:
    """Numeric setting commands honor source number min/max constraints."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="number.presence_detection_delay",
            state="20",
            attributes={"min": 1, "max": 120, "step": 1, "unit_of_measurement": "s"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_zigbee_presence_1", "numeric_setting"): "number.presence_detection_delay"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-setting-delay-out-of-range",
            device_id="ldev_zigbee_presence_1",
            capability="numeric_setting",
            command="set_value",
            params={"value": 121},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(
        result, "invalid_params", "number.presence_detection_delay"
    )
    assert result.body["data"]["expected_state"] == {}
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "number.presence_detection_delay",
            "set_value",
            "invalid_params",
            {
                "command_id": "cmd-setting-delay-out-of-range",
                "logical_device_id": "ldev_zigbee_presence_1",
                "capability": "numeric_setting",
                "source_entity_id": "number.presence_detection_delay",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_numeric_setting_invalid_step() -> None:
    """Numeric setting commands honor source number step constraints."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="number.presence_detection_delay",
            state="1.5",
            attributes={"min": 1, "max": 120, "step": 0.5, "unit_of_measurement": "s"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_zigbee_presence_1", "numeric_setting"): "number.presence_detection_delay"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-setting-delay-invalid-step",
            device_id="ldev_zigbee_presence_1",
            capability="numeric_setting",
            command="set_value",
            params={"value": 1.25},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(
        result, "invalid_params", "number.presence_detection_delay"
    )
    assert result.body["data"]["expected_state"] == {}
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "number.presence_detection_delay",
            "set_value",
            "invalid_params",
            {
                "command_id": "cmd-setting-delay-invalid-step",
                "logical_device_id": "ldev_zigbee_presence_1",
                "capability": "numeric_setting",
                "source_entity_id": "number.presence_detection_delay",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_passes_setting_key_to_target_resolver() -> None:
    """Setting command params are available to resolver-specific target selection."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="number.presence_cooldown",
            state="5",
            attributes={"unit_of_measurement": "s"},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_zigbee_presence_1", "numeric_setting"): "number.presence_cooldown"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-setting-cooldown",
            device_id="ldev_zigbee_presence_1",
            capability="numeric_setting",
            command="set_value",
            params={"key": "cooldown_seconds", "value": 5},
        ),
    )

    assert result.status == 200
    assert resolver.lookup_params == [{"key": "cooldown_seconds", "value": 5}]
    assert gateway.calls == [("number.presence_cooldown", "set_value", {"value": 5})]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_option_setting_command() -> None:
    """Option setting commands map canonical options to select services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="select.presence_occupancy_sensitivity",
            state="medium",
            attributes={"options": ["low", "medium", "high"]},
        )
    )
    resolver = FakeCommandTargetResolver(
        {
            (
                "ldev_zigbee_presence_1",
                "option_setting",
            ): "select.presence_occupancy_sensitivity"
        }
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-setting-sensitivity",
            device_id="ldev_zigbee_presence_1",
            capability="option_setting",
            command="select_option",
            params={"option": "medium"},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {"option_setting": {"value": "medium"}}
    assert gateway.calls == [
        ("select.presence_occupancy_sensitivity", "select_option", {"option": "medium"})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_option_setting_unknown_option() -> None:
    """Option setting commands honor source select option constraints."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="select.presence_occupancy_sensitivity",
            state="medium",
            attributes={"options": ["low", "medium", "high"]},
        )
    )
    resolver = FakeCommandTargetResolver(
        {
            (
                "ldev_zigbee_presence_1",
                "option_setting",
            ): "select.presence_occupancy_sensitivity"
        }
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-setting-sensitivity-invalid",
            device_id="ldev_zigbee_presence_1",
            capability="option_setting",
            command="select_option",
            params={"option": "turbo"},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(
        result, "invalid_params", "select.presence_occupancy_sensitivity"
    )
    assert result.body["data"]["expected_state"] == {}
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "select.presence_occupancy_sensitivity",
            "select_option",
            "invalid_params",
            {
                "command_id": "cmd-setting-sensitivity-invalid",
                "logical_device_id": "ldev_zigbee_presence_1",
                "capability": "option_setting",
                "source_entity_id": "select.presence_occupancy_sensitivity",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_climate_temperature_command() -> None:
    """Target temperature commands map canonical values to climate services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="climate.living_room",
            state="cool",
            attributes={"temperature": 24},
        )
    )
    resolver = FakeCommandTargetResolver(
        {("ldev_climate_living_room", "target_temperature"): "climate.living_room"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-temperature",
            device_id="ldev_climate_living_room",
            capability="target_temperature",
            command="set_temperature",
            params={"value": 24},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {
        "target_temperature": {"value": 24, "unit": "celsius"}
    }
    assert gateway.calls == [
        ("climate.living_room", "set_temperature", {"temperature": 24})
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_dispatches_climate_temperature_range_command() -> None:
    """Target temperature range commands map canonical bounds to climate services."""
    audit = FakeAudit()
    gateway = FakeControlGateway(
        EntityStateSnapshot(
            entity_id="climate.living_room",
            state="heat_cool",
            attributes={"target_temp_low": 22, "target_temp_high": 26},
        )
    )
    resolver = FakeCommandTargetResolver(
        {
            (
                "ldev_climate_living_room",
                "target_temperature_range",
            ): "climate.living_room"
        }
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-temperature-range",
            device_id="ldev_climate_living_room",
            capability="target_temperature_range",
            command="set_temperature_range",
            params={"low": 22, "high": 26},
        ),
    )

    assert result.status == 200
    assert result.body["data"]["expected_state"] == {
        "target_temperature_range": {
            "low": 22,
            "high": 26,
            "unit": "celsius",
        }
    }
    assert gateway.calls == [
        (
            "climate.living_room",
            "set_temperature",
            {"target_temp_low": 22, "target_temp_high": 26},
        )
    ]


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
        "schema_version": "2026.06",
        "data": {
            "command_id": "cmd-404",
            "status": "rejected",
            "device_id": "ldev_unknown",
            "capability": "power",
            "command": "turn_on",
            "adapter_id": "home_assistant",
            "correlation_id": "cmd-404",
            "expected_state": {},
        },
        "warnings": [],
        "errors": [
            {
                "code": "COMMAND_TARGET_NOT_FOUND",
                "message": "Command target could not be resolved.",
                "target": "command.device_id",
                "retryable": False,
            }
        ],
    }
    assert resolver.lookups == [("ldev_unknown", "power")]
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "ldev_unknown",
            "turn_on",
            "command_target_not_found",
            {
                "command_id": "cmd-404",
                "logical_device_id": "ldev_unknown",
                "capability": "power",
            },
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
        "schema_version": "2026.06",
        "data": {
            "command_id": "cmd-unsupported",
            "status": "rejected",
            "device_id": "ldev_light_kitchen",
            "capability": "brightness",
            "command": "turn_on",
            "adapter_id": "home_assistant",
            "correlation_id": "cmd-unsupported",
            "source_entity_id": "light.kitchen",
            "expected_state": {},
        },
        "warnings": [],
        "errors": [
            {
                "code": "COMMAND_NOT_SUPPORTED",
                "message": "Command is not supported by this capability.",
                "target": "command.command",
                "retryable": False,
            }
        ],
    }
    assert resolver.lookups == [("ldev_light_kitchen", "brightness")]
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "light.kitchen",
            "turn_on",
            "command_not_supported",
            {
                "command_id": "cmd-unsupported",
                "logical_device_id": "ldev_light_kitchen",
                "source_entity_id": "light.kitchen",
                "capability": "brightness",
            },
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
        "schema_version": "2026.06",
        "data": {
            "command_id": "cmd-invalid",
            "status": "rejected",
            "device_id": "ldev_light_kitchen",
            "capability": "brightness",
            "command": "set_brightness",
            "adapter_id": "home_assistant",
            "correlation_id": "cmd-invalid",
            "source_entity_id": "light.kitchen",
            "expected_state": {},
        },
        "warnings": [],
        "errors": [
            {
                "code": "INVALID_PARAMS",
                "message": "Command params are invalid for this capability.",
                "target": "command.params",
                "retryable": False,
            }
        ],
    }
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "light.kitchen",
            "set_brightness",
            "invalid_params",
            {
                "command_id": "cmd-invalid",
                "logical_device_id": "ldev_light_kitchen",
                "source_entity_id": "light.kitchen",
                "capability": "brightness",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_error_response_includes_vnext_errors_array() -> None:
    """Command errors expose API vNext structured errors without dropping legacy error."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "brightness"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-vnext",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="set_brightness",
            params={"value": 150},
        ),
    )

    assert result.status == 400
    assert result.body["errors"] == [
        {
            "code": "INVALID_PARAMS",
            "message": "Command params are invalid for this capability.",
            "target": "command.params",
            "retryable": False,
        }
    ]


@pytest.mark.asyncio
async def test_smartly_command_error_response_includes_vnext_envelope() -> None:
    """Command error responses expose only the API vNext top-level envelope."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "brightness"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-envelope",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="set_brightness",
            params={"value": 150},
        ),
    )

    assert result.status == 400
    legacy_fields = {
        "success",
        "command_id",
        "status",
        "adapter_id",
        "correlation_id",
        "error",
        "device_id",
        "capability",
        "command",
        "entity_id",
        "expected_state",
    }
    assert legacy_fields.isdisjoint(result.body)
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == [
        {
            "code": "INVALID_PARAMS",
            "message": "Command params are invalid for this capability.",
            "target": "command.params",
            "retryable": False,
        }
    ]
    assert result.body["data"] == {
        "command_id": "cmd-invalid-envelope",
        "status": "rejected",
        "device_id": "ldev_light_kitchen",
        "capability": "brightness",
        "command": "set_brightness",
        "adapter_id": "home_assistant",
        "correlation_id": "cmd-invalid-envelope",
        "source_entity_id": "light.kitchen",
        "expected_state": {},
    }


@pytest.mark.asyncio
async def test_smartly_command_error_matches_api_vnext_fixture() -> None:
    """Command error full response remains stable for legacy and vNext clients."""
    fixture_path = Path(__file__).parent / "fixtures" / "api-vnext" / "command-error.json"
    expected_body = json.loads(fixture_path.read_text())
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "brightness"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-fixture-error",
            device_id="ldev_light_kitchen",
            capability="brightness",
            command="set_brightness",
            params={"value": 150},
        ),
    )

    assert result.body == expected_body


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
    assert_smartly_command_error(result, "invalid_params", "light.kitchen")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "light.kitchen",
            "set_rgb_color",
            "invalid_params",
            {
                "command_id": "cmd-invalid-rgb",
                "logical_device_id": "ldev_light_kitchen",
                "source_entity_id": "light.kitchen",
                "capability": "rgb_color",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_effect_params() -> None:
    """Effect commands require a string effect name."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver({("ldev_light_kitchen", "effect"): "light.kitchen"})
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-effect",
            device_id="ldev_light_kitchen",
            capability="effect",
            command="set_effect",
            params={"effect": 12},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(result, "invalid_params", "light.kitchen")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "light.kitchen",
            "set_effect",
            "invalid_params",
            {
                "command_id": "cmd-invalid-effect",
                "logical_device_id": "ldev_light_kitchen",
                "source_entity_id": "light.kitchen",
                "capability": "effect",
            },
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
    assert_smartly_command_error(result, "invalid_params", "light.kitchen")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "light.kitchen",
            "set_color_temperature",
            "invalid_params",
            {
                "command_id": "cmd-invalid-color-temp",
                "logical_device_id": "ldev_light_kitchen",
                "source_entity_id": "light.kitchen",
                "capability": "color_temperature",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_target_temperature_params() -> None:
    """Target temperature commands require a numeric value."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {("ldev_climate_living_room", "target_temperature"): "climate.living_room"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-target-temperature",
            device_id="ldev_climate_living_room",
            capability="target_temperature",
            command="set_temperature",
            params={"value": "warm"},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(result, "invalid_params", "climate.living_room")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "climate.living_room",
            "set_temperature",
            "invalid_params",
            {
                "command_id": "cmd-invalid-target-temperature",
                "logical_device_id": "ldev_climate_living_room",
                "source_entity_id": "climate.living_room",
                "capability": "target_temperature",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_temperature_range_params() -> None:
    """Temperature range commands require ordered numeric bounds."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {
            (
                "ldev_climate_living_room",
                "target_temperature_range",
            ): "climate.living_room"
        }
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-temperature-range",
            device_id="ldev_climate_living_room",
            capability="target_temperature_range",
            command="set_temperature_range",
            params={"low": 27, "high": 22},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(result, "invalid_params", "climate.living_room")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "climate.living_room",
            "set_temperature_range",
            "invalid_params",
            {
                "command_id": "cmd-invalid-temperature-range",
                "logical_device_id": "ldev_climate_living_room",
                "source_entity_id": "climate.living_room",
                "capability": "target_temperature_range",
            },
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
    assert_smartly_command_error(result, "invalid_params", "cover.living_curtain")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "cover.living_curtain",
            "set_position",
            "invalid_params",
            {
                "command_id": "cmd-invalid-position",
                "logical_device_id": "ldev_cover_living_curtain",
                "source_entity_id": "cover.living_curtain",
                "capability": "position",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_tilt_position_params() -> None:
    """Tilt position commands require a percentage value in range."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {("ldev_cover_living_blind", "tilt_position"): "cover.living_blind"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-tilt-position",
            device_id="ldev_cover_living_blind",
            capability="tilt_position",
            command="set_tilt_position",
            params={"value": 120},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(result, "invalid_params", "cover.living_blind")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "cover.living_blind",
            "set_tilt_position",
            "invalid_params",
            {
                "command_id": "cmd-invalid-tilt-position",
                "logical_device_id": "ldev_cover_living_blind",
                "source_entity_id": "cover.living_blind",
                "capability": "tilt_position",
            },
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
    assert_smartly_command_error(result, "invalid_params", "fan.bedroom")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "fan.bedroom",
            "set_fan_speed",
            "invalid_params",
            {
                "command_id": "cmd-invalid-fan-speed",
                "logical_device_id": "ldev_fan_bedroom",
                "source_entity_id": "fan.bedroom",
                "capability": "fan_speed",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_fan_direction_params() -> None:
    """Fan direction commands require a supported direction value."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {("ldev_fan_bedroom", "fan_direction"): "fan.bedroom"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-fan-direction",
            device_id="ldev_fan_bedroom",
            capability="fan_direction",
            command="set_direction",
            params={"direction": "sideways"},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(result, "invalid_params", "fan.bedroom")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "fan.bedroom",
            "set_direction",
            "invalid_params",
            {
                "command_id": "cmd-invalid-fan-direction",
                "logical_device_id": "ldev_fan_bedroom",
                "source_entity_id": "fan.bedroom",
                "capability": "fan_direction",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_fan_oscillation_params() -> None:
    """Fan oscillation commands require a boolean oscillating value."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {("ldev_fan_bedroom", "fan_oscillation"): "fan.bedroom"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-fan-oscillation",
            device_id="ldev_fan_bedroom",
            capability="fan_oscillation",
            command="set_oscillation",
            params={"oscillating": "yes"},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(result, "invalid_params", "fan.bedroom")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "fan.bedroom",
            "set_oscillation",
            "invalid_params",
            {
                "command_id": "cmd-invalid-fan-oscillation",
                "logical_device_id": "ldev_fan_bedroom",
                "source_entity_id": "fan.bedroom",
                "capability": "fan_oscillation",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_preset_mode_params() -> None:
    """Preset mode commands require a string mode value."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {("ldev_climate_living_room", "preset_mode"): "climate.living_room"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-preset-mode",
            device_id="ldev_climate_living_room",
            capability="preset_mode",
            command="set_preset_mode",
            params={"mode": 123},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(result, "invalid_params", "climate.living_room")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "climate.living_room",
            "set_preset_mode",
            "invalid_params",
            {
                "command_id": "cmd-invalid-preset-mode",
                "logical_device_id": "ldev_climate_living_room",
                "source_entity_id": "climate.living_room",
                "capability": "preset_mode",
            },
        )
    ]


@pytest.mark.asyncio
async def test_smartly_command_use_case_rejects_invalid_swing_mode_params() -> None:
    """Swing mode commands require a string mode value."""
    audit = FakeAudit()
    gateway = FakeControlGateway()
    resolver = FakeCommandTargetResolver(
        {("ldev_climate_living_room", "swing_mode"): "climate.living_room"}
    )
    use_case = SmartlyCommandUseCase(FakeEntityPolicy(), gateway, audit, resolver)

    result = await use_case.execute(
        "client-1",
        SmartlyCommand(
            command_id="cmd-invalid-swing-mode",
            device_id="ldev_climate_living_room",
            capability="swing_mode",
            command="set_swing_mode",
            params={"mode": 123},
        ),
    )

    assert result.status == 400
    assert_smartly_command_error(result, "invalid_params", "climate.living_room")
    assert gateway.calls == []
    assert audit.denials == [
        (
            "client-1",
            "climate.living_room",
            "set_swing_mode",
            "invalid_params",
            {
                "command_id": "cmd-invalid-swing-mode",
                "logical_device_id": "ldev_climate_living_room",
                "source_entity_id": "climate.living_room",
                "capability": "swing_mode",
            },
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
        "schema_version": "2026.06",
        "data": {
            "command_id": "cmd-denied",
            "status": "rejected",
            "device_id": "ldev_light_kitchen",
            "capability": "power",
            "command": "turn_on",
            "adapter_id": "home_assistant",
            "correlation_id": "cmd-denied",
            "source_entity_id": "light.kitchen",
            "expected_state": {},
        },
        "warnings": [],
        "errors": [
            {
                "code": "SERVICE_NOT_ALLOWED",
                "message": "Resolved source service is not allowed.",
                "target": "source.service",
                "retryable": False,
            }
        ],
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
        "schema_version": "2026.06",
        "data": {
            "command_id": "cmd-failed",
            "status": "failed",
            "device_id": "ldev_light_kitchen",
            "capability": "power",
            "command": "turn_on",
            "adapter_id": "home_assistant",
            "correlation_id": "cmd-failed",
            "source_entity_id": "light.kitchen",
            "expected_state": {},
        },
        "warnings": [],
        "errors": [
            {
                "code": "SERVICE_CALL_FAILED",
                "message": "Source service call failed.",
                "target": "source.service",
                "retryable": True,
            }
        ],
    }


def test_sync_structure_use_case_returns_gateway_structure() -> None:
    """Structure sync uses a sync port instead of reading Home Assistant directly."""
    gateway = FakeSyncGateway()
    result = SyncStructureUseCase(gateway).execute()

    assert result.status == 200
    assert result.body["floors"] == gateway.structure["floors"]
    assert result.body["areas"] == gateway.structure["areas"]
    assert result.body["devices"] == gateway.structure["devices"]
    assert result.body["entities"] == gateway.structure["entities"]
    assert result.body["schema_version"] == "2026.06"
    assert result.body["data"] == {**gateway.structure, "device_count": 0}
    assert result.body["warnings"] == []
    assert result.body["errors"] == []


def test_sync_structure_use_case_includes_vnext_envelope() -> None:
    """Structure sync exposes API vNext envelope fields alongside legacy fields."""
    gateway = FakeSyncGateway()
    result = SyncStructureUseCase(gateway).execute()

    assert result.status == 200
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {**gateway.structure, "device_count": 0}
    assert result.body["entities"] == gateway.structure["entities"]


def test_sync_structure_use_case_matches_current_sync_vnext_data_fixture() -> None:
    """Structure sync vNext data matches the current-sync contract snapshot."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "current-sync" / "structure-vnext-data.json"
    )
    expected_data = json.loads(fixture_path.read_text())

    result = SyncStructureUseCase(FakeSyncGateway()).execute()

    assert result.body["data"] == expected_data


def test_sync_structure_use_case_matches_current_sync_envelope_fixture() -> None:
    """Structure sync full response preserves legacy fields and vNext envelope."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "current-sync" / "structure-envelope.json"
    )
    expected_body = json.loads(fixture_path.read_text())

    result = SyncStructureUseCase(FakeSyncGateway()).execute()

    assert result.body == expected_body


@pytest.mark.asyncio
async def test_sync_states_use_case_returns_states_with_count() -> None:
    """State sync serializes state snapshots returned by the port."""
    result = await SyncStatesUseCase(FakeSyncGateway()).execute()

    assert result.status == 200
    assert result.body["states"] == [
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
    ]
    assert result.body["count"] == 1
    assert result.body["normalization_warnings"] == []
    assert result.body["logical_devices"] == [
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
            "raw_refs": [],
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
                    "commands": [
                        "set_brightness",
                        "increase_brightness",
                        "decrease_brightness",
                    ],
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
    ]
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == []
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "states": result.body["states"],
        "count": 1,
        "logical_devices": result.body["logical_devices"],
        "normalization_warnings": [],
        "device_count": 1,
        "updates": [
            {
                "device_id": "ldev_light_kitchen",
                "capability": "power",
                "state": {
                    "value": True,
                    "updated_at": "2026-06-24T00:00:00+00:00",
                },
            },
            {
                "device_id": "ldev_light_kitchen",
                "capability": "brightness",
                "state": {
                    "value": 50,
                    "unit": "percent",
                    "updated_at": "2026-06-24T00:00:00+00:00",
                },
            },
        ],
    }


@pytest.mark.asyncio
async def test_sync_states_use_case_includes_vnext_envelope() -> None:
    """State sync exposes API vNext envelope fields alongside legacy fields."""
    result = await SyncStatesUseCase(FakeSyncGateway()).execute()

    assert result.status == 200
    assert result.body["schema_version"] == "2026.06"
    assert result.body["warnings"] == result.body["normalization_warnings"]
    assert result.body["errors"] == []
    assert result.body["data"] == {
        "states": result.body["states"],
        "count": 1,
        "logical_devices": result.body["logical_devices"],
        "normalization_warnings": [],
        "device_count": 1,
        "updates": [
            {
                "device_id": "ldev_light_kitchen",
                "capability": "power",
                "state": {
                    "value": True,
                    "updated_at": "2026-06-24T00:00:00+00:00",
                },
            },
            {
                "device_id": "ldev_light_kitchen",
                "capability": "brightness",
                "state": {
                    "value": 50,
                    "unit": "percent",
                    "updated_at": "2026-06-24T00:00:00+00:00",
                },
            },
        ],
    }


@pytest.mark.asyncio
async def test_sync_states_use_case_includes_vnext_state_updates() -> None:
    """State sync vNext data exposes capability state updates for Platform read path."""
    result = await SyncStatesUseCase(FakeSyncGateway()).execute()

    assert result.body["data"]["updates"] == [
        {
            "device_id": "ldev_light_kitchen",
            "capability": "power",
            "state": {
                "value": True,
                "updated_at": "2026-06-24T00:00:00+00:00",
            },
        },
        {
            "device_id": "ldev_light_kitchen",
            "capability": "brightness",
            "state": {
                "value": 50,
                "unit": "percent",
                "updated_at": "2026-06-24T00:00:00+00:00",
            },
        },
    ]


@pytest.mark.asyncio
async def test_sync_states_use_case_matches_current_sync_vnext_data_fixture() -> None:
    """State sync vNext data matches the current-sync contract snapshot."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "current-sync" / "states-vnext-data.json"
    )
    expected_data = json.loads(fixture_path.read_text())

    result = await SyncStatesUseCase(FakeSyncGateway()).execute()

    assert result.body["data"] == expected_data


@pytest.mark.asyncio
async def test_sync_states_use_case_matches_current_sync_envelope_fixture() -> None:
    """State sync full response preserves legacy fields and vNext envelope."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "current-sync" / "states-envelope.json"
    )
    expected_body = json.loads(fixture_path.read_text())

    result = await SyncStatesUseCase(FakeSyncGateway()).execute()

    assert result.body == expected_body


@pytest.mark.asyncio
async def test_sync_states_use_case_reports_diagnostic_normalization_warnings() -> None:
    """Unsupported entities remain visible and emit diagnostic normalization warnings."""
    result = await SyncStatesUseCase(FakeDiagnosticSyncGateway()).execute()

    assert result.status == 200
    assert result.body["logical_devices"][0]["device_class"] == "diagnostic_device"
    assert result.body["logical_devices"][0]["raw_refs"] == []
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


@pytest.mark.asyncio
async def test_sync_states_use_case_records_diagnostic_raw_refs() -> None:
    """Diagnostic fallback devices expose raw refs and store raw payload out-of-band."""
    recorder = FakeRawDiagnosticRecorder()

    result = await SyncStatesUseCase(
        FakeDiagnosticSyncGateway(),
        raw_diagnostic_recorder=recorder,
    ).execute()

    raw_ref = "raw_ldev_camera_porch"
    assert result.status == 200
    assert result.body["logical_devices"][0]["raw_refs"] == [
        {
            "raw_ref": raw_ref,
            "kind": "normalization_diagnostic",
            "source": "home_assistant",
            "entity_ids": ["camera.porch"],
        }
    ]
    assert "raw_payload" not in result.body["logical_devices"][0]
    assert recorder.payloads == {
        raw_ref: {
            "logical_device_id": "ldev_camera_porch",
            "device_class": "diagnostic_device",
            "source_entities": [
                {
                    "entity_id": "camera.porch",
                    "state": "idle",
                    "attributes": {"friendly_name": "Porch Camera"},
                    "last_changed": None,
                    "last_updated": None,
                    "icon": None,
                    "name": "Porch Camera",
                    "domain": "camera",
                    "device_class": "unknown_device",
                    "capabilities": [],
                    "status": "online",
                    "presentation": {"card_template": "unknown_card"},
                }
            ],
        }
    }


@pytest.mark.asyncio
async def test_sync_states_use_case_marks_logical_device_read_path() -> None:
    """The logical-device read path can be enabled without dropping legacy states."""
    result = await SyncStatesUseCase(
        FakeSyncGateway(),
        use_logical_devices=True,
    ).execute()

    assert result.status == 200
    assert result.body["read_path"] == "logical_devices"
    assert result.body["device_count"] == 1
    assert result.body["devices"] == result.body["logical_devices"]
    assert result.body["data"]["read_path"] == "logical_devices"
    assert result.body["data"]["device_count"] == 1
    assert result.body["data"]["devices"] == result.body["logical_devices"]
    assert result.body["states"][0]["entity_id"] == "light.kitchen"


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
