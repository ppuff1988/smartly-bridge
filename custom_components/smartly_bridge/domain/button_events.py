"""Canonical button event vocabulary shared by sync and ingestion."""

from __future__ import annotations

from typing import Any

BUTTON_EVENT_BY_SOURCE_GESTURE = {
    "single": "single_press",
    "short_release": "single_press",
    "double": "double_press",
    "double_press": "double_press",
    "triple": "triple_press",
    "hold": "long_press",
    "long_press": "long_press",
    "release": "long_release",
    "long_release": "long_release",
}


def canonical_button_action(action: Any) -> tuple[str, str] | None:
    """Map a common adapter action value to canonical channel and event names."""
    if not isinstance(action, str) or not action:
        return None
    for source_gesture in sorted(BUTTON_EVENT_BY_SOURCE_GESTURE, key=len, reverse=True):
        prefix = f"{source_gesture}_"
        suffix = f"_{source_gesture}"
        if action.startswith(prefix):
            channel = action.removeprefix(prefix)
        elif action.endswith(suffix):
            channel = action.removesuffix(suffix)
        else:
            continue
        if not channel:
            return None
        if channel.isdigit():
            channel = f"button_{channel}"
        return channel, BUTTON_EVENT_BY_SOURCE_GESTURE[source_gesture]
    return None
