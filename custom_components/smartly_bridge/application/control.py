"""Control command application use case."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..acl import get_entity_domain
from ..domain.models import BridgeResponse
from .ports import AuditPort, CommandTargetResolverPort, ControlGatewayPort, EntityPolicyPort

LIGHT_TURN_ON_ACTIONS = {
    "set_brightness",
    "increase_brightness",
    "decrease_brightness",
    "set_color",
    "set_rgb_color",
    "set_color_temp",
    "set_color_temperature",
    "set_effect",
}

COVER_ACTIONS = {
    "set_position": "set_cover_position",
    "set_tilt_position": "set_cover_tilt_position",
    "open": "open_cover",
    "close": "close_cover",
    "stop": "stop_cover",
}

FAN_ACTIONS = {
    "set_fan_speed": "set_percentage",
    "set_direction": "set_direction",
    "set_oscillation": "oscillate",
}

CLIMATE_ACTIONS = {
    "set_mode": "set_hvac_mode",
    "set_temperature": "set_temperature",
    "set_temperature_range": "set_temperature",
    "set_fan_speed": "set_fan_mode",
    "set_preset_mode": "set_preset_mode",
    "set_swing_mode": "set_swing_mode",
}

RUN_ACTIONS = {
    "run": "turn_on",
}

SUPPORTED_SMARTLY_COMMANDS = {
    "power": {"turn_on", "turn_off", "toggle"},
    "brightness": {
        "set_brightness",
        "increase_brightness",
        "decrease_brightness",
    },
    "color_temperature": {"set_color_temperature"},
    "rgb_color": {"set_rgb_color"},
    "effect": {"set_effect"},
    "target_temperature": {"set_temperature"},
    "target_temperature_range": {"set_temperature_range"},
    "position": {"set_position", "open", "close", "stop"},
    "tilt_position": {"set_tilt_position"},
    "fan_speed": {"set_fan_speed"},
    "fan_direction": {"set_direction"},
    "fan_oscillation": {"set_oscillation"},
    "mode_select": {"set_mode"},
    "preset_mode": {"set_preset_mode"},
    "swing_mode": {"set_swing_mode"},
    "numeric_setting": {"set_value"},
    "option_setting": {"select_option"},
    "lock": {"lock", "unlock"},
    "run": {"run"},
    "button_press": {"press"},
}

SMARTLY_API_SCHEMA_VERSION = "2026.06"

SMARTLY_COMMAND_ERROR_DETAILS = {
    "command_target_not_found": (
        "COMMAND_TARGET_NOT_FOUND",
        "Command target could not be resolved.",
        "command.device_id",
    ),
    "command_not_supported": (
        "COMMAND_NOT_SUPPORTED",
        "Command is not supported by this capability.",
        "command.command",
    ),
    "invalid_params": (
        "INVALID_PARAMS",
        "Command params are invalid for this capability.",
        "command.params",
    ),
    "entity_not_allowed": (
        "ENTITY_NOT_ALLOWED",
        "Resolved source entity is not allowed.",
        "source.entity_id",
    ),
    "service_not_allowed": (
        "SERVICE_NOT_ALLOWED",
        "Resolved source service is not allowed.",
        "source.service",
    ),
    "service_call_failed": (
        "SERVICE_CALL_FAILED",
        "Source service call failed.",
        "source.service",
    ),
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
            return control_error_response("entity_not_allowed", status=403)

        service_action, service_data = _normalize_service_call(command)

        if not self._policy.is_service_allowed(command.entity_id, service_action):
            self._audit.deny(
                client_id,
                command.entity_id,
                command.action,
                "service_not_allowed",
                command.actor,
            )
            return control_error_response("service_not_allowed", status=403)

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
            return control_error_response("service_call_failed", status=500)

        self._audit.control(
            client_id,
            command.entity_id,
            command.action,
            "success",
            command.actor,
        )
        return _control_success_response(
            {
                "success": True,
                "entity_id": command.entity_id,
                "action": command.action,
                "new_state": state.state if state else None,
                "new_attributes": state.attributes if state else None,
            }
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
                _smartly_command_audit_actor(command, None),
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
                entity_id,
                command.command,
                "command_not_supported",
                _smartly_command_audit_actor(command, entity_id),
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
                entity_id,
                command.command,
                "invalid_params",
                _smartly_command_audit_actor(command, entity_id),
            )
            return _smartly_command_error_response(
                command,
                entity_id,
                "invalid_params",
                400,
            )

        actor = {
            **(command.source or {}),
            **_smartly_command_audit_actor(command, entity_id),
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

        expected_state = _expected_state_for_command(command)
        return BridgeResponse(
            {
                "success": True,
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "command_id": command.command_id,
                "status": "completed",
                "device_id": command.device_id,
                "capability": command.capability,
                "command": command.command,
                "entity_id": entity_id,
                "expected_state": expected_state,
                "new_state": result.body.get("new_state"),
                "new_attributes": result.body.get("new_attributes"),
                "data": _smartly_command_vnext_data(
                    command,
                    "completed",
                    expected_state,
                    entity_id,
                ),
                "warnings": [],
                "errors": [],
            },
            status=200,
            headers=result.headers,
        )


def _is_supported_smartly_command(command: SmartlyCommand) -> bool:
    """Return whether a canonical command is valid for its capability."""
    return command.command in SUPPORTED_SMARTLY_COMMANDS.get(command.capability, set())


def _smartly_command_audit_actor(
    command: SmartlyCommand,
    source_entity_id: str | None,
) -> dict[str, Any]:
    """Return audit actor metadata for canonical command migration tracing."""
    actor = {
        "command_id": command.command_id,
        "logical_device_id": command.device_id,
        "capability": command.capability,
    }
    if source_entity_id is not None:
        actor["source_entity_id"] = source_entity_id
    return actor


def _smartly_command_vnext_data(
    command: SmartlyCommand,
    status: str,
    expected_state: dict[str, Any],
    source_entity_id: str | None,
) -> dict[str, Any]:
    """Return API vNext command data without requiring legacy top-level fields."""
    data = {
        "command_id": command.command_id,
        "status": status,
        "device_id": command.device_id,
        "capability": command.capability,
        "command": command.command,
        "expected_state": expected_state,
    }
    if source_entity_id is not None:
        data["source_entity_id"] = source_entity_id
    return data


def _has_valid_smartly_params(command: SmartlyCommand) -> bool:
    """Return whether canonical command params satisfy the capability schema."""
    if command.capability == "brightness" and command.command == "set_brightness":
        value = command.params.get("value")
        return isinstance(value, (int, float)) and 0 <= value <= 100
    if command.capability == "brightness" and command.command in {
        "increase_brightness",
        "decrease_brightness",
    }:
        delta = command.params.get("delta")
        return isinstance(delta, (int, float)) and 1 <= delta <= 100
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
    if command.capability == "effect" and command.command == "set_effect":
        return isinstance(command.params.get("effect"), str)
    if (
        command.capability == "target_temperature"
        and command.command == "set_temperature"
    ):
        return isinstance(command.params.get("value"), (int, float))
    if (
        command.capability == "target_temperature_range"
        and command.command == "set_temperature_range"
    ):
        low = command.params.get("low")
        high = command.params.get("high")
        return (
            isinstance(low, (int, float))
            and isinstance(high, (int, float))
            and low <= high
        )
    if command.capability == "position" and command.command == "set_position":
        value = command.params.get("value")
        return isinstance(value, (int, float)) and 0 <= value <= 100
    if (
        command.capability == "tilt_position"
        and command.command == "set_tilt_position"
    ):
        value = command.params.get("value")
        return isinstance(value, (int, float)) and 0 <= value <= 100
    if command.capability == "fan_speed" and command.command == "set_fan_speed":
        percentage = command.params.get("percentage")
        speed = command.params.get("speed")
        return (
            isinstance(percentage, (int, float))
            and 0 <= percentage <= 100
        ) or isinstance(speed, str)
    if command.capability == "fan_direction" and command.command == "set_direction":
        return command.params.get("direction") in {"forward", "reverse"}
    if (
        command.capability == "fan_oscillation"
        and command.command == "set_oscillation"
    ):
        return isinstance(command.params.get("oscillating"), bool)
    if command.capability == "mode_select" and command.command == "set_mode":
        return isinstance(command.params.get("mode"), str)
    if command.capability == "preset_mode" and command.command == "set_preset_mode":
        return isinstance(command.params.get("mode"), str)
    if command.capability == "swing_mode" and command.command == "set_swing_mode":
        return isinstance(command.params.get("mode"), str)
    if command.capability == "numeric_setting" and command.command == "set_value":
        value = command.params.get("value")
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if command.capability == "option_setting" and command.command == "select_option":
        return isinstance(command.params.get("option"), str)
    return True


def _normalize_service_call(command: ControlCommand) -> tuple[str, dict[str, Any]]:
    """Map Smartly-friendly actions to Home Assistant service calls."""
    if get_entity_domain(command.entity_id) == "climate" and command.action in CLIMATE_ACTIONS:
        service_action = CLIMATE_ACTIONS[command.action]
        return service_action, _normalize_climate_service_data(command.action, command.service_data)

    if (
        get_entity_domain(command.entity_id) in {"scene", "script"}
        and command.action in RUN_ACTIONS
    ):
        return RUN_ACTIONS[command.action], command.service_data

    if get_entity_domain(command.entity_id) == "fan" and command.action in FAN_ACTIONS:
        return _normalize_fan_service_call(command.action, command.service_data)

    if get_entity_domain(command.entity_id) == "cover" and command.action in COVER_ACTIONS:
        service_action = COVER_ACTIONS[command.action]
        return service_action, _normalize_cover_service_data(command.action, command.service_data)

    if (
        get_entity_domain(command.entity_id) != "light"
        or command.action not in LIGHT_TURN_ON_ACTIONS
    ):
        return command.action, command.service_data

    return "turn_on", _normalize_light_service_data(command.action, command.service_data)


def _normalize_climate_service_data(action: str, service_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize canonical climate params to Home Assistant climate service data."""
    normalized = dict(service_data)
    if action == "set_mode" and "mode" in normalized:
        normalized.setdefault("hvac_mode", normalized.pop("mode"))
    if action == "set_temperature" and "value" in normalized:
        normalized.setdefault("temperature", normalized.pop("value"))
    if action == "set_temperature_range":
        if "low" in normalized:
            normalized.setdefault("target_temp_low", normalized.pop("low"))
        if "high" in normalized:
            normalized.setdefault("target_temp_high", normalized.pop("high"))
    if action == "set_fan_speed" and "speed" in normalized:
        normalized.setdefault("fan_mode", normalized.pop("speed"))
    if action == "set_preset_mode" and "mode" in normalized:
        normalized.setdefault("preset_mode", normalized.pop("mode"))
    if action == "set_swing_mode" and "mode" in normalized:
        normalized.setdefault("swing_mode", normalized.pop("mode"))
    return normalized


