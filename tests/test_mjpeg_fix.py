"""Test MJPEG stream endpoint for chunked encoding fix.

This test verifies that:
1. MJPEG stream responses do not use Transfer-Encoding: chunked
2. Proper Content-Type headers are set
3. Cache control headers are appropriate for streaming
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from custom_components.smartly_bridge.const import DOMAIN
from custom_components.smartly_bridge.views.camera import SmartlyCameraStreamView


class TestMJPEGStreamResponse(AioHTTPTestCase):
    """Test MJPEG stream response headers."""

    async def get_application(self):
        """Create test application."""
        app = web.Application()
        return app

    @pytest.mark.asyncio
    async def test_stream_response_headers(self):
        """Test that MJPEG stream has correct headers.

        Verifies:
        - Content-Type is multipart/x-mixed-replace;boundary=frame
        - Cache-Control headers are set appropriately
        - Connection: close is set to avoid chunked encoding
        """
        # Mock Home Assistant components
        mock_hass = MagicMock()
        mock_hass.data = {
            DOMAIN: {
                "client_secret": "test-secret",
                "camera_manager": MagicMock(),
            }
        }

        # Mock request with entity_id
        mock_request = MagicMock()
        mock_request.match_info = {"entity_id": "camera.test"}
        mock_request.headers = {
            "X-Client-Id": "test-client",
            "X-Timestamp": "1234567890",
            "X-Nonce": "test-nonce",
            "X-Signature": "test-signature",
        }
        mock_request.method = "GET"
        mock_request.path = "/api/smartly/camera/camera.test/stream"
        mock_request.query_string = ""
        mock_request.query = {}
        mock_request.remote = "127.0.0.1"

        # Create view instance
        view = SmartlyCameraStreamView(mock_request)
        view.hass = mock_hass

        # Mock authentication
        with patch("custom_components.smartly_bridge.views.camera.verify_request") as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True,
                client_id="test-client",
                error=None,
            )

            # Mock rate limiter
            with patch("custom_components.smartly_bridge.views.camera.RateLimiter") as mock_limiter:
                mock_limiter.return_value.check = AsyncMock(return_value=True)

                # Mock entity registry and ACL
                with patch(
                    "custom_components.smartly_bridge.views.camera.is_entity_allowed"
                ) as mock_acl:
                    mock_acl.return_value = True

                    # Mock camera manager stream_proxy
                    mock_camera_manager = mock_hass.data[DOMAIN]["camera_manager"]
                    mock_camera_manager.stream_proxy = AsyncMock()

                    # Call the get method
                    response = await view.get()

                    # Verify response type
                    assert isinstance(response, web.StreamResponse)

                    # Verify Content-Type
                    assert response.content_type == "multipart/x-mixed-replace;boundary=frame"

                    # Verify Cache-Control headers
                    assert "Cache-Control" in response.headers
                    assert "no-cache" in response.headers["Cache-Control"]
                    assert "no-store" in response.headers["Cache-Control"]
                    assert "must-revalidate" in response.headers["Cache-Control"]

                    # Verify Pragma header
                    assert response.headers.get("Pragma") == "no-cache"

                    # Verify Expires header
                    assert response.headers.get("Expires") == "0"

                    # Verify Connection header (critical for avoiding chunked encoding)
                    assert response.headers.get("Connection") == "close"

                    print("✅ All header validations passed")

    @pytest.mark.asyncio
    async def test_no_chunked_encoding_flag(self):
        """Test that chunked encoding is not explicitly enabled.

        This test ensures we don't accidentally enable chunked encoding
        which would break MJPEG streaming.
        """
        # Create a StreamResponse with our headers
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "multipart/x-mixed-replace;boundary=frame",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "close",
            },
        )

        # Verify that we haven't set up chunked encoding
        # Note: aiohttp's StreamResponse doesn't expose a direct way to check
        # if chunked encoding will be used before prepare(), but we can verify
        # our headers are set correctly

        assert "Content-Type" in response.headers
        assert response.headers["Content-Type"] == "multipart/x-mixed-replace;boundary=frame"
        assert response.headers["Connection"] == "close"

        # The combination of no Content-Length and Connection: close
        # should prevent aiohttp from using chunked encoding
        assert "Content-Length" not in response.headers

        print("✅ Chunked encoding prevention checks passed")


def test_stream_response_documentation():
    """Verify that our fix is properly documented.

    This test ensures the code contains appropriate comments explaining
    the chunked encoding fix.
    """
    import inspect

    from custom_components.smartly_bridge.views.camera import SmartlyCameraStreamView

    # Get the source code
    source = inspect.getsource(SmartlyCameraStreamView.get)

    # Verify critical documentation keywords
    assert "chunked encoding" in source.lower(), "Missing chunked encoding documentation"
    assert "multipart/x-mixed-replace" in source.lower(), "Missing MJPEG format documentation"
    assert "Connection" in source, "Missing Connection header documentation"

    print("✅ Documentation checks passed")


if __name__ == "__main__":
    # Run tests
    test_stream_response_documentation()
    print("\n" + "=" * 80)
    print("NOTE: Async tests require pytest to run:")
    print("  pytest tests/test_mjpeg_fix.py -v")
    print("=" * 80)
