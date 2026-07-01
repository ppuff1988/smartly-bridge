"""Home Assistant adapters for application ports."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ..acl import (
    get_allowed_entities,
    get_entity_domain,
    get_structure,
    is_entity_allowed,
    is_service_allowed,
)
from ..audit import log_control, log_deny
from ..application.control import SmartlyCommand, SmartlyCommandUseCase
from ..application.local_automation import (
    AutomationAction,
    AutomationTrigger,
    LocalAutomationRule,
)
from ..application.logical_devices import (
    canonical_capability_name,
    logical_device_id_for_source_id,
)
from ..const import (
    BRIDGE_CHART_LOOKBACK_HOURS,
    DEFAULT_DOMAIN_ICONS,
    DOMAIN,
    MAX_CONCURRENT_HISTORY_QUERIES,
    RAW_DIAGNOSTIC_TTL,
)
from ..device_presentation import build_device_card_metadata
from ..domain.models import CameraSnapshot, CameraStreamInfo, EntityStateSnapshot
from ..utils import (
    build_bridge_chart_from_states,
    format_numeric_attributes,
    format_sensor_state,
    numeric_state_value,
    signal_attribute_key_for_entity,
)

DEVICE_EVENT_TYPE = "smartly_bridge_device_event"


def _entry_labels(entry: Any) -> set[str]:
    """Return string labels from a Home Assistant entity registry entry."""
    labels = getattr(entry, "labels", None)
    if labels is None:
        return set()
    if isinstance(labels, (set, list, tuple)):
        return {label for label in labels if isinstance(label, str)}
    return set()


def _history_end_time(value: Any) -> datetime:
    """Return a timezone-aware history query end time."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.now(timezone.utc)


def _setting_key_for_entity(entity_id: str, name: str, domain: str) -> str | None:
    """Return the Smartly setting key for supported sibling setting entities."""
    haystack = f"{entity_id} {name}".lower()
    if domain == "number" and any(
        token in haystack for token in ("cooldown", "cooldown_seconds", "冷卻")
    ):
        return "cooldown_seconds"
    if domain == "number" and any(
        token in haystack
        for token in (
            "delay",
            "duration",
            "hold",
            "timeout",
            "occupancy_timeout",
            "trigger",
            "second",
            "秒",
            "維持",
        )
    ):
        return "trigger_hold_seconds"
    if domain == "select" and any(
        token in haystack for token in ("sensitivity", "occupancy_sensitivity", "感應強度")
    ):
        return "occupancy_sensitivity"
    return None


