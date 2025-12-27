# Home Assistant 設備控制 API 完整指南

> ⚠️ **本文檔已重新整理**
> 
> 為提升可讀性，本指南已拆分為多個子文檔。請前往 **[control/](./control/)** 資料夾查看完整內容。

---

## 📖 文檔導覽

| 文檔 | 說明 |
|------|------|
| **[控制 API 指南](./control/README.md)** | 主要索引頁面 |
| **[API 基礎與認證](./control/api-basics.md)** | 端點資訊、HTTP 標頭、HMAC-SHA256 簽名計算 |
| **[設備類型控制](./control/device-types.md)** | 9 種設備類型的動作與參數說明 |
| **[程式碼範例](./control/code-examples.md)** | cURL、Python、JavaScript/TypeScript 實作範例 |
| **[回應格式](./control/responses.md)** | 成功回應、錯誤回應與 HTTP 狀態碼 |
| **[安全指南](./control/security.md)** | 安全最佳實踐、IP 白名單、ACL、審計日誌 |
| **[故障排除](./control/troubleshooting.md)** | 常見問題與解決方案 |

---

## 🚀 快速開始

請前往 **[控制 API 指南](./control/README.md)** 開始使用。

---

> **以下為舊版內容（已棄用），請參考上方連結查看最新文檔。**

---

## 📡 API 基礎（已棄用）

### 端點資訊

```
POST /api/smartly/control
Content-Type: application/json
```

### 必要的 HTTP 標頭

| 標頭 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `Content-Type` | string | 內容類型，必須為 `application/json` | `application/json` |
| `X-Client-Id` | string | 客戶端識別碼（由管理員配置） | `ha_abc123def456` |
| `X-Timestamp` | string | Unix 時間戳（秒，必須在伺服器時間 ±30 秒內） | `1735228800` |
| `X-Nonce` | string | UUID v4，每次請求唯一，5 分鐘內不可重複 | `550e8400-e29b-41d4-a716-446655440000` |
| `X-Signature` | string | HMAC-SHA256 簽名（小寫十六進位） | `a1b2c3d4e5f6789...` |

### 請求 Body 結構

```json
{
  "entity_id": "設備實體 ID（必填）",
  "action": "動作名稱（必填）",
  "service_data": {
    "參數名稱": "參數值（選填）"
  },
  "actor": {
    "user_id": "操作者 ID（選填，用於審計）",
    "role": "操作者角色（選填）"
  }
}
```

---

## 🔐 認證機制

### HMAC-SHA256 簽名計算

**Payload 格式**（使用 `\n` 換行符連接）：

```
{METHOD}\n{PATH}\n{TIMESTAMP}\n{NONCE}\n{BODY_SHA256}
```

**範例**：

```python
import hashlib
import hmac
import json

# 1. 計算 Body 的 SHA256 雜湊值
body = {"entity_id": "light.bedroom", "action": "turn_on", "service_data": {}}
body_json = json.dumps(body, separators=(',', ':'))  # 不含空格
body_hash = hashlib.sha256(body_json.encode()).hexdigest()

# 2. 組合 Payload
method = "POST"
path = "/api/smartly/control"
timestamp = "1735228800"
nonce = "550e8400-e29b-41d4-a716-446655440000"
payload = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"

# 3. 使用 HMAC-SHA256 計算簽名
client_secret = "your_secret_key"
signature = hmac.new(
    client_secret.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

print(f"X-Signature: {signature}")
```

**重要提醒**：

- Body JSON 必須與發送的內容完全一致（包括空格、換行、欄位順序）
- 簽名必須使用小寫十六進位字串
- 時間戳必須在伺服器時間的 **±30 秒內**
- Nonce 在 **5 分鐘內不可重複使用**

---

## 🎯 設備類型

---

## 1. Switch（開關）

**適用設備**：智慧插座、電源開關、繼電器模組等

**領域（Domain）**：`switch`

### 支援的動作
- `turn_on` - 開啟
- `turn_off` - 關閉
- `toggle` - 切換狀態

### 範例

