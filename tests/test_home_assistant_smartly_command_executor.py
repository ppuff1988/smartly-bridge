"""Tests for Home Assistant Smartly command executor wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.smartly_bridge.adapters.home_assistant import (
    HomeAssistantSmartlyCommandExecutor,
    _home_assistant_smartly_command_executor,
)
from custom_components.smartly_bridge.application.control import SmartlyCommand
from custom_components.smartly_bridge.domain.models import BridgeResponse


class FakeSmartlyCommandUseCase:
    """Smartly command use case used to verify executor wiring."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, SmartlyCommand]] = []

    async def execute(self, client_id: str, command: SmartlyCommand) -> BridgeResponse:
        """Record the command and return an accepted response."""
        self.calls.append((client_id, command))
        return BridgeResponse({"success": True, "status": "completed"})


def test_home_assistant_smartly_command_executor_factory_builds_legacy_executor() -> None:
    """Smartly command executor factory centralizes legacy executor wiring."""
    hass = MagicMock()
    logger = MagicMock()

    executor = _home_assistant_smartly_command_executor(hass, logger)

    assert isinstance(executor, HomeAssistantSmartlyCommandExecutor)


@pytest.mark.asyncio
async def test_smartly_command_executor_uses_injected_use_case_factory() -> None:
    """Command executor delegates through the injected application use case seam."""
    hass = MagicMock()
    logger = MagicMock()
    use_case = FakeSmartlyCommandUseCase()
    factory_calls: list[tuple[object, object]] = []

    def use_case_factory(hass_arg: object, logger_arg: object) -> FakeSmartlyCommandUseCase:
        factory_calls.append((hass_arg, logger_arg))
        return use_case

    executor = HomeAssistantSmartlyCommandExecutor(
        hass,
        logger,
        use_case_factory=use_case_factory,
    )
    command = SmartlyCommand(
        command_id="cmd-1",
        device_id="ldev-light",
        capability="power",
        command="turn_on",
    )

    result = await executor.execute("client-1", command)

    assert result.body["success"] is True
    assert factory_calls == [(hass, logger)]
    assert use_case.calls == [("client-1", command)]
