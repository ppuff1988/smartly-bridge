"""Local automation application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..domain.models import BridgeResponse
from .control import SmartlyCommand
from .ports import LocalAutomationRuleStorePort, SmartlyCommandExecutorPort

SMARTLY_API_SCHEMA_VERSION = "2026.06"


@dataclass(frozen=True)
class AutomationTrigger:
    """Canonical device event trigger for a local automation rule."""

    device_id: str
    capability: str
    event: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationAction:
    """Local automation action."""

    type: str
    device_id: str
    capability: str
    command: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalAutomationRule:
    """Local automation rule using canonical triggers and actions."""

    rule_id: str
    trigger: AutomationTrigger
    actions: list[AutomationAction]
    enabled: bool = True


CommandIdFactory = Callable[[dict[str, Any], LocalAutomationRule, int], str]


class LocalAutomationRulesListUseCase:
    """List local automation rules as canonical API payloads."""

    def __init__(self, rules: LocalAutomationRuleStorePort) -> None:
        self._rules = rules

    def execute(self) -> BridgeResponse:
        """Return configured local automation rules."""
        rules = [_rule_payload(rule) for rule in self._rules.list_rules()]
        return BridgeResponse(
            {
                "success": True,
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "rules": rules,
                "count": len(rules),
                "data": {
                    "rules": rules,
                    "count": len(rules),
                },
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


class LocalAutomationRuleCreateUseCase:
    """Create a local automation rule from canonical API payloads."""

    def __init__(self, rules: LocalAutomationRuleStorePort) -> None:
        self._rules = rules

    def execute(self, payload: dict[str, Any]) -> BridgeResponse:
        """Persist a new local automation rule."""
        rule = _rule_from_payload(payload)
        if rule is None:
            return _rule_error_response(
                "invalid_rule",
                message="Invalid local automation rule",
                status=400,
                target="rule",
            )
        if any(existing.rule_id == rule.rule_id for existing in self._rules.list_rules()):
            return _rule_error_response(
                "rule_already_exists",
                message="Local automation rule already exists",
                status=409,
                target="rule.rule_id",
            )
        if not self._rules.create_rule(rule):
            return _rule_error_response(
                "rule_persistence_failed",
                message="Local automation rule could not be persisted",
                status=500,
                target="rule",
            )
        body_rule = _rule_payload(rule)
        return BridgeResponse(
            {
                "success": True,
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "status": "created",
                "rule_id": rule.rule_id,
                "rule": body_rule,
                "data": {
                    "status": "created",
                    "rule": body_rule,
                },
                "warnings": [],
                "errors": [],
            },
            status=201,
        )


class LocalAutomationRuleUpdateUseCase:
    """Update a local automation rule from canonical API payloads."""

    def __init__(self, rules: LocalAutomationRuleStorePort) -> None:
        self._rules = rules

    def execute(self, rule_id: str, payload: dict[str, Any]) -> BridgeResponse:
        """Replace an existing local automation rule."""
        rule_payload = dict(payload)
        rule_payload["rule_id"] = rule_id
        rule = _rule_from_payload(rule_payload)
        if rule is None:
            return _rule_error_response(
                "invalid_rule",
                message="Invalid local automation rule",
                status=400,
                target="rule",
            )
        rule_exists = any(
            existing.rule_id == rule.rule_id for existing in self._rules.list_rules()
        )
        if not self._rules.update_rule(rule):
            if rule_exists:
                return _rule_error_response(
                    "rule_persistence_failed",
                    message="Local automation rule could not be persisted",
                    status=500,
                    target="rule",
                )
            return _rule_error_response(
                "rule_not_found",
                message="Local automation rule not found",
                status=404,
                target="rule.rule_id",
            )
        body_rule = _rule_payload(rule)
        return BridgeResponse(
            {
                "success": True,
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "status": "updated",
                "rule_id": rule.rule_id,
                "rule": body_rule,
                "data": {
                    "status": "updated",
                    "rule": body_rule,
                },
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


class LocalAutomationRuleDeleteUseCase:
    """Delete a local automation rule by canonical rule ID."""

    def __init__(self, rules: LocalAutomationRuleStorePort) -> None:
        self._rules = rules

    def execute(self, rule_id: str) -> BridgeResponse:
        """Remove an existing local automation rule."""
        if not rule_id:
            return _rule_error_response(
                "invalid_rule",
                message="Invalid local automation rule",
                status=400,
                target="rule.rule_id",
            )
        rule_exists = any(
            existing.rule_id == rule_id for existing in self._rules.list_rules()
        )
        if not self._rules.delete_rule(rule_id):
            if rule_exists:
                return _rule_error_response(
                    "rule_persistence_failed",
                    message="Local automation rule could not be persisted",
                    status=500,
                    target="rule",
                )
            return _rule_error_response(
                "rule_not_found",
                message="Local automation rule not found",
                status=404,
                target="rule.rule_id",
            )
        return BridgeResponse(
            {
                "success": True,
                "schema_version": SMARTLY_API_SCHEMA_VERSION,
                "status": "deleted",
                "rule_id": rule_id,
                "data": {
                    "status": "deleted",
                    "rule_id": rule_id,
                },
                "warnings": [],
                "errors": [],
            },
            status=200,
        )


class LocalAutomationUseCase:
    """Run local automation rules for canonical device events."""

    def __init__(
        self,
        rules: LocalAutomationRuleStorePort,
        command_executor: SmartlyCommandExecutorPort,
        *,
        command_id_factory: CommandIdFactory | None = None,
    ) -> None:
        self._rules = rules
        self._command_executor = command_executor
        self._command_id_factory = command_id_factory or _automation_command_id

    async def handle_device_event(
        self,
        client_id: str,
        event: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Execute local automation actions matching a canonical event."""
        results: list[dict[str, Any]] = []
        for rule in self._rules.list_rules():
            if not rule.enabled or not _event_matches_trigger(event, rule.trigger):
                continue
            for index, action in enumerate(rule.actions):
                if action.type != "device_command":
                    continue
                command_id = self._command_id_factory(event, rule, index)
                response = await self._command_executor.execute(
                    client_id,
                    SmartlyCommand(
                        command_id=command_id,
                        device_id=action.device_id,
                        capability=action.capability,
                        command=action.command,
                        params=action.params,
                        source={
                            "automation_rule_id": rule.rule_id,
                            "event_id": event["event_id"],
                        },
                    ),
                )
                results.append(
                    {
                        "rule_id": rule.rule_id,
                        "action_index": index,
                        "type": action.type,
                        "command_id": command_id,
                        "status": response.body.get("status", "unknown"),
                        "response_status": response.status,
                    }
                )
        return results