#### 開啟開關
```json
{
  "entity_id": "switch.living_room_light",
  "action": "turn_on",
  "service_data": {},
  "actor": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

#### 關閉開關
```json
{
  "entity_id": "switch.living_room_light",
  "action": "turn_off",
  "service_data": {}
}
```

#### 切換開關
```json
{
  "entity_id": "switch.living_room_light",
  "action": "toggle",
  "service_data": {}
}
```

---

## 2. Light（燈光）

**適用設備**：智慧燈泡、LED 燈條、調光器、RGB 燈等

**領域（Domain）**：`light`

### 支援的動作
- `turn_on` - 開啟
- `turn_off` - 關閉
- `toggle` - 切換狀態

### 範例

#### 開啟燈光（基本）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {}
}
```

#### 開啟燈光（設定亮度）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 255
  }
}
```

#### 開啟燈光（設定 RGB 顏色）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 200,
    "rgb_color": [255, 0, 0]
  }
}
```

#### 開啟燈光（設定色溫）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 180,
    "color_temp": 370
  }
}
```

#### 開啟燈光（漸變效果）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 255,
    "transition": 2
  }
}
```

#### 關閉燈光
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_off",
  "service_data": {}
}
```

### Light 參數說明

| 參數 | 類型 | 範圍 | 說明 |
|------|------|------|------|
| `brightness` | integer | 0-255 | 亮度值，0 為最暗，255 為最亮 |
| `rgb_color` | array | [0-255, 0-255, 0-255] | RGB 顏色，例如 [255, 0, 0] 為紅色 |
| `color_temp` | integer | 153-500 | 色溫（mireds），153 為冷白光，500 為暖黃光 |
| `kelvin` | integer | 2000-6500 | 色溫（Kelvin） |
| `hs_color` | array | [0-360, 0-100] | HSV 色彩空間的色相和飽和度 |
| `xy_color` | array | [0-1, 0-1] | CIE 1931 色彩空間座標 |
| `transition` | integer | 0+ | 漸變時間（秒） |

---

## 3. Cover（窗簾/捲簾/車庫門）

**適用設備**：電動窗簾、捲簾、百葉窗、車庫門、天窗等

**領域（Domain）**：`cover`

### 支援的動作
- `open_cover` - 打開
- `close_cover` - 關閉
- `stop_cover` - 停止移動
- `set_cover_position` - 設定位置

### 範例

#### 打開窗簾
```json
{
  "entity_id": "cover.living_room_curtain",
  "action": "open_cover",
  "service_data": {}
}
```

#### 關閉窗簾
```json
{
  "entity_id": "cover.living_room_curtain",
  "action": "close_cover",
  "service_data": {}
}
```

#### 停止移動
```json
{
  "entity_id": "cover.living_room_curtain",
  "action": "stop_cover",
  "service_data": {}
}
```

#### 設定位置
```json
{
  "entity_id": "cover.living_room_curtain",
  "action": "set_cover_position",
  "service_data": {
    "position": 50
  }
}
```

### Cover 參數說明

| 參數 | 類型 | 範圍 | 說明 |
|------|------|------|------|
| `position` | integer | 0-100 | 位置百分比，0=完全關閉，100=完全打開 |
| `tilt_position` | integer | 0-100 | 傾斜角度百分比（適用於百葉窗） |

---

## 4. Climate（空調/恆溫器/暖氣）

**適用設備**：空調、恆溫器、暖氣系統、熱泵、地暖控制器等

**領域（Domain）**：`climate`

### 支援的動作
- `set_temperature` - 設定溫度
- `set_hvac_mode` - 設定 HVAC 模式
- `set_fan_mode` - 設定風扇模式

### 範例

#### 設定溫度
```json
{
  "entity_id": "climate.living_room_ac",
  "action": "set_temperature",
  "service_data": {
    "temperature": 24
  }
}
```

#### 設定溫度範圍（冷暖兩用）
```json
{
  "entity_id": "climate.living_room_ac",
  "action": "set_temperature",
  "service_data": {
    "target_temp_high": 26,
    "target_temp_low": 22
  }
}
```

#### 設定 HVAC 模式
```json
{
  "entity_id": "climate.living_room_ac",
  "action": "set_hvac_mode",
  "service_data": {
    "hvac_mode": "cool"
  }
}
```

#### 設定風扇模式
```json
{
  "entity_id": "climate.living_room_ac",
  "action": "set_fan_mode",
  "service_data": {
    "fan_mode": "auto"
  }
}
```

### Climate 參數說明

| 參數 | 類型 | 說明 | 可能的值 |
|------|------|------|----------|
| `temperature` | float | 目標溫度 | 依設備而定，例如 16-30 |
| `target_temp_high` | float | 目標最高溫度（冷暖模式） | 依設備而定 |
| `target_temp_low` | float | 目標最低溫度（冷暖模式） | 依設備而定 |
| `hvac_mode` | string | HVAC 模式 | `off`, `heat`, `cool`, `heat_cool`, `auto`, `dry`, `fan_only` |
| `fan_mode` | string | 風扇模式 | `auto`, `low`, `medium`, `high`, `middle`, `focus`, `diffuse` |
| `preset_mode` | string | 預設模式 | `eco`, `away`, `boost`, `comfort`, `home`, `sleep` |
| `swing_mode` | string | 擺風模式 | `off`, `vertical`, `horizontal`, `both` |

---

## 5. Fan（風扇）

**適用設備**：電風扇、吊扇、換氣扇、循環扇等

**領域（Domain）**：`fan`

### 支援的動作
- `turn_on` - 開啟
- `turn_off` - 關閉
- `set_percentage` - 設定風速百分比
- `set_preset_mode` - 設定預設模式

### 範例

#### 開啟風扇
```json
{
  "entity_id": "fan.bedroom_fan",
  "action": "turn_on",
  "service_data": {}
}
```

#### 關閉風扇
```json
{
  "entity_id": "fan.bedroom_fan",
  "action": "turn_off",
  "service_data": {}
}
```

#### 設定風速
```json
{
  "entity_id": "fan.bedroom_fan",
  "action": "set_percentage",
  "service_data": {
    "percentage": 75
  }
}
```

#### 設定預設模式
```json
{
  "entity_id": "fan.bedroom_fan",
  "action": "set_preset_mode",
  "service_data": {
    "preset_mode": "sleep"
  }
}
```

### Fan 參數說明

| 參數 | 類型 | 範圍/值 | 說明 |
|------|------|---------|------|
| `percentage` | integer | 0-100 | 風速百分比，0 為關閉，100 為最大風速 |
| `preset_mode` | string | 依設備 | 預設模式，例如 `sleep`, `normal`, `turbo`, `natural` |
| `direction` | string | `forward`, `reverse` | 風扇旋轉方向 |
| `oscillating` | boolean | true/false | 是否擺頭 |

---

## 6. Lock（門鎖）

**適用設備**：智慧門鎖、電子鎖、磁力鎖等

**領域（Domain）**：`lock`

### 支援的動作
- `lock` - 上鎖
- `unlock` - 解鎖

### 範例

#### 上鎖
```json
{
  "entity_id": "lock.front_door",
  "action": "lock",
  "service_data": {}
}
```

#### 解鎖
```json
{
  "entity_id": "lock.front_door",
  "action": "unlock",
  "service_data": {}
}
```

#### 解鎖（使用密碼）
```json
{
  "entity_id": "lock.front_door",
  "action": "unlock",
  "service_data": {
    "code": "1234"
  }
}
```

### Lock 參數說明

| 參數 | 類型 | 說明 |
|------|------|------|
| `code` | string | 解鎖密碼（可選） |

---

## 7. Scene（場景）

**適用場景**：預設的多設備聯動狀態組合（如「電影模式」、「離家模式」等）

**領域（Domain）**：`scene`

### 支援的動作
- `turn_on` - 啟動場景

### 範例

#### 啟動場景
```json
{
  "entity_id": "scene.movie_night",
  "action": "turn_on",
  "service_data": {}
}
```

#### 啟動場景（設定漸變）
```json
{
  "entity_id": "scene.romantic_dinner",
  "action": "turn_on",
  "service_data": {
    "transition": 3
  }
}
```

### Scene 參數說明

| 參數 | 類型 | 說明 |
|------|------|------|
| `transition` | integer | 場景切換的漸變時間（秒） |

---

## 8. Script（腳本）

**適用場景**：自定義的動作序列、複雜的自動化邏輯等

**領域（Domain）**：`script`

### 支援的動作
- `turn_on` - 執行腳本
- `turn_off` - 停止腳本

### 範例

#### 執行腳本
```json
{
  "entity_id": "script.morning_routine",
  "action": "turn_on",
  "service_data": {}
}
```

#### 執行腳本（傳遞變數）
```json
{
  "entity_id": "script.notify_user",
  "action": "turn_on",
  "service_data": {
    "variables": {
      "message": "Hello from API",
      "title": "Notification"
    }
  }
}
```

#### 停止腳本
```json
{
  "entity_id": "script.morning_routine",
  "action": "turn_off",
  "service_data": {}
}
```

---

## 9. Automation（自動化）

**適用場景**：事件驅動的自動化規則管理

**領域（Domain）**：`automation`

### 支援的動作
- `trigger` - 觸發自動化
- `turn_on` - 啟用自動化
- `turn_off` - 停用自動化

### 範例

#### 觸發自動化
```json
{
  "entity_id": "automation.motion_light",
  "action": "trigger",
  "service_data": {}
}
```

#### 觸發自動化（跳過條件）
```json
{
  "entity_id": "automation.motion_light",
  "action": "trigger",
  "service_data": {
    "skip_condition": true
  }
}
```

#### 啟用自動化
```json
{
  "entity_id": "automation.motion_light",
  "action": "turn_on",
  "service_data": {}
}
```

#### 停用自動化
```json
{
  "entity_id": "automation.motion_light",
  "action": "turn_off",
  "service_data": {}
}
```

### Automation 參數說明

| 參數 | 類型 | 說明 |
|------|------|------|
| `skip_condition` | boolean | 是否跳過條件檢查，直接執行動作 |

---

## 📋 完整 HTTP 請求範例

### cURL 範例

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

### Python 範例

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


# 使用範例
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

### JavaScript/TypeScript 範例

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

// 使用範例
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

// 執行範例
main();
```

