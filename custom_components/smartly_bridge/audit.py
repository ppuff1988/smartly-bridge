"""Audit logging for Smartly Bridge."""

from __future__ import annotations

import logging
from typing import Any


def log_control(
    logger: logging.Logger,
    client_id: str,
    entity_id: str,
    service: str,
    result: str,
    actor: dict[str, Any] | None = None,
) -> None:
    """Log a control action."""
    actor_info = ""
    if actor:
        user_id = actor.get("user_id", "unknown")
        role = actor.get("role", "unknown")
        actor_info = f", actor={user_id}/{role}"

    logger.info(
        "CONTROL: client=%s, entity=%s, service=%s, result=%s%s",
        client_id,
        entity_id,
        service,
        result,
        actor_info,
    )


def log_deny(
    logger: logging.Logger,
    client_id: str,
    entity_id: str,
    service: str,
    reason: str,
    actor: dict[str, Any] | None = None,
) -> None:
    """Log a denied action."""
    actor_info = ""
    if actor:
        user_id = actor.get("user_id", "unknown")
        role = actor.get("role", "unknown")
        actor_info = f", actor={user_id}/{role}"

    logger.warning(
        "DENY: client=%s, entity=%s, service=%s, reason=%s%s",
        client_id,
        entity_id,
        service,
        reason,
        actor_info,
    )


def log_push_success(
    logger: logging.Logger,
    instance_id: str,
    event_count: int,
) -> None:
    """Log a successful push to Platform."""
    logger.debug(
        "PUSH_SUCCESS: instance=%s, events=%d",
        instance_id,
        event_count,
    )


def log_push_fail(
    logger: logging.Logger,
    instance_id: str,
    event_count: int,
    reason: str,
) -> None:
    """Log a failed push to Platform."""
    logger.error(
        "PUSH_FAIL: instance=%s, events=%d, reason=%s",
        instance_id,
        event_count,
        reason,
    )


def log_auth_fail(
    logger: logging.Logger,
    client_id: str,
    reason: str,
    ip: str = "",
) -> None:
    """Log an authentication failure."""
    logger.warning(
        "AUTH_FAIL: client=%s, reason=%s, ip=%s",
        client_id,
        reason,
        ip,
    )


def log_rate_limit(
    logger: logging.Logger,
    client_id: str,
    endpoint: str,
) -> None:
    """Log a rate limit hit."""
    logger.warning(
        "RATE_LIMIT: client=%s, endpoint=%s",
        client_id,
        endpoint,
    )


def log_integration_event(
    logger: logging.Logger,
    event: str,
    details: str = "",
) -> None:
    """Log an integration lifecycle event."""
    if details:
        logger.info("INTEGRATION: event=%s, details=%s", event, details)
    else:
        logger.info("INTEGRATION: event=%s", event)
