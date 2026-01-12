#!/usr/bin/env python3
"""Test Smartly Bridge API with HMAC authentication."""

import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime

import requests

# 設定這些值（從 Home Assistant 設定中獲取）
CLIENT_ID = "ha_J-TvO08fU8U7gSo3gJnUWQ"
CLIENT_SECRET = "ws8KOn36wCyhF5ga6CoVOG5ZpAYdybBxoPdCssye9CQ"
INSTANCE_ID = "home"
BASE_URL = "http://localhost:8123"


def generate_signature(
    client_secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes = b"",
) -> str:
    """Generate HMAC-SHA256 signature matching server's compute_signature."""
    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    signature = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature


def test_sync_api():
    """Test the sync API endpoint."""
    print("=== 測試 Sync API ===")
    
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(16)
    path = "/api/smartly/sync/structure"
    signature = generate_signature(CLIENT_SECRET, "GET", path, timestamp, nonce, b"")
    
    headers = {
        "X-Client-Id": CLIENT_ID,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
        "X-HA-Instance-Id": INSTANCE_ID,
    }
    
    url = f"{BASE_URL}{path}"
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    
    response = requests.get(url, headers=headers, timeout=10)
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    return response


def test_control_api(entity_id: str, action: str, service_data: dict = None):
    """Test the control API endpoint."""
    print(f"\n=== 測試 Control API ===")
    
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(16)
    path = "/api/smartly/control"
    
    body_dict = {
        "entity_id": entity_id,
        "action": action,
        "service_data": service_data or {},
        "actor": {
            "id": "test_user",
            "name": "Test User",
        },
    }
    body = json.dumps(body_dict).encode("utf-8")
    
    signature = generate_signature(CLIENT_SECRET, "POST", path, timestamp, nonce, body)
    
    headers = {
        "X-Client-Id": CLIENT_ID,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
        "X-HA-Instance-Id": INSTANCE_ID,
        "Content-Type": "application/json",
    }
    
    url = f"{BASE_URL}{path}"
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Body: {json.dumps(body_dict, indent=2)}")
    
    response = requests.post(url, headers=headers, data=body, timeout=10)
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    return response


if __name__ == "__main__":
    # 檢查是否已設定憑證
    if "YOUR_" in CLIENT_ID:
        print("❌ 請先設定 CLIENT_ID, CLIENT_SECRET, INSTANCE_ID")
        print("\n從 Home Assistant UI 設定 Smartly Bridge 後，會獲得這些憑證")
        exit(1)
    
    try:
        # 測試 Sync API
        test_sync_api()
        
        # 測試 Control API（需要有實際的實體）
        # test_control_api("light.living_room", "turn_on", {"brightness": 255})
        
    except requests.exceptions.ConnectionError:
        print("❌ 無法連接到 Home Assistant，請確保它正在運行")
    except Exception as e:
        print(f"❌ 錯誤: {e}")