### 瀏覽器環境（使用 Web Crypto API）

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

## 📤 回應格式

### 成功回應（200 OK）

```json
{
  "success": true,
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "new_state": "on",
  "new_attributes": {
    "brightness": 200,
    "rgb_color": [255, 180, 100],
    "color_mode": "rgb",
    "supported_color_modes": ["rgb", "color_temp"],
    "friendly_name": "臥室燈光"
  },
  "timestamp": "2025-12-27T10:30:45.123456+00:00"
}
```

### 錯誤回應

#### 400 Bad Request - 請求格式錯誤

```json
{
  "error": "missing_required_fields",
  "message": "缺少必要欄位：entity_id",
  "details": {
    "missing_fields": ["entity_id"]
  }
}
```

**可能的錯誤碼**：
- `invalid_json` - JSON 格式錯誤
- `missing_required_fields` - 缺少必要欄位（entity_id、action）
- `invalid_entity_id` - 實體 ID 格式不正確
- `invalid_action` - 動作名稱不支援
- `invalid_service_data` - 服務參數格式錯誤

#### 401 Unauthorized - 認證失敗

```json
{
  "error": "invalid_signature",
  "message": "HMAC 簽名驗證失敗"
}
```

**可能的錯誤碼**：
- `missing_headers` - 缺少必要的 HTTP 標頭
- `invalid_client_id` - 客戶端 ID 不存在或無效
- `invalid_timestamp` - 時間戳無效或超出容許範圍（±30 秒）
- `nonce_reused` - Nonce 已在 5 分鐘內使用過
- `invalid_signature` - HMAC-SHA256 簽名驗證失敗
- `ip_not_allowed` - IP 地址不在 CIDR 白名單中

