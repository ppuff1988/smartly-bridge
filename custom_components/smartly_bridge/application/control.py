"""Control command application use case."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..acl import get_entity_domain
from ..domain.models import BridgeResponse
from .ports import AuditPort, CommandTargetResolverPort, ControlGatewayPort, EntityPolicyPort

LIGHT_TURN_ON_ACTIONS = {
    "set_brightness",
    "set_color",
    "set_rgb_color",
    "set_color_temp",
    "set_color_temperature",
}

COVER_ACTIONS = {
    "set_position": "set_cover_position",
    "open": "open_cover",
    "close": "close_cover",
    "stop": "stop_cover",
}

SUPPORTED_SMARTLY_COMMANDS = {
    "power": {"turn_on", "turn_off", "toggle"},
    "brightness": {"set_brightness"},
    "color_temperature": {"set_color_temperature"},
    "rgb_color": {"set_rgb_color"},
    "position": {"set_position", "open", "close", "stop"},
    "fan_speed": {"set_fan_speed"},
    "mode_select": {"set_mode"},
    "lock": {"lock", "unlock"},
}


@dataclass(frozen=True)
class ControlCommand:
    """Control command requested by Platform."""

    entity_id: str
    action: str
    service_data: dict[str, Any] = field(default_factory=dict)
    actor: dict[str, Any] | None = None


@dataclass(frozen=True)
class SmartlyCommand:
    """Canonical capability command requested by Smartly Platform."""

    command_id: str
    device_id: str
    capability: str
    command: str
    params: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] | None = None


class ControlUseCase:
    """Authorize and execute a control command."""

    def __init__(
        self,
        policy: EntityPolicyPort,
        gateway: ControlGatewayPort,
        audit: AuditPort,
    ) -> None:
        self._policy = policy
        self._gateway = gateway
        self._audit = audit

    async def execute(self, client_id: str, command: ControlCommand) -> BridgeResponse:
        """Execute a control command."""
        if not self._policy.is_entity_allowed(command.entity_id):
            self._audit.deny(
                client_id,
                command.entity_id,
                command.action,
                "entity_not_allowed",
                command.actor,
            )
            return BridgeResponse({"error": "entity_not_allowed"}, status=403)

        service_action, service_data = _normalize_service_call(command)

        if not self._policy.is_service_allowed(command.entity_id, service_action):
            self._audit.deny(
                client_id,
                command.entity_id,
                command.action,
                "service_not_allowed",
                command.actor,
            )
            return BridgeResponse({"error": "service_not_allowed"}, status=403)

        try:
            state = await self._gateway.call_service(
                command.entity_id,
                service_action,
                service_data,
            )
        except Exception as err:
            self._audit.control(
                client_id,
                command.entity_id,
                command.action,
                f"error: {type(err).__name__}",
                command.actor,
            )
            return BridgeResponse({"error": "service_call_failed"}, status=500)

        self._audit.control(
            client_id,
            command.entity_id,
            command.action,
            "success",
            command.actor,
        )
        return BridgeResponse(
            {
                "success": True,
                "entity_id": command.entity_id,
                "action": command.action,
                "new_state": state.state if state else None,
                "new_attributes": state.attributes if state else None,
            },
            status=200,
        )


class SmartlyCommandUseCase:
    """Resolve and execute canonical Smartly capability commands."""

    def __init__(
        self,
        policy: EntityPolicyPort,
        gateway: ControlGatewayPort,
        audit: AuditPort,
        target_resolver: CommandTargetResolverPort,
    ) -> None:
        self._policy = policy
        self._gateway = gateway
        self._audit = audit
        self._target_resolver = target_resolver

    async def execute(self, client_id: str, command: SmartlyCommand) -> BridgeResponse:
        """Execute a canonical command through the resolved source entity."""
        entity_id = self._target_resolver.resolve_command_target(
            command.device_id,
            command.capability,
        )
        if entity_id is None:
            self._audit.deny(
                client_id,
                command.device_id,
                command.command,
                "command_target_not_found",
                {
                    "command_id": command.command_id,
                    "capability": command.capability,
                },
            )
            return _smartly_command_error_response(
                command,
                None,
                "command_target_not_found",
                404,
            )

        if not _is_supported_smartly_command(command):
            self._audit.deny(
                client_id,
                command.device_id,
                command.command,
                "command_not_supported",
                {
                    "command_id": command.command_id,
                    "capability": command.capability,
                },
            )
            return _smartly_command_error_response(
                command,
                entity_id,
                "command_not_supported",
                400,
            )

        if not _has_valid_smartly_params(command):
            self._audit.deny(
                client_id,
                command.device_id,
                command.command,
                "invalid_params",
                {
                    "command_id": command.command_id,
                    "capability": command.capability,
                },
            )
            return _smartly_command_error_response(
                command,
                entity_id,
                "invalid_params",
                400,
            )

        actor = {
            **(command.source or {}),
            "command_id": command.command_id,
            "logical_device_id": command.device_id,
            "capability": command.capability,
        }
        result = await ControlUseCase(self._policy, self._gateway, self._audit).execute(
            client_id,
            ControlCommand(
                entity_id=entity_id,
                action=command.command,
                service_data=command.params,
                actor=actor,
            ),
        )
        if result.status != 200:
            return _smartly_command_error_response(command, entity_id, result)

        return BridgeResponse(
            {
                "success": True,
                "command_id": command.command_id,
                "status": "completed",
                "device_id": command.device_id,
                "capability": command.capability,
                "command": command.command,
                "entity_id": entity_id,
                "expected_state": _expected_state_for_command(command),
                "new_state": result.body.get("new_state"),
                "new_attributes": result.body.get("new_attributes"),
            },
            status=200,
            headers=result.headers,
        )


def _is_supported_smartly_command(command: SmartlyCommand) -> bool:
    """Return whether a canonical command is valid for its capability."""
    return command.command in SUPPORTED_SMARTLY_COMMANDS.get(command.capability, set())


def _has_valid_smartly_params(command: SmartlyCommand) -> bool:
    """Return whether canonical command params satisfy the capability schema."""
    if command.capability == "brightness" and command.command == "set_brightness":
        value = command.params.get("value")
        return isinstance(value, (int, float)) and 0 <= value <= 100
    if (
        command.capability == "color_temperature"
        and command.command == "set_color_temperature"
    ):
        value = command.params.get("value")
        return isinstance(value, (int, float)) and value > 0
    if command.capability == "rgb_color" and command.command == "set_rgb_color":
        rgb_color = _rgb_color_state(command.params)
        if rgb_color is None:
            return False
        return all(0 <= channel <= 255 for channel in rgb_color.values())
    if command.capability == "position" and command.command == "set_position":
        value = command.params.get("value")
        return isinstance(value, (int, float)) and 0 <= value <= 100
    return True


def _normalize_service_call(command: ControlCommand) -> tuple[str, dict[str, Any]]:
    """Map Smartly-friendly actions to Home Assistant service calls."""
    if get_entity_domain(command.entity_id) == "cover" and command.action in COVER_ACTIONS:
        service_action = COVER_ACTIONS[command.action]
        return service_action, _normalize_cover_service_data(command.action, command.service_data)

    if (
        get_entity_domain(command.entity_id) != "light"
        or command.action not in LIGHT_TURN_ON_ACTIONS
    ):
        return command.action, command.service_data

    return "turn_on", _normalize_light_service_data(command.action, command.service_data)


def _normalize_cover_service_data(action: str, service_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize canonical cover params to Home Assistant cover service data."""
    normalized = dict(service_data)
    if action == "set_position" and "value" in normalized:
        normalized.setdefault("position", normalized.pop("value"))
    return normalized


