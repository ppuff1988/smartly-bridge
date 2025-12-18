"""Tests for audit logging module."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from custom_components.smartly_bridge.audit import (
    log_control,
    log_deny,
    log_push_success,
    log_push_fail,
    log_auth_fail,
    log_rate_limit,
    log_integration_event,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock(spec=logging.Logger)


class TestLogControl:
    """Tests for log_control function."""

    def test_log_control_basic(self, mock_logger):
        """Test basic control logging."""
        log_control(
            mock_logger,
            client_id="client_123",
            entity_id="light.test",
            service="turn_on",
            result="success",
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "CONTROL" in call_args
        assert "client_123" in mock_logger.info.call_args[0]

    def test_log_control_with_actor(self, mock_logger):
        """Test control logging with actor information."""
        log_control(
            mock_logger,
            client_id="client_123",
            entity_id="light.test",
            service="turn_on",
            result="success",
            actor={"user_id": "user_456", "role": "admin"},
        )
        
        mock_logger.info.assert_called_once()


class TestLogDeny:
    """Tests for log_deny function."""

    def test_log_deny_basic(self, mock_logger):
        """Test basic deny logging."""
        log_deny(
            mock_logger,
            client_id="client_123",
            entity_id="light.test",
            service="turn_on",
            reason="entity_not_allowed",
        )
        
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "DENY" in call_args

    def test_log_deny_with_actor(self, mock_logger):
        """Test deny logging with actor information."""
        log_deny(
            mock_logger,
            client_id="client_123",
            entity_id="light.test",
            service="turn_on",
            reason="service_not_allowed",
            actor={"user_id": "user_456", "role": "guest"},
        )
        
        mock_logger.warning.assert_called_once()


class TestLogPush:
    """Tests for push logging functions."""

    def test_log_push_success(self, mock_logger):
        """Test push success logging."""
        log_push_success(
            mock_logger,
            instance_id="instance_123",
            event_count=5,
        )
        
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "PUSH_SUCCESS" in call_args

    def test_log_push_fail(self, mock_logger):
        """Test push failure logging."""
        log_push_fail(
            mock_logger,
            instance_id="instance_123",
            event_count=5,
            reason="connection_timeout",
        )
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "PUSH_FAIL" in call_args


class TestLogAuthFail:
    """Tests for log_auth_fail function."""

    def test_log_auth_fail(self, mock_logger):
        """Test auth failure logging."""
        log_auth_fail(
            mock_logger,
            client_id="client_123",
            reason="invalid_signature",
            ip="192.168.1.100",
        )
        
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "AUTH_FAIL" in call_args


class TestLogRateLimit:
    """Tests for log_rate_limit function."""

    def test_log_rate_limit(self, mock_logger):
        """Test rate limit logging."""
        log_rate_limit(
            mock_logger,
            client_id="client_123",
            endpoint="/api/smartly/control",
        )
        
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "RATE_LIMIT" in call_args


class TestLogIntegrationEvent:
    """Tests for log_integration_event function."""

    def test_log_integration_event_basic(self, mock_logger):
        """Test basic integration event logging."""
        log_integration_event(
            mock_logger,
            event="setup_complete",
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "INTEGRATION" in call_args

    def test_log_integration_event_with_details(self, mock_logger):
        """Test integration event logging with details."""
        log_integration_event(
            mock_logger,
            event="setup_complete",
            details="instance=test_123",
        )
        
        mock_logger.info.assert_called_once()
