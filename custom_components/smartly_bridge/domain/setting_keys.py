"""Stable setting identity shared by sync and command routing."""

from __future__ import annotations

NUMERIC_SETTING_DOMAINS = {"number", "input_number"}
OPTION_SETTING_DOMAINS = {"select", "input_select"}
SETTING_DOMAINS = NUMERIC_SETTING_DOMAINS | OPTION_SETTING_DOMAINS


def setting_key_for_entity(entity_id: str, name: str, domain: str) -> str | None:
    """Return the stable Smartly key for a supported setting entity."""
    haystack = f"{entity_id} {name}".lower()
    if domain in NUMERIC_SETTING_DOMAINS and any(
        token in haystack for token in ("cooldown", "cooldown_seconds", "冷卻")
    ):
        return "cooldown_seconds"
    if domain in NUMERIC_SETTING_DOMAINS and any(
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
    if domain in OPTION_SETTING_DOMAINS and any(
        token in haystack for token in ("sensitivity", "occupancy_sensitivity", "感應強度")
    ):
        return "occupancy_sensitivity"
    if domain in SETTING_DOMAINS:
        _, _, object_id = entity_id.partition(".")
        return object_id or entity_id
    return None
