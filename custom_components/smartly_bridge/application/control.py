"""Control command application use case."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..acl import get_entity_domain
from ..domain.models import BridgeResponse
from .ports import AuditPort, ControlGatewayPort, EntityPolicyPort

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


def _normalize_service_call(command: ControlCommand) -> tuple[str, dict[str, Any]]:
    """Map Smartly-friendly actions to Home Assistant service calls."""
    if (
        get_entity_domain(command.entity_id) != "light"
        or command.action not in LIGHT_TURN_ON_ACTIONS
    ):
        return command.action, command.service_data

    return "turn_on", _normalize_light_service_data(command.service_data)


def _normalize_light_service_data(service_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize light aliases to Home Assistant light.turn_on fields."""
    normalized = dict(service_data)

    if "color" in normalized and "rgb_color" not in normalized:
        normalized["rgb_color"] = normalized.pop("color")
    if "color_temperature" in normalized and "color_temp" not in normalized:
        normalized["color_temp"] = normalized.pop("color_temperature")

    return normalized