def _number_setting_control(
    entity_id: str,
    key: str,
    state: Any,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    """Build a number setting control descriptor."""
    control: dict[str, Any] = {
        "key": key,
        "entity_id": entity_id,
        "domain": "number",
        "name": attributes.get("friendly_name", entity_id),
        "action": "set_value",
        "value": numeric_state_value(getattr(state, "state", None)),
    }
    for source, target in (("min", "min"), ("max", "max"), ("step", "step")):
        value = numeric_state_value(attributes.get(source))
        if value is not None:
            control[target] = value
    unit = attributes.get("unit_of_measurement")
    if unit:
        control["unit"] = unit
    return control


def _select_setting_control(
    entity_id: str,
    key: str,
    state: Any,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    """Build a select setting control descriptor."""
    control: dict[str, Any] = {
        "key": key,
        "entity_id": entity_id,
        "domain": "select",
        "name": attributes.get("friendly_name", entity_id),
        "action": "select_option",
        "value": getattr(state, "state", None),
    }
    options = attributes.get("options")
    if isinstance(options, list):
        control["options"] = options
    return control


class LoggingAuditAdapter:
    """Audit adapter backed by the existing logging helpers."""

    def __init__(self, logger: Any) -> None:
        self._logger = logger

    def deny(
        self,
        client_id: str,
        entity_id: str,
        service: str,
        reason: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Record a denied operation."""
        log_deny(
            self._logger,
            client_id=client_id,
            entity_id=entity_id,
            service=service,
            reason=reason,
            actor=actor,
        )

    def control(
        self,
        client_id: str,
        entity_id: str,
        service: str,
        result: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Record a control operation."""
        log_control(
            self._logger,
            client_id=client_id,
            entity_id=entity_id,
            service=service,
            result=result,
            actor=actor,
        )


class HomeAssistantDeviceEventPublisher:
    """Device event publisher backed by the Home Assistant event bus."""

    def __init__(self, hass: Any) -> None:
        self._hass = hass

    def publish_device_event(self, event_data: dict[str, Any]) -> None:
        """Publish a normalized Smartly device event."""
        self._hass.bus.async_fire(DEVICE_EVENT_TYPE, event_data)


class InMemoryDeviceEventDeduplicator:
    """In-memory event dedupe store scoped to a Home Assistant runtime."""

    def __init__(self) -> None:
        self._event_ids_by_key: dict[str, str] = {}

    def event_id_for_key(self, key: str) -> str | None:
        """Return an existing event ID for the idempotency key."""
        return self._event_ids_by_key.get(key)

    def remember_event(self, key: str, event_id: str) -> None:
        """Remember the event ID for the idempotency key."""
        self._event_ids_by_key.setdefault(key, event_id)


def _home_assistant_device_event_publisher(hass: Any) -> HomeAssistantDeviceEventPublisher:
    """Build the Home Assistant-backed legacy device event publisher."""
    return HomeAssistantDeviceEventPublisher(hass)


def _in_memory_device_event_deduplicator() -> InMemoryDeviceEventDeduplicator:
    """Build the legacy in-memory device event deduplicator."""
    return InMemoryDeviceEventDeduplicator()


class HomeAssistantLocalAutomationRuleStore:
    """Local automation rule store backed by Home Assistant runtime data."""

    def __init__(self, hass: Any) -> None:
        self._hass = hass

    def list_rules(self) -> list[LocalAutomationRule]:
        """Return local automation rules registered in the integration runtime."""
        integration_data = self._hass.data.get(DOMAIN, {})
        rules = integration_data.get("local_automation_rules")
        if rules is None:
            config_entry = integration_data.get("config_entry")
            data = getattr(config_entry, "data", {}) if config_entry else {}
            rules = data.get("local_automation_rules", [])
        return [
            parsed
            for rule in rules
            if (parsed := _local_automation_rule_from_config(rule)) is not None
        ]

    def create_rule(self, rule: LocalAutomationRule) -> bool:
        """Persist a local automation rule to the Home Assistant config entry."""
        integration_data = self._hass.data.get(DOMAIN, {})
        config_entry = integration_data.get("config_entry")
        if config_entry is None:
            return False
        data = dict(getattr(config_entry, "data", {}))
        stored_rules = self._serialized_rules_for_persistence(integration_data, data)
        stored_rules.append(_local_automation_rule_to_config(rule))
        data["local_automation_rules"] = stored_rules
        try:
            self._hass.config_entries.async_update_entry(config_entry, data=data)
        except Exception:
            return False
        self._refresh_runtime_rules(integration_data, stored_rules)
        return True

    def update_rule(self, rule: LocalAutomationRule) -> bool:
        """Replace a local automation rule in the Home Assistant config entry."""
        integration_data = self._hass.data.get(DOMAIN, {})
        config_entry = integration_data.get("config_entry")
        if config_entry is None:
            return False
        data = dict(getattr(config_entry, "data", {}))
        stored_rules = self._serialized_rules_for_persistence(integration_data, data)
        updated = False
        serialized_rule = _local_automation_rule_to_config(rule)
        for index, stored_rule in enumerate(stored_rules):
            if isinstance(stored_rule, dict) and stored_rule.get("rule_id") == rule.rule_id:
                stored_rules[index] = serialized_rule
                updated = True
                break
        if not updated:
            return False
        data["local_automation_rules"] = stored_rules
        try:
            self._hass.config_entries.async_update_entry(config_entry, data=data)
        except Exception:
            return False
        self._refresh_runtime_rules(integration_data, stored_rules)
        return True

    def delete_rule(self, rule_id: str) -> bool:
        """Remove a local automation rule from the Home Assistant config entry."""
        integration_data = self._hass.data.get(DOMAIN, {})
        config_entry = integration_data.get("config_entry")
        if config_entry is None:
            return False
        data = dict(getattr(config_entry, "data", {}))
        stored_rules = self._serialized_rules_for_persistence(integration_data, data)
        remaining_rules = [
            stored_rule
            for stored_rule in stored_rules
            if not (
                isinstance(stored_rule, dict)
                and stored_rule.get("rule_id") == rule_id
            )
        ]
        if len(remaining_rules) == len(stored_rules):
            return False
        data["local_automation_rules"] = remaining_rules
        try:
            self._hass.config_entries.async_update_entry(config_entry, data=data)
        except Exception:
            return False
        self._refresh_runtime_rules(integration_data, remaining_rules)
        return True

    def _serialized_rules_for_persistence(
        self,
        integration_data: dict[str, Any],
        config_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return the current rule set as serialized config data."""
        if "local_automation_rules" in integration_data:
            return [_local_automation_rule_to_config(rule) for rule in self.list_rules()]
        return list(config_data.get("local_automation_rules", []))

    def _refresh_runtime_rules(
        self,
        integration_data: dict[str, Any],
        serialized_rules: list[dict[str, Any]],
    ) -> None:
        """Make persisted rule changes visible to runtime readers immediately."""
        integration_data["local_automation_rules"] = list(serialized_rules)


def _local_automation_rule_from_config(value: Any) -> LocalAutomationRule | None:
    """Return a local automation rule from runtime or serialized config data."""
    if isinstance(value, LocalAutomationRule):
        return value
    if not isinstance(value, dict):
        return None
    trigger = _automation_trigger_from_config(value.get("trigger"))
    if trigger is None:
        return None
    actions = [
        action
        for item in value.get("actions", [])
        if (action := _automation_action_from_config(item)) is not None
    ]
    if not actions:
        return None
    rule_id = value.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id:
        return None
    return LocalAutomationRule(
        rule_id=rule_id,
        trigger=trigger,
        actions=actions,
        enabled=value.get("enabled", True) is not False,
    )


def _automation_trigger_from_config(value: Any) -> AutomationTrigger | None:
    """Return an automation trigger from serialized config data."""
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


def _automation_action_from_config(value: Any) -> AutomationAction | None:
    """Return an automation action from serialized config data."""
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


def _local_automation_rule_to_config(rule: LocalAutomationRule) -> dict[str, Any]:
    """Return serialized config entry data for a local automation rule."""
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


def _home_assistant_local_automation_rule_store(hass: Any) -> HomeAssistantLocalAutomationRuleStore:
    """Build the Home Assistant-backed legacy local automation rule store."""
    return HomeAssistantLocalAutomationRuleStore(hass)


def _smartly_command_use_case(hass: Any, logger: Any) -> SmartlyCommandUseCase:
    """Build the Home Assistant-backed canonical command use case."""
    return SmartlyCommandUseCase(
        HomeAssistantEntityPolicy(hass),
        HomeAssistantControlGateway(hass),
        LoggingAuditAdapter(logger),
        HomeAssistantCommandTargetResolver(hass),
    )


def _home_assistant_history_gateway(
    hass: Any,
    history_semaphore_factory: Callable[[], Any],
) -> Any:
    """Build the Home Assistant-backed legacy history gateway."""
    return HomeAssistantHistoryGateway(hass, history_semaphore_factory)


def _state_sync_history_gateway(
    hass: Any,
    history_semaphore_factory: Callable[[], Any],
) -> Any:
    """Build the Home Assistant-backed history gateway for state sync charts."""
    return _home_assistant_history_gateway(hass, history_semaphore_factory)


class HomeAssistantSmartlyCommandExecutor:
    """SmartlyCommand executor backed by Home Assistant control adapters."""

    def __init__(
        self,
        hass: Any,
        logger: Any,
        *,
        use_case_factory: Callable[[Any, Any], Any] = _smartly_command_use_case,
    ) -> None:
        self._hass = hass
        self._logger = logger
        self._use_case_factory = use_case_factory

    async def execute(self, client_id: str, command: SmartlyCommand) -> Any:
        """Execute a canonical Smartly command through Home Assistant."""
        return await self._use_case_factory(self._hass, self._logger).execute(
            client_id,
            command,
        )


def _home_assistant_smartly_command_executor(
    hass: Any, logger: Any
) -> HomeAssistantSmartlyCommandExecutor:
    """Build the Home Assistant-backed legacy SmartlyCommand executor."""
    return HomeAssistantSmartlyCommandExecutor(hass, logger)


class HomeAssistantEntityPolicy:
    """Entity and service policy backed by Home Assistant registries."""

    def __init__(
        self,
        hass: Any,
        *,
        entity_allowed_fn: Callable[[Any, str, Any], bool] = is_entity_allowed,
        service_allowed_fn: Callable[[str, str], bool] = is_service_allowed,
    ) -> None:
        self._hass = hass
        self._entity_allowed_fn = entity_allowed_fn
        self._service_allowed_fn = service_allowed_fn

    def is_entity_allowed(self, entity_id: str) -> bool:
        """Return whether an entity can be accessed by Platform."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self._hass)
        if self._entity_allowed_fn(self._hass, entity_id, entity_registry):
            return True
        return self._is_allowed_setting_sibling(entity_id, entity_registry)

    def is_service_allowed(self, entity_id: str, action: str) -> bool:
        """Return whether an action is allowed for the entity domain."""
        return self._service_allowed_fn(get_entity_domain(entity_id), action)

    def _is_allowed_setting_sibling(
        self,
        entity_id: str,
        entity_registry: Any,
    ) -> bool:
        """Return whether an editable setting belongs to an allowed primary entity."""
        domain = get_entity_domain(entity_id)
        if domain not in {"number", "select"}:
            return False
        entry = entity_registry.async_get(entity_id)
        device_id = getattr(entry, "device_id", None) if entry else None
        if not device_id:
            return False
        state = self._hass.states.get(entity_id)
        if state is None:
            return False
        attributes = format_numeric_attributes(dict(getattr(state, "attributes", {}) or {}))
        name = str(attributes.get("friendly_name", entity_id))
        if _setting_key_for_entity(entity_id, name, domain) is None:
            return False
        for sibling_entity_id, sibling in getattr(entity_registry, "entities", {}).items():
            if getattr(sibling, "device_id", None) != device_id:
                continue
            if self._entity_allowed_fn(self._hass, sibling_entity_id, entity_registry):
                return True
        return False


class HomeAssistantControlGateway:
    """Control gateway backed by Home Assistant services."""

    def __init__(self, hass: Any, *, sleep_seconds: float = 0.1) -> None:
        self._hass = hass
        self._sleep_seconds = sleep_seconds

    def get_state(self, entity_id: str) -> EntityStateSnapshot | None:
        """Return the current entity state snapshot."""
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        return EntityStateSnapshot(
            entity_id=entity_id,
            state=state.state,
            attributes=format_numeric_attributes(dict(state.attributes)),
        )

    async def call_service(
        self, entity_id: str, action: str, service_data: dict[str, Any]
    ) -> EntityStateSnapshot | None:
        """Call a service and return the updated entity state."""
        domain = get_entity_domain(entity_id)
        await self._hass.services.async_call(
            domain,
            action,
            {"entity_id": entity_id, **service_data},
            blocking=True,
        )
        await asyncio.sleep(self._sleep_seconds)

        return self.get_state(entity_id)


class HomeAssistantCommandTargetResolver:
    """Resolve Smartly logical-device commands to Home Assistant entities."""

    def __init__(
        self,
        hass: Any,
        *,
        allowed_entities_fn: Callable[[Any, Any], list[str]] | None = None,
    ) -> None:
        self._hass = hass
        self._allowed_entities_fn = allowed_entities_fn or get_allowed_entities

    def resolve_command_target(
        self,
        device_id: str,
        capability: str,
        params: dict[str, Any] | None = None,
    ) -> str | None:
        """Return the HA entity that owns the requested logical capability."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self._hass)
        allowed_entities = self._allowed_entities_fn(self._hass, entity_registry)
        matched_device_ids: set[str] = set()
        for entity_id in allowed_entities:
            entry = entity_registry.async_get(entity_id)
            source_device_id = getattr(entry, "device_id", None) if entry else None
            if not isinstance(source_device_id, str):
                source_device_id = entity_id
            if logical_device_id_for_source_id(source_device_id) != device_id:
                continue
            matched_device_ids.add(source_device_id)

            state = self._hass.states.get(entity_id)
            attributes = format_numeric_attributes(dict(getattr(state, "attributes", {}) or {}))
            metadata = build_device_card_metadata(
                entity_id,
                getattr(state, "state", None) if state else None,
                attributes,
                _entry_labels(entry),
            )
            canonical_capabilities = {
                canonical_capability_name(item) for item in metadata["capabilities"]
            }
            if capability in canonical_capabilities:
                return entity_id
        if capability in {"numeric_setting", "option_setting"}:
            setting_key = params.get("key") if isinstance(params, dict) else None
            return self._resolve_setting_target(
                entity_registry,
                matched_device_ids,
                domain="number" if capability == "numeric_setting" else "select",
                setting_key=setting_key if isinstance(setting_key, str) else None,
            )
        return None

    def _resolve_setting_target(
        self,
        entity_registry: Any,
        matched_device_ids: set[str],
        *,
        domain: str,
        setting_key: str | None = None,
    ) -> str | None:
        """Return a sibling setting entity from an allowed logical-device group."""
        if not matched_device_ids:
            return None
        for registry_entity_id, sibling in getattr(entity_registry, "entities", {}).items():
            entity_id = getattr(sibling, "entity_id", None) or registry_entity_id
            if not isinstance(entity_id, str):
                entity_id = registry_entity_id if isinstance(registry_entity_id, str) else None
            if not entity_id or get_entity_domain(entity_id) != domain:
                continue
            source_device_id = getattr(sibling, "device_id", None)
            if source_device_id not in matched_device_ids:
                continue
            state = self._hass.states.get(entity_id)
            if state is None:
                continue
            attributes = format_numeric_attributes(dict(getattr(state, "attributes", {}) or {}))
            name = str(attributes.get("friendly_name", entity_id))
            resolved_key = _setting_key_for_entity(entity_id, name, domain)
            if setting_key is not None and resolved_key != setting_key:
                continue
            if resolved_key is not None:
                return entity_id
        return None


class HomeAssistantSyncGateway:
    """Structure sync gateway backed by Home Assistant registries."""

    def __init__(
        self,
        hass: Any,
        *,
        allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
        structure_fn: Callable[
            [Any, list[str], Any, Any, Any, Any], dict[str, Any]
        ] = get_structure,
    ) -> None:
        self._hass = hass
        self._allowed_entities_fn = allowed_entities_fn
        self._structure_fn = structure_fn

    def get_structure(self) -> dict[str, Any]:
        """Return the allowed structure payload."""
        from homeassistant.helpers import area_registry as ar
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers import floor_registry as fr

        entity_registry = er.async_get(self._hass)
        allowed_entities = self._allowed_entities_fn(self._hass, entity_registry)
        return self._structure_fn(
            self._hass,
            allowed_entities,
            entity_registry,
            dr.async_get(self._hass),
            ar.async_get(self._hass),
            fr.async_get(self._hass),
        )


def _home_assistant_sync_structure_gateway(
    hass: Any,
    *,
    allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
    structure_fn: Callable[[Any, list[str], Any, Any, Any, Any], dict[str, Any]] = get_structure,
) -> HomeAssistantSyncGateway:
    """Build the Home Assistant-backed legacy sync structure gateway."""
    return HomeAssistantSyncGateway(
        hass,
        allowed_entities_fn=allowed_entities_fn,
        structure_fn=structure_fn,
    )


class HomeAssistantRawDiagnosticStore:
    """Raw diagnostic store backed by Home Assistant runtime data."""

    def __init__(
        self,
        hass: Any,
        *,
        ttl_seconds: int = RAW_DIAGNOSTIC_TTL,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._hass = hass
        self._ttl_seconds = ttl_seconds
        self._now_fn = now_fn

    def get_raw_diagnostic(self, raw_ref: str) -> dict[str, Any] | None:
        """Return a raw diagnostic payload registered for a raw reference."""
        raw_diagnostics = self._raw_diagnostics()
        if not isinstance(raw_diagnostics, dict):
            return None
        entry = raw_diagnostics.get(raw_ref)
        if not isinstance(entry, dict):
            return None
        if self._is_wrapped_entry(entry):
            expires_at = entry["expires_at"]
            if isinstance(expires_at, (int, float)) and expires_at < self._now_fn():
                raw_diagnostics.pop(raw_ref, None)
                return None
            payload = entry["payload"]
            return payload if isinstance(payload, dict) else None
        payload = entry
        return payload

    def record_raw_diagnostic(self, raw_ref: str, payload: dict[str, Any]) -> None:
        """Record a raw diagnostic payload for a reference."""
        self._raw_diagnostics()[raw_ref] = {
            "payload": payload,
            "expires_at": self._now_fn() + self._ttl_seconds,
        }

    @staticmethod
    def _is_wrapped_entry(entry: dict[str, Any]) -> bool:
        """Return whether a raw diagnostic entry has store metadata."""
        return "payload" in entry and "expires_at" in entry

    def _raw_diagnostics(self) -> dict[str, Any]:
        """Return the runtime raw diagnostic mapping."""
        integration_data = self._hass.data.setdefault(DOMAIN, {})
        raw_diagnostics = integration_data.setdefault("raw_diagnostics", {})
        if not isinstance(raw_diagnostics, dict):
            raw_diagnostics = {}
            integration_data["raw_diagnostics"] = raw_diagnostics
        return raw_diagnostics


def _home_assistant_raw_diagnostic_store(hass: Any) -> HomeAssistantRawDiagnosticStore:
    """Build the Home Assistant-backed legacy raw diagnostic store."""
    return HomeAssistantRawDiagnosticStore(hass)


class HomeAssistantStateSyncGateway:
    """State sync gateway backed by Home Assistant state and entity registries."""

    def __init__(
        self,
        hass: Any,
        *,
        allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
        history_semaphore_factory: Callable[[], Any] | None = None,
        history_gateway_factory: Callable[
            [Any, Callable[[], Any]], Any
        ] = _state_sync_history_gateway,
    ) -> None:
        self._hass = hass
        self._allowed_entities_fn = allowed_entities_fn
        self._history_semaphore = asyncio.Semaphore(MAX_CONCURRENT_HISTORY_QUERIES)
        self._history_semaphore_factory = history_semaphore_factory or self._get_history_semaphore
        self._history_gateway_factory = history_gateway_factory

    async def list_states(self) -> list[EntityStateSnapshot]:
        """Return allowed entity state snapshots."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self._hass)
        allowed_entities = self._allowed_entities_fn(self._hass, entity_registry)
        signal_by_device = self._signal_attributes_by_device(allowed_entities, entity_registry)
        setting_controls_by_device = self._setting_controls_by_device(
            allowed_entities,
            entity_registry,
        )

        snapshots: list[EntityStateSnapshot] = []
        for entity_id in allowed_entities:
            state = self._hass.states.get(entity_id)
            if state is None:
                continue

            entry = entity_registry.async_get(entity_id)
            icon = state.attributes.get("icon")
            if not icon and entry:
                icon = entry.icon or entry.original_icon
            if not icon:
                icon = DEFAULT_DOMAIN_ICONS.get(get_entity_domain(entity_id))

            raw_attributes = dict(state.attributes)
            device_id = getattr(entry, "device_id", None) if entry else None
            if not isinstance(device_id, str):
                device_id = None
            if device_id and device_id in signal_by_device:
                for key, value in signal_by_device[device_id].items():
                    raw_attributes.setdefault(key, value)
            attributes = format_numeric_attributes(raw_attributes)
            labels = _entry_labels(entry)
            card_metadata = build_device_card_metadata(
                entity_id,
                state.state,
                attributes,
                labels,
            )
            if (
                device_id
                and card_metadata["device_class"] == "presence_sensor"
                and device_id in setting_controls_by_device
            ):
                card_metadata["presentation"]["setting_controls"] = setting_controls_by_device[
                    device_id
                ]
            bridge_chart = await self._bridge_chart_for_state(entity_id, state, attributes)

            snapshots.append(
                EntityStateSnapshot(
                    entity_id=entity_id,
                    state=format_sensor_state(state.state, state.attributes),
                    attributes=attributes,
                    last_changed=state.last_changed.isoformat() if state.last_changed else None,
                    last_updated=state.last_updated.isoformat() if state.last_updated else None,
                    icon=icon,
                    bridge_chart=bridge_chart,
                    source_device_id=device_id,
                    **card_metadata,
                )
            )
        return snapshots

    def _signal_attributes_by_device(
        self,
        entity_ids: list[str],
        entity_registry: Any,
    ) -> dict[str, dict[str, int | float]]:
        """Return signal attributes exposed by diagnostic sibling entities."""
        allowed_device_ids: set[str] = set()
        for entity_id in entity_ids:
            entry = entity_registry.async_get(entity_id)
            device_id = getattr(entry, "device_id", None) if entry else None
            if device_id:
                allowed_device_ids.add(device_id)

        if not allowed_device_ids:
            return {}

        signal_by_device: dict[str, dict[str, int | float]] = {}
        for registry_entity_id, sibling in getattr(entity_registry, "entities", {}).items():
            entity_id = getattr(sibling, "entity_id", None) or registry_entity_id
            if not isinstance(entity_id, str):
                entity_id = registry_entity_id if isinstance(registry_entity_id, str) else None
            device_id = getattr(sibling, "device_id", None)
            if not entity_id or device_id not in allowed_device_ids:
                continue

            key = signal_attribute_key_for_entity(entity_id)
            if key is None:
                continue

            state = self._hass.states.get(entity_id)
            value = numeric_state_value(getattr(state, "state", None) if state else None)
            if value is None:
                continue

            signal_by_device.setdefault(device_id, {})[key] = value
        return signal_by_device

    def _setting_controls_by_device(
        self,
        entity_ids: list[str],
        entity_registry: Any,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return editable number/select setting controls from sibling entities."""
        allowed_device_ids: set[str] = set()
        for entity_id in entity_ids:
            entry = entity_registry.async_get(entity_id)
            device_id = getattr(entry, "device_id", None) if entry else None
            if device_id:
                allowed_device_ids.add(device_id)

        if not allowed_device_ids:
            return {}

        controls_by_device: dict[str, list[dict[str, Any]]] = {}
        for registry_entity_id, sibling in getattr(entity_registry, "entities", {}).items():
            entity_id = getattr(sibling, "entity_id", None) or registry_entity_id
            if not isinstance(entity_id, str):
                entity_id = registry_entity_id if isinstance(registry_entity_id, str) else None
            device_id = getattr(sibling, "device_id", None)
            domain = get_entity_domain(entity_id or "")
            if (
                not entity_id
                or device_id not in allowed_device_ids
                or domain not in {"number", "select"}
            ):
                continue

            state = self._hass.states.get(entity_id)
            if state is None:
                continue

            attributes = format_numeric_attributes(dict(state.attributes))
            name = str(attributes.get("friendly_name", entity_id))
            key = _setting_key_for_entity(entity_id, name, domain)
            if key is None:
                continue

            if domain == "number":
                control = _number_setting_control(entity_id, key, state, attributes)
            else:
                control = _select_setting_control(entity_id, key, state, attributes)

            controls_by_device.setdefault(device_id, []).append(control)

        order = {
            "trigger_hold_seconds": 0,
            "cooldown_seconds": 1,
            "occupancy_sensitivity": 2,
        }
        for controls in controls_by_device.values():
            controls.sort(key=lambda control: order.get(str(control.get("key")), 99))
        return controls_by_device

    def _get_history_semaphore(self) -> asyncio.Semaphore:
        """Return the recorder query semaphore for bridge chart preloading."""
        return self._history_semaphore

    async def _bridge_chart_for_state(
        self,
        entity_id: str,
        state: Any,
        attributes: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Return recent bridge chart history for an eligible sensor."""
        device_class = attributes.get("device_class")
        unit = attributes.get("unit_of_measurement")
        fallback_timestamp = state.last_updated.isoformat() if state.last_updated else None
        fallback_chart = build_bridge_chart_from_states(
            [],
            device_class,
            unit,
            fallback_state=state.state,
            fallback_timestamp=fallback_timestamp,
        )
        if fallback_chart is None:
            return None

        end_time = _history_end_time(getattr(state, "last_updated", None))
        start_time = end_time - timedelta(hours=BRIDGE_CHART_LOOKBACK_HOURS)
        history_gateway = self._history_gateway_factory(
            self._hass,
            self._history_semaphore_factory,
        )
        history_states = await history_gateway.query_states(
            entity_id,
            start_time,
            end_time,
            significant_changes_only=True,
        )
        return (
            build_bridge_chart_from_states(
                history_states,
                device_class,
                unit,
                fallback_state=state.state,
                fallback_timestamp=fallback_timestamp,
            )
            or fallback_chart
        )


def _home_assistant_sync_states_gateway(
    hass: Any,
    *,
    allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
    history_semaphore_factory: Callable[[], Any] | None = None,
    history_gateway_factory: Callable[
        [Any, Callable[[], Any]], Any
    ] = _state_sync_history_gateway,
) -> HomeAssistantStateSyncGateway:
    """Build the Home Assistant-backed legacy sync states gateway."""
    return HomeAssistantStateSyncGateway(
        hass,
        allowed_entities_fn=allowed_entities_fn,
        history_semaphore_factory=history_semaphore_factory,
        history_gateway_factory=history_gateway_factory,
    )


class HomeAssistantCameraGateway:
    """Camera gateway backed by Home Assistant state and CameraManager."""

    def __init__(
        self,
        hass: Any,
        camera_manager: Any,
        *,
        allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
    ) -> None:
        self._hass = hass
        self._camera_manager = camera_manager
        self._allowed_entities_fn = allowed_entities_fn

    def list_allowed_camera_ids(self) -> list[str]:
        """Return allowed camera entity IDs."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self._hass)
        return [
            entity_id
            for entity_id in self._allowed_entities_fn(self._hass, entity_registry)
            if entity_id.startswith("camera.")
        ]

    def get_camera_state(self, entity_id: str) -> dict[str, Any] | None:
        """Return camera state metadata."""
        state = self._hass.states.get(entity_id)
        if state is None:
            return None

        return {
            "entity_id": entity_id,
            "name": state.attributes.get("friendly_name", entity_id),
            "state": state.state,
            "is_streaming": state.attributes.get("is_streaming", False),
            "brand": state.attributes.get("brand"),
            "model": state.attributes.get("model_name"),
            "supported_features": state.attributes.get("supported_features", 0),
        }

    async def get_stream_info(self, entity_id: str) -> CameraStreamInfo | None:
        """Return camera stream capabilities."""
        if self._camera_manager is None:
            return None

        stream_info = await self._camera_manager.get_stream_info(entity_id)
        if stream_info is None:
            return None

        return CameraStreamInfo(
            entity_id=stream_info.entity_id,
            name=stream_info.name,
            supports_snapshot=stream_info.supports_snapshot,
            supports_mjpeg=stream_info.supports_mjpeg,
            supports_hls=stream_info.supports_hls,
            supports_webrtc=stream_info.supports_webrtc,
            is_streaming=stream_info.is_streaming,
        )

    def get_cache_stats(self) -> dict[str, Any]:
        """Return camera snapshot cache statistics."""
        if self._camera_manager is None:
            return {}
        return self._camera_manager.get_cache_stats()

    def get_hls_stats(self) -> dict[str, Any]:
        """Return HLS statistics."""
        if self._camera_manager is None:
            return {}
        return self._camera_manager.get_hls_stats()

    def register_camera(self, config: dict[str, Any]) -> None:
        """Register a camera configuration."""
        from ..camera import CameraConfig

        self._camera_manager.register_camera(CameraConfig(**config))

    def unregister_camera(self, entity_id: str) -> None:
        """Unregister a camera configuration."""
        self._camera_manager.unregister_camera(entity_id)

    async def clear_cache(self, entity_id: str | None = None) -> int:
        """Clear snapshot cache."""
        return await self._camera_manager.clear_cache(entity_id)

    def list_registered_cameras(self) -> list[dict[str, Any]]:
        """Return registered cameras."""
        return self._camera_manager.list_cameras()

    async def get_snapshot(
        self,
        entity_id: str,
        force_refresh: bool = False,
        if_none_match: str | None = None,
    ) -> tuple[CameraSnapshot | None, bool]:
        """Return a camera snapshot."""
        snapshot, not_modified = await self._camera_manager.get_snapshot(
            entity_id,
            force_refresh=force_refresh,
            if_none_match=if_none_match,
        )
        if snapshot is None:
            return None, not_modified
        return (
            CameraSnapshot(
                entity_id=snapshot.entity_id,
                image_data=snapshot.image_data,
                content_type=snapshot.content_type,
                timestamp=snapshot.timestamp,
                etag=snapshot.etag,
            ),
            not_modified,
        )

    async def start_hls_stream(self, entity_id: str) -> dict[str, Any] | None:
        """Start an HLS stream."""
        return await self._camera_manager.start_hls_stream(entity_id)

    async def stop_hls_stream(self, entity_id: str) -> bool:
        """Stop an HLS stream."""
        return await self._camera_manager.stop_hls_stream(entity_id)

    async def stream_proxy(self, entity_id: str, request: Any, response: Any) -> None:
        """Proxy an MJPEG stream through the existing camera manager."""
        await self._camera_manager.stream_proxy(entity_id, request, response)


def _home_assistant_camera_gateway(
    hass: Any,
    camera_manager: Any,
    *,
    allowed_entities_fn: Callable[[Any, Any], list[str]] = get_allowed_entities,
) -> HomeAssistantCameraGateway:
    """Build the Home Assistant-backed legacy camera gateway."""
    return HomeAssistantCameraGateway(
        hass,
        camera_manager,
        allowed_entities_fn=allowed_entities_fn,
    )


class HomeAssistantWebRTCGateway:
    """WebRTC gateway backed by Home Assistant state and WebRTCTokenManager."""

    def __init__(self, hass: Any, webrtc_manager: Any) -> None:
        self._hass = hass
        self._webrtc_manager = webrtc_manager

    def camera_exists(self, entity_id: str) -> bool:
        """Return whether the camera entity exists."""
        return self._hass.states.get(entity_id) is not None

    async def generate_token(self, entity_id: str, client_id: str) -> Any:
        """Generate a WebRTC token."""
        return await self._webrtc_manager.generate_token(
            entity_id=entity_id,
            client_id=client_id,
        )

    def get_ice_servers(
        self,
        turn_url: str | None = None,
        turn_username: str | None = None,
        turn_credential: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return configured ICE servers."""
        from ..webrtc import get_default_ice_servers, get_ice_servers_with_turn

        if turn_url and turn_username and turn_credential:
            return get_ice_servers_with_turn(turn_url, turn_username, turn_credential)
        return get_default_ice_servers()

    def get_session_by_partial_token(self, session_id: str) -> Any | None:
        """Return a WebRTC session by public session id."""
        return self._webrtc_manager.get_session_by_partial_token(session_id)

    async def consume_token(self, token: str, entity_id: str) -> Any | None:
        """Consume a WebRTC token and create a session."""
        return await self._webrtc_manager.consume_token(token, entity_id)

    async def update_session_state(
        self,
        token: str,
        state: str,
        local_sdp: str | None = None,
        remote_sdp: str | None = None,
    ) -> None:
        """Update a WebRTC session."""
        await self._webrtc_manager.update_session_state(
            token_str=token,
            state=state,
            local_sdp=local_sdp,
            remote_sdp=remote_sdp,
        )

    async def create_webrtc_answer(self, entity_id: str, offer_sdp: str, session: Any) -> str:
        """Create a WebRTC SDP answer through go2rtc."""
        from homeassistant.components.camera import async_get_stream_source
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        from ..const import DOMAIN, GO2RTC_URL, GO2RTC_WEBRTC_TIMEOUT

        stream_source = await async_get_stream_source(self._hass, entity_id)
        if not stream_source:
            raise RuntimeError(f"No stream source available for camera {entity_id}")

        data = self._hass.data.get(DOMAIN, {}).get("config_entry")
        go2rtc_url = GO2RTC_URL
        if data:
            go2rtc_url = data.data.get("go2rtc_url", GO2RTC_URL)

        session_client = async_get_clientsession(self._hass)
        stream_name = entity_id
        payload = {"type": "offer", "sdp": offer_sdp}
        url = f"{go2rtc_url}/api/webrtc"
        params = {"src": stream_name}

        try:
            return await self._post_webrtc_offer(
                session_client,
                url,
                params,
                payload,
                GO2RTC_WEBRTC_TIMEOUT,
            )
        except RuntimeError as err:
            if "404" not in str(err):
                raise

        await self._add_stream_to_go2rtc(
            session_client,
            go2rtc_url,
            stream_name,
            stream_source,
        )
        return await self._post_webrtc_offer(
            session_client,
            url,
            params,
            payload,
            GO2RTC_WEBRTC_TIMEOUT,
            retry=True,
        )

    async def _post_webrtc_offer(
        self,
        session_client: Any,
        url: str,
        params: dict[str, str],
        payload: dict[str, str],
        timeout_seconds: int,
        *,
        retry: bool = False,
    ) -> str:
        import aiohttp
        from aiohttp import ClientTimeout

        timeout = ClientTimeout(total=timeout_seconds)
        try:
            async with session_client.post(
                url,
                params=params,
                json=payload,
                timeout=timeout,
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    answer_sdp = result.get("sdp", "")
                    if answer_sdp:
                        return answer_sdp
                    suffix = " after retry" if retry else ""
                    raise RuntimeError(f"go2rtc returned empty SDP answer{suffix}")

                error_text = await response.text()
                suffix = " after adding stream" if retry else ""
                raise RuntimeError(
                    f"go2rtc WebRTC request failed{suffix}: " f"{response.status} - {error_text}"
                )
        except aiohttp.ClientError as err:
            raise RuntimeError(f"Failed to connect to go2rtc server. Error: {err}") from err

    async def _add_stream_to_go2rtc(
        self,
        session_client: Any,
        go2rtc_url: str,
        stream_name: str,
        stream_source: str,
    ) -> None:
        import aiohttp

        url = f"{go2rtc_url}/api/streams"
        params = {"name": stream_name, "src": stream_source}
        try:
            async with session_client.put(url, params=params) as response:
                await response.text()
        except aiohttp.ClientError:
            return

    async def close_session(self, token: str) -> bool:
        """Close a WebRTC session."""
        return await self._webrtc_manager.close_session(token)


def _home_assistant_web_rtc_gateway(
    hass: Any,
    webrtc_manager: Any,
) -> HomeAssistantWebRTCGateway:
    """Build the Home Assistant-backed legacy WebRTC gateway."""
    return HomeAssistantWebRTCGateway(hass, webrtc_manager)


class HomeAssistantHistoryGateway:
    """History gateway backed by Home Assistant Recorder."""

    def __init__(
        self,
        hass: Any,
        semaphore_factory: Callable[[], Any],
    ) -> None:
        self._hass = hass
        self._semaphore_factory = semaphore_factory

    async def query_states(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> list[Any]:
        """Return raw recorder states for an entity."""
        states = await self._query_recorder(
            start_time,
            end_time,
            [entity_id],
            significant_changes_only,
            no_attributes=False,
        )
        return states.get(entity_id, [])

    async def query_batch_states(
        self,
        entity_ids: list[str],
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> dict[str, list[Any]]:
        """Return raw recorder states for multiple entities."""
        return await self._query_recorder(
            start_time,
            end_time,
            entity_ids,
            significant_changes_only,
            no_attributes=False,
        )

    async def first_state_with_attributes(self, entity_id: str, start_time: Any) -> Any | None:
        """Return the first state with attributes near the query start."""
        from datetime import timedelta

        states = await self._query_recorder(
            start_time,
            start_time + timedelta(seconds=1),
            [entity_id],
            significant_changes_only=True,
            no_attributes=False,
        )
        first_state_list = states.get(entity_id, [])
        if first_state_list:
            return first_state_list[0]
        return None

    async def count_states(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        significant_changes_only: bool,
    ) -> int:
        """Return total state count for an entity."""
        states = await self._query_recorder(
            start_time,
            end_time,
            [entity_id],
            significant_changes_only,
            no_attributes=True,
        )
        return len(states.get(entity_id, []))

    def get_current_attributes(self, entity_id: str) -> dict[str, Any] | None:
        """Return current entity attributes."""
        current_state = self._hass.states.get(entity_id)
        if current_state and current_state.attributes:
            return dict(current_state.attributes)
        return None

    async def query_statistics(
        self,
        entity_id: str,
        start_time: Any,
        end_time: Any,
        period: str,
    ) -> list[dict[str, Any]]:
        """Return recorder statistics for an entity."""
        from homeassistant.components.recorder.statistics import statistics_during_period
        from homeassistant.helpers.recorder import get_instance

        stat_types = {"mean", "min", "max", "sum", "state"}
        recorder_instance = get_instance(self._hass)
        stat_result = await recorder_instance.async_add_executor_job(
            statistics_during_period,
            self._hass,
            start_time,
            end_time,
            {entity_id},
            period,
            None,
            stat_types,
        )
        return stat_result.get(entity_id, [])

    async def _query_recorder(
        self,
        start_time: Any,
        end_time: Any,
        entity_ids: list[str],
        significant_changes_only: bool,
        no_attributes: bool,
    ) -> dict[str, list[Any]]:
        from homeassistant.components.recorder import history
        from homeassistant.helpers.recorder import get_instance

        semaphore = self._semaphore_factory()
        async with semaphore:
            recorder_instance = get_instance(self._hass)
            return await recorder_instance.async_add_executor_job(
                history.get_significant_states,
                self._hass,
                start_time,
                end_time,
                entity_ids,
                None,
                True,
                significant_changes_only,
                True,
                no_attributes,
                True,
            )
