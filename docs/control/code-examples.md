# 程式碼範例

> **返回**：[控制 API 指南](./README.md)

本文檔提供 API vNext `SmartlyCommand` 客戶端範例，包含 cURL、Python、JavaScript/TypeScript 以及瀏覽器環境。

---

## cURL 範例

```bash
#!/bin/bash

BASE_URL="http://homeassistant.local:8123"
CLIENT_ID="ha_abc123def456"
CLIENT_SECRET="your_secret_key"
METHOD="POST"
PATH="/api/smartly/control"
TIMESTAMP=$(date +%s)
NONCE=$(uuidgen | tr '[:upper:]' '[:lower:]')

BODY='{
  "command_id": "cmd_20260627_0001",
  "device_id": "ldev_bedroom_light",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "value": 78
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}'

BODY_HASH=$(echo -n "$BODY" | sha256sum | awk '{print $1}')
PAYLOAD="${METHOD}\n${PATH}\n${TIMESTAMP}\n${NONCE}\n${BODY_HASH}"
SIGNATURE=$(echo -n -e "$PAYLOAD" | openssl dgst -sha256 -hmac "$CLIENT_SECRET" | awk '{print $2}')

curl -X POST "${BASE_URL}${PATH}" \
  -H "Content-Type: application/json" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Timestamp: ${TIMESTAMP}" \
  -H "X-Nonce: ${NONCE}" \
  -H "X-Signature: ${SIGNATURE}" \
  -d "$BODY"
```

---

## Python 範例

```python
#!/usr/bin/env python3
"""Smartly Bridge API vNext client."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import requests


class SmartlyBridgeClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret

    def _signature(
        self,
        method: str,
        path: str,
        timestamp: str,
        nonce: str,
        body: dict[str, Any],
    ) -> str:
        body_json = json.dumps(body, separators=(",", ":"), sort_keys=False)
        body_hash = hashlib.sha256(body_json.encode()).hexdigest()
        payload = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
        return hmac.new(
            self.client_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    def send_command(
        self,
        *,
        command_id: str,
        device_id: str,
        capability: str,
        command: str,
        params: dict[str, Any] | None = None,
        source: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        method = "POST"
        path = "/api/smartly/control"
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        body: dict[str, Any] = {
            "command_id": command_id,
            "device_id": device_id,
            "capability": capability,
            "command": command,
            "params": params or {},
        }
        if source:
            body["source"] = source

        headers = {
            "Content-Type": "application/json",
            "X-Client-Id": self.client_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": self._signature(method, path, timestamp, nonce, body),
        }
        response = requests.post(
            f"{self.base_url}{path}",
            headers=headers,
            json=body,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    client = SmartlyBridgeClient(
        base_url="http://homeassistant.local:8123",
        client_id="ha_abc123def456",
        client_secret="your_secret_key",
    )

    result = client.send_command(
        command_id="cmd_20260627_0001",
        device_id="ldev_bedroom_light",
        capability="brightness",
        command="set_brightness",
        params={"value": 78},
        source={"user_id": "u_123", "role": "tenant"},
    )
    print(result)
```

---

## JavaScript/TypeScript 範例

```typescript
import crypto from 'crypto';

type JsonObject = Record<string, unknown>;

interface SmartlyCommand {
  command_id: string;
  device_id: string;
  capability: string;
  command: string;
  params?: JsonObject;
  source?: {
    user_id?: string;
    role?: string;
  };
}

interface BridgeEnvelope {
  schema_version: string;
  data: JsonObject;
  warnings: unknown[];
  errors: Array<{
    code: string;
    message: string;
    target?: string;
  }>;
}

class SmartlyBridgeClient {
  constructor(
    private baseUrl: string,
    private clientId: string,
    private clientSecret: string
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  private signature(
    method: string,
    path: string,
    timestamp: string,
    nonce: string,
    body: SmartlyCommand
  ): string {
    const bodyJson = JSON.stringify(body);
    const bodyHash = crypto.createHash('sha256').update(bodyJson).digest('hex');
    const payload = `${method}\n${path}\n${timestamp}\n${nonce}\n${bodyHash}`;
    return crypto
      .createHmac('sha256', this.clientSecret)
      .update(payload)
      .digest('hex');
  }

  async sendCommand(body: SmartlyCommand): Promise<BridgeEnvelope> {
    const method = 'POST';
    const path = '/api/smartly/control';
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const nonce = crypto.randomUUID();
    const headers = {
      'Content-Type': 'application/json',
      'X-Client-Id': this.clientId,
      'X-Timestamp': timestamp,
      'X-Nonce': nonce,
      'X-Signature': this.signature(method, path, timestamp, nonce, body)
    };

    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: JSON.stringify(body)
    });
    const envelope = await response.json();
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${JSON.stringify(envelope)}`);
    }
    return envelope;
  }
}

const client = new SmartlyBridgeClient(
  'http://homeassistant.local:8123',
  'ha_abc123def456',
  'your_secret_key'
);

client.sendCommand({
  command_id: 'cmd_20260627_0001',
  device_id: 'ldev_bedroom_light',
  capability: 'brightness',
  command: 'set_brightness',
  params: { value: 78 },
  source: { user_id: 'u_123', role: 'tenant' }
}).then(console.log);
```

---

## 瀏覽器環境範例

```javascript
class SmartlyBridgeBrowserClient {
  constructor(baseUrl, clientId, clientSecret) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.clientId = clientId;
    this.clientSecret = clientSecret;
  }

  async signature(method, path, timestamp, nonce, body) {
    const bodyJson = JSON.stringify(body);
    const bodyBuffer = new TextEncoder().encode(bodyJson);
    const bodyHashBuffer = await crypto.subtle.digest('SHA-256', bodyBuffer);
    const bodyHash = Array.from(new Uint8Array(bodyHashBuffer))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
    const payload = `${method}\n${path}\n${timestamp}\n${nonce}\n${bodyHash}`;
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(this.clientSecret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    const signatureBuffer = await crypto.subtle.sign(
      'HMAC',
      key,
      new TextEncoder().encode(payload)
    );
    return Array.from(new Uint8Array(signatureBuffer))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  }

  async sendCommand(body) {
    const method = 'POST';
    const path = '/api/smartly/control';
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const nonce = crypto.randomUUID();
    const headers = {
      'Content-Type': 'application/json',
      'X-Client-Id': this.clientId,
      'X-Timestamp': timestamp,
      'X-Nonce': nonce,
      'X-Signature': await this.signature(method, path, timestamp, nonce, body)
    };
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: JSON.stringify(body)
    });
    const envelope = await response.json();
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${JSON.stringify(envelope)}`);
    }
    return envelope;
  }
}

const client = new SmartlyBridgeBrowserClient(
  'http://homeassistant.local:8123',
  'ha_abc123def456',
  'your_secret_key'
);

client.sendCommand({
  command_id: 'cmd_20260627_0001',
  device_id: 'ldev_bedroom_light',
  capability: 'brightness',
  command: 'set_brightness',
  params: { value: 78 },
  source: { user_id: 'u_123', role: 'tenant' }
}).then(console.log);
```

---

## 📚 相關文檔

- **[API 基礎與認證](./api-basics.md)** - 端點資訊與簽名計算
- **[設備類型控制](./device-types.md)** - 各設備類型的 capability 與 command
- **[回應格式](./responses.md)** - 成功與錯誤回應說明

---

**返回**：[控制 API 指南](./README.md)