#### 403 Forbidden - 權限不足

```json
{
  "error": "entity_not_allowed",
  "message": "實體未標記為 smartly 標籤",
  "details": {
    "entity_id": "light.bedroom",
    "required_label": "smartly"
  }
}
```

**可能的錯誤碼**：
- `entity_not_allowed` - 實體未標記為 `smartly` 標籤
- `service_not_allowed` - 服務不在允許清單中
- `acl_denied` - ACL 規則拒絕操作
- `insufficient_permissions` - 操作者權限不足

#### 404 Not Found - 實體不存在

```json
{
  "error": "entity_not_found",
  "message": "找不到指定的實體",
  "details": {
    "entity_id": "light.nonexistent"
  }
}
```

#### 422 Unprocessable Entity - 服務調用失敗

```json
{
  "error": "service_call_failed",
  "message": "設備回應錯誤",
  "details": {
    "entity_id": "light.bedroom",
    "action": "turn_on",
    "reason": "設備離線"
  }
}
```

#### 429 Too Many Requests - 超過速率限制

```json
{
  "error": "rate_limited",
  "message": "超過速率限制，請稍後再試",
  "details": {
    "limit": 60,
    "window": "60s",
    "retry_after": 45
  }
}
```

**回應標頭**：
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1735228845
Retry-After: 45
```

#### 500 Internal Server Error - 伺服器錯誤

```json
{
  "error": "internal_server_error",
  "message": "伺服器發生內部錯誤",
  "details": {
    "request_id": "req_abc123def456"
  }
}
```

#### 503 Service Unavailable - 服務不可用

```json
{
  "error": "service_unavailable",
  "message": "Home Assistant 服務暫時無法使用",
  "details": {
    "retry_after": 60
  }
}
```

---

## 🔒 安全注意事項

### 1. HMAC 簽名安全

- **密鑰管理**：
  - ✅ 使用強隨機密鑰（至少 32 字元）
  - ✅ 定期輪換密鑰
  - ✅ 使用環境變數或密鑰管理服務存儲密鑰
  - ❌ 永不將密鑰硬編碼在程式碼中
  - ❌ 永不透過 GET 參數或 URL 傳遞密鑰

- **簽名計算**：
  - ✅ 確保 Body JSON 與發送的內容完全一致
  - ✅ 使用 UTF-8 編碼
  - ✅ 簽名必須使用小寫十六進位字串
  - ✅ 每次請求使用新的 Nonce

### 2. 時間戳與 Nonce

- **時間戳驗證**：
  - 伺服器允許時間戳在 **±30 秒**內
  - 確保客戶端時間同步（使用 NTP）
  - 時間偏移過大會導致所有請求失敗

- **Nonce 防重放**：
  - 每個 Nonce 在 **5 分鐘內只能使用一次**
  - 使用 UUID v4 格式
  - 伺服器會記錄並檢查 Nonce

### 3. IP 白名單

配置 `allowed_cidr` 限制允許的來源 IP：

```yaml
# configuration.yaml
smartly_bridge:
  clients:
    - client_id: ha_abc123
      client_secret: your_secret
      allowed_cidr:
        - "192.168.1.0/24"    # 本地網路
        - "10.0.0.100/32"     # 特定 IP
