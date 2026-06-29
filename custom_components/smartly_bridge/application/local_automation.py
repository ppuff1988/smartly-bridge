"""Local automation application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .control import SmartlyCommand
from .ports import LocalAutomationRuleStorePort, SmartlyCommandExecutorPort


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
