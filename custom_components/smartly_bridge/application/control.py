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
            return BridgeResponse(
                {
                    "success": False,
                    "command_id": command.command_id,
                    "status": "rejected",
                    "error": "command_target_not_found",
                    "device_id": command.device_id,
                    "capability": command.capability,
                },
                status=404,
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
                "new_state": result.body.get("new_state"),
                "new_attributes": result.body.get("new_attributes"),
            },
            status=200,
            headers=result.headers,
        )


def _normalize_service_call(command: ControlCommand) -> tuple[str, dict[str, Any]]:
    """Map Smartly-friendly actions to Home Assistant service calls."""
    if (
        get_entity_domain(command.entity_id) != "light"
        or command.action not in LIGHT_TURN_ON_ACTIONS
    ):
        return command.action, command.service_data

    return "turn_on", _normalize_light_service_data(command.action, command.service_data)


def _normalize_light_service_data(action: str, service_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize light aliases to Home Assistant light.turn_on fields."""
    normalized = dict(service_data)

    if action == "set_brightness" and "value" in normalized:
        normalized.setdefault("brightness_pct", normalized.pop("value"))
    if action == "set_color_temperature" and "value" in normalized:
        normalized.setdefault("color_temp_kelvin", normalized.pop("value"))
    if "color" in normalized and "rgb_color" not in normalized:
        normalized["rgb_color"] = normalized.pop("color")
    if "color_temperature" in normalized and "color_temp" not in normalized:
        normalized["color_temp"] = normalized.pop("color_temperature")

    return normalized


def _smartly_command_error_response(
    command: SmartlyCommand,
    entity_id: str,
    result: BridgeResponse,
) -> BridgeResponse:
    """Wrap legacy control errors in the canonical command response shape."""
    return BridgeResponse(
        {
            "success": False,
            "command_id": command.command_id,
            "status": "failed" if result.status >= 500 else "rejected",
            "error": result.body.get("error"),
            "device_id": command.device_id,
            "capability": command.capability,
            "command": command.command,
            "entity_id": entity_id,
        },
        status=result.status,
        headers=result.headers,
    )