```

### 4. 速率限制

預設配置：
- **每分鐘 60 次請求**（可自訂）
- 超過限制將收到 `429 Too Many Requests`
- 建議實作指數退避重試機制

```python
# 指數退避範例
import time

def call_api_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)
            else:
                raise
```

### 5. HTTPS 使用建議

- ✅ **生產環境必須使用 HTTPS**
- ✅ 使用有效的 SSL/TLS 憑證
- ✅ 啟用 HSTS（HTTP Strict Transport Security）
- ❌ 避免在公網上使用 HTTP

```yaml
# configuration.yaml
http:
  ssl_certificate: /path/to/fullchain.pem
  ssl_key: /path/to/privkey.pem
```

### 6. 實體標籤控制

只有標記為 `smartly` 的實體才能被控制：

**在 Home Assistant 介面設定**：
1. 設定 → 實體
2. 選擇要開放的實體
3. 點選「標籤」
4. 新增或選擇 `smartly` 標籤

**透過 YAML 設定**：
```yaml
# configuration.yaml
label:
  smartly:
    name: Smartly 可控制
    icon: mdi:api
```

### 7. 審計日誌

所有 API 請求都會記錄在審計日誌中：

```yaml
# 啟用審計日誌
smartly_bridge:
  audit:
    enabled: true
    level: info  # debug, info, warning, error
```

查看日誌：
```bash
# 檢視 Home Assistant 日誌
tail -f /config/home-assistant.log | grep smartly
```

### 8. ACL（存取控制清單）

設定細緻化的權限控制：

```yaml
smartly_bridge:
  acl:
    - entity_id: "light.*"
      allowed_actions: ["turn_on", "turn_off"]
      allowed_roles: ["admin", "tenant"]
    
    - entity_id: "climate.*"
      allowed_actions: ["set_temperature"]
      allowed_roles: ["admin"]
      
    - entity_id: "lock.*"
      allowed_actions: ["unlock"]
      denied: true  # 拒絕所有解鎖操作