def _normalize_light_service_data(action: str, service_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize light aliases to Home Assistant light.turn_on fields."""
    normalized = dict(service_data)

    if action == "set_brightness" and "value" in normalized:
        normalized.setdefault("brightness_pct", normalized.pop("value"))
    if action == "set_color_temperature" and "value" in normalized:
        normalized.setdefault("color_temp_kelvin", normalized.pop("value"))
    if action == "set_rgb_color" and "rgb_color" not in normalized:
        rgb_color = _rgb_color_service_data(normalized)
        if rgb_color is not None:
            normalized["rgb_color"] = rgb_color
            normalized.pop("r")
            normalized.pop("g")
            normalized.pop("b")
    if "color" in normalized and "rgb_color" not in normalized:
        normalized["rgb_color"] = normalized.pop("color")
    if "color_temperature" in normalized and "color_temp" not in normalized:
        normalized["color_temp"] = normalized.pop("color_temperature")

    return normalized


def _expected_state_for_command(command: SmartlyCommand) -> dict[str, Any]:
    """Return the expected canonical state after a command is accepted."""
    if command.capability == "power":
        if command.command == "turn_on":
            return {"power": {"value": True}}
        if command.command == "turn_off":
            return {"power": {"value": False}}

    if (
        command.capability == "brightness"
        and command.command == "set_brightness"
        and isinstance(command.params.get("value"), (int, float))
    ):
        return {
            "brightness": {
                "value": command.params["value"],
                "unit": "percent",
            }
        }

    if (
        command.capability == "color_temperature"
        and command.command == "set_color_temperature"
        and isinstance(command.params.get("value"), (int, float))
    ):
        return {
            "color_temperature": {
                "value": command.params["value"],
                "unit": "kelvin",
            }
        }

    if command.capability == "rgb_color" and command.command == "set_rgb_color":
        rgb_color = _rgb_color_state(command.params)
        if rgb_color is not None:
            return {"rgb_color": {"value": rgb_color}}

    if command.capability == "position":
        if command.command == "set_position" and isinstance(
            command.params.get("value"), (int, float)
        ):
            return {
                "position": {
                    "value": command.params["value"],
                    "unit": "percent",
                }
            }
        if command.command == "open":
            return {"position": {"value": 100, "unit": "percent"}}
        if command.command == "close":
            return {"position": {"value": 0, "unit": "percent"}}

    return {}


def _rgb_color_service_data(params: dict[str, Any]) -> list[int] | None:
    """Return Home Assistant RGB service data from canonical channel params."""
    rgb_color = _rgb_color_state(params)
    if rgb_color is None:
        return None
    return [rgb_color["r"], rgb_color["g"], rgb_color["b"]]


def _rgb_color_state(params: dict[str, Any]) -> dict[str, int] | None:
    """Return canonical RGB state when all channel params are numeric."""
    channels = (params.get("r"), params.get("g"), params.get("b"))
    if not all(isinstance(channel, (int, float)) for channel in channels):
        return None
    red, green, blue = channels
    return {"r": int(red), "g": int(green), "b": int(blue)}


def _smartly_command_error_response(
    command: SmartlyCommand,
    entity_id: str | None,
    error: str | BridgeResponse,
    status: int | None = None,
) -> BridgeResponse:
    """Wrap legacy control errors in the canonical command response shape."""
    result = error if isinstance(error, BridgeResponse) else None
    error_code = result.body.get("error") if result else error
    response_status = result.status if result else status
    if response_status is None:
        response_status = 500

    return BridgeResponse(
        {
            "success": False,
            "command_id": command.command_id,
            "status": "failed" if response_status >= 500 else "rejected",
            "error": error_code,
            "device_id": command.device_id,
            "capability": command.capability,
            "command": command.command,
            "entity_id": entity_id,
            "expected_state": {},
        },
        status=response_status,
        headers=result.headers if result else {},
    )
