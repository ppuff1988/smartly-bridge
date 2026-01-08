#!/usr/bin/env python3
"""Test MJPEG stream for chunked encoding issues.

This script tests the MJPEG stream endpoint to verify:
1. Response headers do not contain Transfer-Encoding: chunked
2. Response contains correct multipart/x-mixed-replace format
3. Stream data is properly formatted (starts with --frame boundary)
4. No chunked encoding wrapper is present in the stream

Usage:
    python scripts/manual_tests/test_mjpeg_stream.py

Requirements:
    - Home Assistant instance running with Smartly Bridge
    - Camera entity configured (e.g., camera.test)
    - Client ID and secret configured
"""

import hashlib
import hmac
import sys
import time
from typing import Dict

import requests


def generate_hmac_headers(
    client_id: str,
    client_secret: str,
    path: str,
    method: str = "GET",
    body: str = "",
) -> Dict[str, str]:
    """Generate HMAC authentication headers.

    Args:
        client_id: Client ID for authentication
        client_secret: Client secret for HMAC signing
        path: Request path (e.g., /api/smartly/camera/camera.test/stream)
        method: HTTP method (default: GET)
        body: Request body (default: empty)

    Returns:
        Dictionary of authentication headers
    """
    timestamp = str(int(time.time()))
    nonce = hashlib.sha256(f"{timestamp}{client_id}".encode()).hexdigest()[:16]

    # Construct string to sign
    string_to_sign = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body}"

    # Generate HMAC signature
    signature = hmac.new(
        client_secret.encode(),
        string_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "X-Client-Id": client_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }


def test_mjpeg_stream(
    base_url: str,
    entity_id: str,
    client_id: str,
    client_secret: str,
) -> None:
    """Test MJPEG stream endpoint.

    Args:
        base_url: Base URL of Home Assistant (e.g., http://localhost:8123)
        entity_id: Camera entity ID (e.g., camera.test)
        client_id: Client ID for authentication
        client_secret: Client secret for HMAC signing
    """
    path = f"/api/smartly/camera/{entity_id}/stream"
    url = f"{base_url}{path}"

    print(f"Testing MJPEG stream: {url}")
    print("=" * 80)

    # Generate authentication headers
    headers = generate_hmac_headers(client_id, client_secret, path, "GET")

    try:
        # Send HEAD request first to check headers
        print("\n1. Checking response headers (HEAD request)...")
        head_response = requests.head(url, headers=headers, timeout=5)
        print(f"   Status: {head_response.status_code}")
        print(f"   Content-Type: {head_response.headers.get('Content-Type', 'N/A')}")
        print(f"   Transfer-Encoding: {head_response.headers.get('Transfer-Encoding', 'None')}")
        print(f"   Content-Length: {head_response.headers.get('Content-Length', 'N/A')}")
        print(f"   Connection: {head_response.headers.get('Connection', 'N/A')}")
        print(f"   Cache-Control: {head_response.headers.get('Cache-Control', 'N/A')}")

        # Check for chunked encoding (should NOT be present)
        if "chunked" in head_response.headers.get("Transfer-Encoding", "").lower():
            print("   ❌ ERROR: Transfer-Encoding: chunked is present!")
            print("   This will cause MJPEG parsing errors in clients.")
        else:
            print("   ✅ PASS: No chunked encoding detected")

        # Check Content-Type
        content_type = head_response.headers.get("Content-Type", "")
        if "multipart/x-mixed-replace" in content_type and "boundary=frame" in content_type:
            print("   ✅ PASS: Correct Content-Type for MJPEG")
        else:
            print(f"   ❌ ERROR: Invalid Content-Type: {content_type}")

        # Send GET request to read stream data
        print("\n2. Reading stream data (first 2KB)...")
        response = requests.get(url, headers=headers, stream=True, timeout=10)

        # Read first 2KB
        chunk = response.raw.read(2048)

        print(f"   Bytes read: {len(chunk)}")

        if len(chunk) > 0:
            print("   ✅ PASS: Stream data received")

            # Check for MJPEG boundary marker
            if b"--frame" in chunk[:100]:
                print("   ✅ PASS: MJPEG boundary marker found")
            else:
                print("   ❌ ERROR: No MJPEG boundary marker in first 100 bytes")

            # Check for chunked encoding wrapper (should NOT be present)
            # Chunked encoding starts with hex size like "5\r\n"
            hex_chars = b"0123456789abcdefABCDEF"
            if chunk[0:1] in hex_chars and b"\r\n" in chunk[:10]:
                print("   ❌ ERROR: Chunked encoding wrapper detected!")
                print(f"   First 50 bytes (hex): {chunk[:50].hex()}")
            else:
                print("   ✅ PASS: No chunked encoding wrapper")

            # Show first 100 bytes for inspection
            print(f"\n   First 100 bytes:")
            print(f"   {chunk[:100]!r}")

            # Hex dump of first 50 bytes
            print(f"\n   Hex dump (first 50 bytes):")
            hex_dump = " ".join(f"{b:02x}" for b in chunk[:50])
            print(f"   {hex_dump}")

        else:
            print("   ❌ ERROR: No data received (bytes_written: 0)")

        response.close()

        print("\n" + "=" * 80)
        print("Test completed.")

    except requests.exceptions.Timeout:
        print("   ❌ ERROR: Request timeout")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ ERROR: {e}")
    except Exception as e:
        print(f"   ❌ UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main entry point."""
    # Configuration (modify these values for your setup)
    BASE_URL = "http://localhost:8123"
    ENTITY_ID = "camera.test"
    CLIENT_ID = "your-client-id"  # Replace with your client ID
    CLIENT_SECRET = "your-client-secret"  # Replace with your client secret

    # Check if using default values
    if CLIENT_ID == "your-client-id" or CLIENT_SECRET == "your-client-secret":
        print("ERROR: Please configure CLIENT_ID and CLIENT_SECRET in the script")
        print("You can find these values in your Home Assistant configuration")
        sys.exit(1)

    test_mjpeg_stream(BASE_URL, ENTITY_ID, CLIENT_ID, CLIENT_SECRET)


if __name__ == "__main__":
    main()