```

### 9. 安全檢查清單

部署前確認：

- [ ] 已設定強隨機的 `client_secret`
- [ ] 已配置 IP 白名單或防火牆規則
- [ ] 生產環境使用 HTTPS
- [ ] 已啟用審計日誌
- [ ] 已設定實體標籤控制
- [ ] 已配置適當的 ACL 規則
- [ ] 已測試速率限制機制
- [ ] 已同步伺服器時間（NTP）
- [ ] 已定期檢查日誌異常活動

---

## 📚 相關文檔

- [OpenAPI 規格](./openapi.yaml)
- [認證機制說明](../README.md#authentication)
- [配置指南](../README.md#configuration)
- [安全最佳實踐](../SECURITY.md)

---

## 🆘 故障排除

### 常見問題與解決方案

#### 1. 簽名驗證失敗（`invalid_signature`）

**症狀**：收到 401 錯誤，錯誤訊息為 `invalid_signature`

**可能原因與解決方案**：

| 原因 | 解決方案 | 驗證方法 |
|------|---------|---------|
| `client_secret` 錯誤 | 確認密鑰與伺服器配置一致 | 檢查 `secrets.yaml` 中的配置 |
| Body JSON 格式不一致 | 確保 JSON 不含多餘空格/換行 | 使用 `json.dumps(separators=(',', ':'))` |
| 簽名計算錯誤 | 檢查 Payload 組合順序 | 參考範例程式碼 |
| 編碼問題 | 使用 UTF-8 編碼 | `str.encode('utf-8')` |
| 大小寫錯誤 | 簽名必須是小寫十六進位 | `.hexdigest()` 或 `.toLowerCase()` |

**除錯步驟**：

```python
# 1. 印出簽名計算過程
print(f"Method: {method}")
print(f"Path: {path}")
print(f"Timestamp: {timestamp}")
print(f"Nonce: {nonce}")
print(f"Body JSON: {body_json}")
print(f"Body Hash: {body_hash}")
print(f"Payload: {payload}")
print(f"Signature: {signature}")

# 2. 在伺服器端啟用 debug 日誌
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.smartly_bridge.auth: debug
```

#### 2. 實體不允許控制（`entity_not_allowed`）

**症狀**：收到 403 錯誤，錯誤訊息為 `entity_not_allowed`

**解決方案**：

1. **檢查實體是否存在**：
   ```bash
   # 在 Home Assistant 開發者工具 → 狀態 中搜尋實體 ID
   ```

2. **確認實體已添加 `smartly` 標籤**：
   - 方法 1：介面操作
     - 設定 → 實體 → 選擇實體 → 標籤 → 新增 `smartly`
   
   - 方法 2：檢查 `labels` 資料夾
     ```bash
     cat .storage/core.entity_registry
     ```

3. **重新載入整合**：
   ```
   設定 → 裝置與服務 → Smartly Bridge → 重新載入
   ```

#### 3. 服務不允許（`service_not_allowed`）

**症狀**：收到 403 錯誤，錯誤訊息為 `service_not_allowed`

**解決方案**：

1. **確認動作名稱正確**：
   - ✅ `turn_on`（小寫，底線分隔）
   - ❌ `turnOn`（駝峰式）
   - ❌ `TURN_ON`（大寫）

2. **檢查允許的服務清單**：
   ```python
   # custom_components/smartly_bridge/const.py
   ALLOWED_SERVICES = {
       "switch": ["turn_on", "turn_off", "toggle"],
       "light": ["turn_on", "turn_off", "toggle"],
       # ...
   }
   ```

3. **檢查設備支援的功能**：
   - 開發者工具 → 服務 → 選擇設備 → 查看可用服務

#### 4. 時間戳錯誤（`invalid_timestamp`）

**症狀**：收到 401 錯誤，錯誤訊息為 `invalid_timestamp`

**原因**：客戶端時間與伺服器時間差異超過 30 秒

**解決方案**：

1. **同步系統時間**：
   ```bash
   # Linux/macOS
   sudo ntpdate pool.ntp.org
   
   # 或使用 systemd-timesyncd
   sudo timedatectl set-ntp true
   
   # Windows
   w32tm /resync
   ```

2. **檢查時區設定**：
   ```python
   import time
   print(f"當前 Unix 時間戳: {int(time.time())}")
   ```

3. **比對伺服器時間**：
   ```bash
   curl -I http://homeassistant.local:8123
   # 檢查 Date 標頭
   ```

#### 5. Nonce 重複使用（`nonce_reused`）

**症狀**：收到 401 錯誤，錯誤訊息為 `nonce_reused`

**原因**：同一個 Nonce 在 5 分鐘內被使用多次

**解決方案**：

1. **確保每次請求生成新的 UUID**：
   ```python
   # ✅ 正確
   nonce = str(uuid.uuid4())
   
   # ❌ 錯誤：重複使用
   nonce = "fixed-nonce-12345"
   ```

2. **檢查是否有重試邏輯**：
   ```python
   # 重試時必須生成新的 nonce 和 timestamp
   def retry_request():
       timestamp = str(int(time.time()))
       nonce = str(uuid.uuid4())  # 新的 nonce
       # ...
   ```

#### 6. 速率限制（`rate_limited`）

**症狀**：收到 429 錯誤，錯誤訊息為 `rate_limited`

**解決方案**：

1. **實作重試機制**：
   ```python
   import time
   
   response = requests.post(url, headers=headers, json=body)
   if response.status_code == 429:
       retry_after = int(response.headers.get('Retry-After', 60))
       time.sleep(retry_after)
       response = requests.post(url, headers=headers, json=body)
   ```

2. **調整速率限制**：
   ```yaml
   # configuration.yaml
   smartly_bridge:
     rate_limit:
       requests_per_minute: 120  # 預設 60
   ```

### 除錯工具

#### 測試簽名計算

```python
#!/usr/bin/env python3
"""簽名計算測試工具"""