def _normalize_cover_service_data(action: str, service_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize canonical cover params to Home Assistant cover service data."""
    normalized = dict(service_data)
    if action == "set_position" and "value" in normalized:
        normalized.setdefault("position", normalized.pop("value"))
    if action == "set_tilt_position" and "value" in normalized:
        normalized.setdefault("tilt_position", normalized.pop("value"))
    return normalized


def _normalize_fan_service_call(
    action: str,
    service_data: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Normalize canonical fan params to Home Assistant fan service calls."""
    normalized = dict(service_data)
    if action == "set_fan_speed" and "speed" in normalized:
        normalized.setdefault("preset_mode", normalized.pop("speed"))
        return "set_preset_mode", normalized
    return FAN_ACTIONS[action], normalized


def _normalize_light_service_data(action: str, service_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize light aliases to Home Assistant light.turn_on fields."""
    normalized = dict(service_data)

    if action == "set_brightness" and "value" in normalized:
        normalized.setdefault("brightness_pct", normalized.pop("value"))
    if action == "increase_brightness" and "delta" in normalized:
        normalized.setdefault("brightness_step_pct", normalized.pop("delta"))
    if action == "decrease_brightness" and "delta" in normalized:
        normalized.setdefault("brightness_step_pct", -normalized.pop("delta"))
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

    if (
        command.capability == "effect"
        and command.command == "set_effect"
        and isinstance(command.params.get("effect"), str)
    ):
        return {"effect": {"value": command.params["effect"]}}

    if (
        command.capability == "target_temperature"
        and command.command == "set_temperature"
        and isinstance(command.params.get("value"), (int, float))
    ):
        return {
            "target_temperature": {
                "value": command.params["value"],
                "unit": "celsius",
            }
        }

    if (
        command.capability == "target_temperature_range"
        and command.command == "set_temperature_range"
        and isinstance(command.params.get("low"), (int, float))
        and isinstance(command.params.get("high"), (int, float))
    ):
        return {
            "target_temperature_range": {
                "low": command.params["low"],
                "high": command.params["high"],
                "unit": "celsius",
            }
        }

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

    if (
        command.capability == "tilt_position"
        and command.command == "set_tilt_position"
        and isinstance(command.params.get("value"), (int, float))
    ):
        return {
            "tilt_position": {
                "value": command.params["value"],
                "unit": "percent",
            }
        }

    if (
        command.capability == "fan_speed"
        and command.command == "set_fan_speed"
    ):
        if isinstance(command.params.get("speed"), str):
            return {"fan_speed": {"speed": command.params["speed"]}}
        if not isinstance(command.params.get("percentage"), (int, float)):
            return {}
        return {
            "fan_speed": {
                "percentage": command.params["percentage"],
                "unit": "percent",
            }
        }

    if (
        command.capability == "fan_direction"
        and command.command == "set_direction"
        and command.params.get("direction") in {"forward", "reverse"}
    ):
        return {"fan_direction": {"value": command.params["direction"]}}

    if (
        command.capability == "fan_oscillation"
        and command.command == "set_oscillation"
        and isinstance(command.params.get("oscillating"), bool)
    ):
        return {"fan_oscillation": {"value": command.params["oscillating"]}}

    if command.capability == "lock":
        if command.command == "lock":
            return {"lock": {"value": "locked"}}
        if command.command == "unlock":
            return {"lock": {"value": "unlocked"}}

    if (
        command.capability == "mode_select"
        and command.command == "set_mode"
        and isinstance(command.params.get("mode"), str)
    ):
        return {"mode_select": {"value": command.params["mode"]}}

    if (
        command.capability == "preset_mode"
        and command.command == "set_preset_mode"
        and isinstance(command.params.get("mode"), str)
    ):
        return {"preset_mode": {"value": command.params["mode"]}}

    if (
        command.capability == "swing_mode"
        and command.command == "set_swing_mode"
        and isinstance(command.params.get("mode"), str)
    ):
        return {"swing_mode": {"value": command.params["mode"]}}

    if (
        command.capability == "numeric_setting"
        and command.command == "set_value"
        and isinstance(command.params.get("value"), (int, float))
        and not isinstance(command.params.get("value"), bool)
    ):
        return {"numeric_setting": {"value": command.params["value"]}}

    if (
        command.capability == "option_setting"
        and command.command == "select_option"
        and isinstance(command.params.get("option"), str)
    ):
        return {"option_setting": {"value": command.params["option"]}}

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


def control_error_response(error: str, *, status: int) -> BridgeResponse:
    """Return a legacy-compatible API vNext control error response."""
    code, message, target = SMARTLY_COMMAND_ERROR_DETAILS.get(
        error,
        (error.upper(), error.replace("_", " "), "control"),
    )
    return BridgeResponse(
        {
            "error": error,
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {"status": "rejected"},
            "warnings": [],
            "errors": [
                {
                    "code": code,
                    "message": message,
                    "target": target,
                    "retryable": error == "service_call_failed",
                }
            ],
        },
        status=status,
    )


def _control_success_response(body: dict[str, Any], *, status: int = 200) -> BridgeResponse:
    """Return a legacy-compatible API vNext control success response."""
    return BridgeResponse(
        {
            **body,
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": body,
            "warnings": [],
            "errors": [],
        },
        status=status,
    )


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
    command_status = "failed" if response_status >= 500 else "rejected"

    return BridgeResponse(
        {
            "success": False,
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "command_id": command.command_id,
            "status": command_status,
            "error": error_code,
            "errors": [_smartly_command_vnext_error(error_code, response_status)],
            "device_id": command.device_id,
            "capability": command.capability,
            "command": command.command,
            "entity_id": entity_id,
            "expected_state": {},
            "data": _smartly_command_vnext_data(command, command_status, {}, entity_id),
            "warnings": [],
        },
        status=response_status,
        headers=result.headers if result else {},
    )


def _smartly_command_vnext_error(error_code: Any, status: int) -> dict[str, Any]:
    """Return API vNext structured error while preserving legacy error codes."""
    legacy_code = str(error_code)
    code, message, target = SMARTLY_COMMAND_ERROR_DETAILS.get(
        legacy_code,
        (
            legacy_code.upper(),
            legacy_code.replace("_", " "),
            "command",
        ),
    )
    return {
        "code": code,
        "message": message,
        "target": target,
        "retryable": status >= 500,
    }
