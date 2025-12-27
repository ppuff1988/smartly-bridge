# 程式碼範例

> **返回**：[控制 API 指南](./README.md)

本文檔提供完整的 API 客戶端實作範例，包含 cURL、Python、JavaScript/TypeScript 以及瀏覽器環境。

---

## 目錄

1. [cURL 範例](#curl-範例)
2. [Python 範例](#python-範例)
3. [JavaScript/TypeScript 範例](#javascripttypescript-範例)
4. [瀏覽器環境範例](#瀏覽器環境範例)

---

## cURL 範例

```bash
#!/bin/bash

# 配置變數
BASE_URL="http://homeassistant.local:8123"
CLIENT_ID="ha_abc123def456"
CLIENT_SECRET="your_secret_key"
METHOD="POST"
PATH="/api/smartly/control"
TIMESTAMP=$(date +%s)
NONCE=$(uuidgen | tr '[:upper:]' '[:lower:]')

# 請求 Body
BODY='{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 200,
    "rgb_color": [255, 180, 100]
  },
  "actor": {
    "user_id": "u_123",
    "role": "tenant"
  }
}'

# 計算 Body SHA256
BODY_HASH=$(echo -n "$BODY" | sha256sum | awk '{print $1}')

# 組合 Payload
PAYLOAD="${METHOD}\n${PATH}\n${TIMESTAMP}\n${NONCE}\n${BODY_HASH}"

# 計算 HMAC-SHA256 簽名
SIGNATURE=$(echo -n -e "$PAYLOAD" | openssl dgst -sha256 -hmac "$CLIENT_SECRET" | awk '{print $2}')

# 發送請求
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

### 完整客戶端類別

```python
#!/usr/bin/env python3
"""
Smartly Bridge API Client - Python 範例
支援 Python 3.8+
"""

import requests
import hashlib
import hmac
import time
import uuid
import json
from typing import Dict, Any, Optional


class SmartlyBridgeClient:
    """Smartly Bridge API 客戶端"""
    
    def __init__(self, base_url: str, client_id: str, client_secret: str):
        """
        初始化客戶端
        
        Args:
            base_url: Home Assistant 基礎 URL
            client_id: 客戶端 ID
            client_secret: 客戶端密鑰
        """
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
    
    def _calculate_signature(
        self, 
        method: str, 
        path: str, 
        timestamp: str, 
        nonce: str, 
        body: Dict[str, Any]
    ) -> str:
        """計算 HMAC-SHA256 簽名"""
        # 計算 Body 的 SHA256 雜湊值
        body_json = json.dumps(body, separators=(',', ':'), sort_keys=False)
        body_hash = hashlib.sha256(body_json.encode()).hexdigest()
        
        # 組合 Payload
        payload = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
        
        # 計算 HMAC-SHA256
        signature = hmac.new(
            self.client_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def control_device(
        self,
        entity_id: str,
        action: str,
        service_data: Optional[Dict[str, Any]] = None,
        actor: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        控制設備
        
        Args:
            entity_id: 設備實體 ID
            action: 動作名稱
            service_data: 服務參數（選填）
            actor: 操作者資訊（選填）
        
        Returns:
            API 回應的 JSON 資料
        
        Raises:
            requests.HTTPError: HTTP 錯誤
        """
        method = "POST"
        path = "/api/smartly/control"
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        
        # 準備請求 Body
        body = {
            "entity_id": entity_id,
            "action": action,
            "service_data": service_data or {}
        }
        
        if actor:
            body["actor"] = actor
        
        # 計算簽名
        signature = self._calculate_signature(method, path, timestamp, nonce, body)
        
        # 準備標頭
        headers = {
            "Content-Type": "application/json",
            "X-Client-Id": self.client_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature
        }
        
        # 發送請求
        response = requests.post(
            f"{self.base_url}{path}",
            headers=headers,
            json=body,
            timeout=10
        )
        
        # 檢查錯誤
        response.raise_for_status()
        
        return response.json()
```

### 使用範例

```python
if __name__ == "__main__":
    # 初始化客戶端
    client = SmartlyBridgeClient(
        base_url="http://homeassistant.local:8123",
        client_id="ha_abc123def456",
        client_secret="your_secret_key"
    )
    
    try:
        # 範例 1: 開啟燈光並設定亮度和顏色
        result = client.control_device(
            entity_id="light.bedroom",
            action="turn_on",
            service_data={
                "brightness": 200,
                "rgb_color": [255, 180, 100]
            },
            actor={
                "user_id": "u_123",
                "role": "tenant"
            }
        )
        print("✓ 燈光控制成功:", result)
        
        # 範例 2: 設定空調溫度
        result = client.control_device(
            entity_id="climate.living_room_ac",
            action="set_temperature",
            service_data={
                "temperature": 24
            }
        )
        print("✓ 空調控制成功:", result)
        
        # 範例 3: 開啟窗簾
        result = client.control_device(
            entity_id="cover.living_room_curtain",
            action="open_cover"
        )
        print("✓ 窗簾控制成功:", result)
        
    except requests.HTTPError as e:
        print(f"✗ HTTP 錯誤: {e.response.status_code}")
        print(f"  回應內容: {e.response.text}")
    except Exception as e:
        print(f"✗ 發生錯誤: {e}")
```

---

## JavaScript/TypeScript 範例

### 完整客戶端類別（Node.js）

```typescript
/**
 * Smartly Bridge API Client - JavaScript/TypeScript 範例
 * 支援 Node.js 18+ 和現代瀏覽器
 */

import crypto from 'crypto';

interface ServiceData {
  [key: string]: any;
}

interface Actor {
  user_id: string;
  role: string;
}

interface ControlRequest {
  entity_id: string;
  action: string;
  service_data?: ServiceData;
  actor?: Actor;
}

interface ControlResponse {
  success: boolean;
  entity_id: string;
  action: string;
  new_state?: string;
  new_attributes?: Record<string, any>;
  error?: string;
}

class SmartlyBridgeClient {
  private baseUrl: string;
  private clientId: string;
  private clientSecret: string;

  /**
   * 初始化客戶端
   * @param baseUrl - Home Assistant 基礎 URL
   * @param clientId - 客戶端 ID
   * @param clientSecret - 客戶端密鑰
   */
  constructor(baseUrl: string, clientId: string, clientSecret: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.clientId = clientId;
    this.clientSecret = clientSecret;
  }

  /**
   * 計算 HMAC-SHA256 簽名
   */
  private calculateSignature(
    method: string,
    path: string,
    timestamp: string,
    nonce: string,
    body: ControlRequest
  ): string {
    // 計算 Body 的 SHA256 雜湊值
    const bodyJson = JSON.stringify(body);
    const bodyHash = crypto.createHash('sha256').update(bodyJson).digest('hex');

    // 組合 Payload
    const payload = `${method}\n${path}\n${timestamp}\n${nonce}\n${bodyHash}`;

    // 計算 HMAC-SHA256
    const signature = crypto
      .createHmac('sha256', this.clientSecret)
      .update(payload)
      .digest('hex');

    return signature;
  }

  /**
   * 控制設備
   * @param entityId - 設備實體 ID
   * @param action - 動作名稱
   * @param serviceData - 服務參數（選填）
   * @param actor - 操作者資訊（選填）
   * @returns API 回應
   */
  async controlDevice(
    entityId: string,
    action: string,
    serviceData?: ServiceData,
    actor?: Actor
  ): Promise<ControlResponse> {
    const method = 'POST';
    const path = '/api/smartly/control';
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const nonce = crypto.randomUUID();

    // 準備請求 Body
    const body: ControlRequest = {
      entity_id: entityId,
      action: action,
      service_data: serviceData || {}
    };

    if (actor) {
      body.actor = actor;
    }

    // 計算簽名
    const signature = this.calculateSignature(method, path, timestamp, nonce, body);

    // 準備標頭
    const headers = {
      'Content-Type': 'application/json',
      'X-Client-Id': this.clientId,
      'X-Timestamp': timestamp,
      'X-Nonce': nonce,
      'X-Signature': signature
    };

    // 發送請求
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`HTTP ${response.status}: ${JSON.stringify(errorData)}`);
    }

    return response.json();
  }
}

export default SmartlyBridgeClient;
```

### 使用範例

```typescript
async function main() {
  // 初始化客戶端
  const client = new SmartlyBridgeClient(
    'http://homeassistant.local:8123',
    'ha_abc123def456',
    'your_secret_key'
  );

  try {
    // 範例 1: 開啟燈光並設定亮度和顏色
    const lightResult = await client.controlDevice(
      'light.bedroom',
      'turn_on',
      {
        brightness: 200,
        rgb_color: [255, 180, 100]
      },
      {
        user_id: 'u_123',
        role: 'tenant'
      }
    );
    console.log('✓ 燈光控制成功:', lightResult);

    // 範例 2: 設定空調溫度
    const climateResult = await client.controlDevice(
      'climate.living_room_ac',
      'set_temperature',
      {
        temperature: 24
      }
    );
    console.log('✓ 空調控制成功:', climateResult);

    // 範例 3: 開啟窗簾
    const coverResult = await client.controlDevice(
      'cover.living_room_curtain',
      'open_cover'
    );
    console.log('✓ 窗簾控制成功:', coverResult);

  } catch (error) {
    console.error('✗ 發生錯誤:', error);
  }
}

main();
```

---

## 瀏覽器環境範例

使用 Web Crypto API 的瀏覽器客戶端：

```javascript
/**
 * 瀏覽器環境的 Smartly Bridge Client
 * 使用 Web Crypto API
 */

class SmartlyBridgeBrowserClient {
  constructor(baseUrl, clientId, clientSecret) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.clientId = clientId;
    this.clientSecret = clientSecret;
  }

  async calculateSignature(method, path, timestamp, nonce, body) {
    // 計算 Body 的 SHA256
    const bodyJson = JSON.stringify(body);
    const bodyBuffer = new TextEncoder().encode(bodyJson);
    const bodyHashBuffer = await crypto.subtle.digest('SHA-256', bodyBuffer);
    const bodyHash = Array.from(new Uint8Array(bodyHashBuffer))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');

    // 組合 Payload
    const payload = `${method}\n${path}\n${timestamp}\n${nonce}\n${bodyHash}`;

    // 計算 HMAC-SHA256
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

    const signature = Array.from(new Uint8Array(signatureBuffer))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');

    return signature;
  }

  generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  async controlDevice(entityId, action, serviceData = {}, actor = null) {
    const method = 'POST';
    const path = '/api/smartly/control';
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const nonce = this.generateUUID();

    const body = {
      entity_id: entityId,
      action: action,
      service_data: serviceData
    };

    if (actor) {
      body.actor = actor;
    }

    const signature = await this.calculateSignature(method, path, timestamp, nonce, body);

    const headers = {
      'Content-Type': 'application/json',
      'X-Client-Id': this.clientId,
      'X-Timestamp': timestamp,
      'X-Nonce': nonce,
      'X-Signature': signature
    };

    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`HTTP ${response.status}: ${JSON.stringify(errorData)}`);
    }

    return response.json();
  }
}
```

### 瀏覽器使用範例

```javascript
// 使用範例
const client = new SmartlyBridgeBrowserClient(
  'http://homeassistant.local:8123',
  'ha_abc123def456',
  'your_secret_key'
);

client.controlDevice('light.bedroom', 'turn_on', { brightness: 200 })
  .then(result => console.log('成功:', result))
  .catch(error => console.error('錯誤:', error));
```

---

## 📚 相關文檔

- **[API 基礎與認證](./api-basics.md)** - 端點資訊與簽名計算
- **[設備類型控制](./device-types.md)** - 各設備類型的動作與參數
- **[回應格式](./responses.md)** - 成功與錯誤回應說明
- **[故障排除](./troubleshooting.md)** - 常見問題與解決方案

---

**返回**：[控制 API 指南](./README.md)