import hashlib
import hmac
import json

def test_signature():
    # 配置
    client_secret = "your_secret_key"
    method = "POST"
    path = "/api/smartly/control"
    timestamp = "1735228800"
    nonce = "550e8400-e29b-41d4-a716-446655440000"
    
    body = {
        "entity_id": "light.bedroom",
        "action": "turn_on",
        "service_data": {}
    }
    
    # 計算
    body_json = json.dumps(body, separators=(',', ':'))
    body_hash = hashlib.sha256(body_json.encode()).hexdigest()
    payload = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    signature = hmac.new(
        client_secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    print("=== 簽名計算測試 ===")
    print(f"Body JSON: {body_json}")
    print(f"Body Hash: {body_hash}")
    print(f"Payload:\n{payload}")
    print(f"Signature: {signature}")

if __name__ == "__main__":
    test_signature()
```

### 取得協助

如果問題仍未解決：

1. **檢查 GitHub Issues**：[專案 Issues 頁面](https://github.com/your-repo/smartly-bridge/issues)

2. **提交問題時請包含**：
   - Home Assistant 版本
   - Smartly Bridge 版本
   - 完整錯誤訊息（隱藏敏感資訊）
   - 相關日誌片段
   - 最小化重現步驟

---

## 📚 相關文檔

- **[OpenAPI 規格](./openapi.yaml)** - 完整的 API 規格定義
- **[README.md](../README.md)** - 專案概覽與快速開始
- **[SECURITY.md](../SECURITY.md)** - 安全最佳實踐與漏洞回報
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - 貢獻指南
- **[Home Assistant 開發文檔](https://developers.home-assistant.io/)** - 官方開發資源

---

## 📝 更新記錄

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| **v1.0.0** | 2025-12-27 | • 完整重寫文檔結構<br>• 新增完整的 Python/JS/TypeScript 範例<br>• 擴充故障排除章節<br>• 新增安全最佳實踐<br>• 改進回應格式說明 |
| **v0.1.0** | 2025-12-26 | • 初始版本<br>• 包含 9 種設備類型的基本範例 |

---

## 🤝 貢獻

歡迎提交 Issue 或 Pull Request 來改進這份文檔！

**貢獻指南**：
1. Fork 本專案
2. 建立功能分支（`git checkout -b feature/improve-docs`）
3. 提交變更（`git commit -m 'docs: 改進控制範例說明'`）
4. 推送到分支（`git push origin feature/improve-docs`）
5. 建立 Pull Request

---

## 📄 授權

本專案採用 MIT License - 詳見 [LICENSE](../LICENSE) 檔案。

---

**製作**：Smartly Bridge Team  
**維護**：[@your-username](https://github.com/your-username)  
**最後更新**：2025-12-27
