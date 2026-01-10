#!/usr/bin/env python3
"""Debug script for HMAC signature calculation.

This script helps diagnose signature mismatches by showing exactly
how signatures should be calculated for History API requests.
"""

import hashlib
import hmac
import sys


def compute_signature(
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    """Compute HMAC-SHA256 signature."""
    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    
    print("═" * 80)
    print("簽名計算詳細資訊")
    print("═" * 80)
    print(f"Method:    {method}")
    print(f"Path:      {path}")
    print(f"Timestamp: {timestamp}")
    print(f"Nonce:     {nonce}")
    print(f"Body:      {body}")
    print(f"Body Hash: {body_hash}")
    print()
    print("Message to sign:")
    print("─" * 80)
    print(message)
    print("─" * 80)
    print()
    
    signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    
    print(f"Secret:    {secret}")
    print(f"Signature: {signature}")
    print("═" * 80)
    print()
    
    return signature


if __name__ == "__main__":
    # 範例：從日誌中的資訊計算簽名
    print("History API 簽名計算範例")
    print()
    
    # 客戶端需要提供的值
    SECRET = "YOUR_CLIENT_SECRET_HERE"  # 從 Home Assistant 設定中取得
    METHOD = "GET"
    PATH = "/api/smartly/history/sensor.temperature?start_time=2026-01-09T00:00:00Z&end_time=2026-01-10T00:00:00Z&limit=1000&significant_changes_only=true"
    TIMESTAMP = "1768016004"
    NONCE = "af211ce5-8888-4444-aaaa-bbbbccccdddd"
    BODY = b""
    
    print("⚠️  注意：PATH 必須包含完整的查詢參數字串")
    print("⚠️  查詢參數順序必須與發送請求時完全一致")
    print()
    
    signature = compute_signature(SECRET, METHOD, PATH, TIMESTAMP, NONCE, BODY)
    
    print()
    print("客戶端應該在 HTTP headers 中包含：")
    print(f"  X-Client-Id: YOUR_CLIENT_ID")
    print(f"  X-Timestamp: {TIMESTAMP}")
    print(f"  X-Nonce: {NONCE}")
    print(f"  X-Signature: {signature}")
    print()
    print("常見錯誤：")
    print("  ❌ Path 不包含查詢參數")
    print("  ❌ 查詢參數順序不一致")
    print("  ❌ URL 編碼不一致（如 : 被編碼為 %3A）")
    print("  ❌ 使用錯誤的 secret")