def _event_matches_trigger(event: dict[str, Any], trigger: AutomationTrigger) -> bool:
    """Return whether a canonical event satisfies a rule trigger."""
    if event.get("device_id") != trigger.device_id:
        return False
    if event.get("capability") != trigger.capability:
        return False
    if event.get("event") != trigger.event:
        return False
    payload = event.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    return all(payload.get(key) == value for key, value in trigger.payload.items())


def _automation_command_id(
    event: dict[str, Any],
    rule: LocalAutomationRule,
    index: int,
) -> str:
    """Return a deterministic command ID for an automation action."""
    return f"auto_{event['event_id']}_{rule.rule_id}_{index}"


def _rule_payload(rule: LocalAutomationRule) -> dict[str, Any]:
    """Return a serializable canonical automation rule payload."""
    return {
        "rule_id": rule.rule_id,
        "enabled": rule.enabled,
        "trigger": {
            "device_id": rule.trigger.device_id,
            "capability": rule.trigger.capability,
            "event": rule.trigger.event,
            "payload": dict(rule.trigger.payload),
        },
        "actions": [
            {
                "type": action.type,
                "device_id": action.device_id,
                "capability": action.capability,
                "command": action.command,
                "params": dict(action.params),
            }
            for action in rule.actions
        ],
    }


def _rule_from_payload(value: dict[str, Any]) -> LocalAutomationRule | None:
    """Return a local automation rule from a canonical API payload."""
    if not isinstance(value, dict):
        return None
    rule_id = value.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id:
        return None
    trigger = _trigger_from_payload(value.get("trigger"))
    if trigger is None:
        return None
    actions = [
        action
        for item in value.get("actions", [])
        if (action := _action_from_payload(item)) is not None
    ]
    if not actions:
        return None
    return LocalAutomationRule(
        rule_id=rule_id,
        trigger=trigger,
        actions=actions,
        enabled=value.get("enabled", True) is not False,
    )


def _trigger_from_payload(value: Any) -> AutomationTrigger | None:
    """Return an automation trigger from a canonical API payload."""
    if not isinstance(value, dict):
        return None
    device_id = value.get("device_id")
    capability = value.get("capability")
    event = value.get("event")
    if not all(isinstance(item, str) and item for item in (device_id, capability, event)):
        return None
    payload = value.get("payload", {})
    return AutomationTrigger(
        device_id=device_id,
        capability=capability,
        event=event,
        payload=payload if isinstance(payload, dict) else {},
    )


def _action_from_payload(value: Any) -> AutomationAction | None:
    """Return an automation action from a canonical API payload."""
    if not isinstance(value, dict):
        return None
    action_type = value.get("type")
    device_id = value.get("device_id")
    capability = value.get("capability")
    command = value.get("command")
    if not all(
        isinstance(item, str) and item
        for item in (action_type, device_id, capability, command)
    ):
        return None
    params = value.get("params", {})
    return AutomationAction(
        type=action_type,
        device_id=device_id,
        capability=capability,
        command=command,
        params=params if isinstance(params, dict) else {},
    )


def _rule_error_response(
    error: str,
    *,
    message: str,
    status: int,
    target: str,
) -> BridgeResponse:
    """Return a local automation API vNext error response."""
    return local_automation_rule_error_response(
        error,
        message=message,
        status=status,
        target=target,
    )


def local_automation_rule_error_response(
    error: str,
    *,
    message: str,
    status: int,
    target: str,
) -> BridgeResponse:
    """Return a local automation API vNext error response."""
    return BridgeResponse(
        {
            "error": error,
            "message": message,
            "schema_version": SMARTLY_API_SCHEMA_VERSION,
            "data": {
                "status": "rejected",
            },
            "warnings": [],
            "errors": [
                {
                    "code": error,
                    "message": message,
                    "target": target,
                }
            ],
        },
        status=status,
    )
