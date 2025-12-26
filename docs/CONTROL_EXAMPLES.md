# Home Assistant 設備控制類型與範例

本文檔列出所有支援的 Home Assistant 設備類型及其控制 API 範例。

## 📡 API 端點

```
POST /api/smartly/control
```

## 🔐 必要的 HTTP 標頭

| 標頭 | 說明 | 範例 |
|------|------|------|
| `X-Client-Id` | 客戶端 ID | `ha_abc123def456` |
| `X-Timestamp` | Unix 時間戳（秒） | `1735228800` |
| `X-Nonce` | UUID，每次請求唯一 | `550e8400-e29b-41d4-a716-446655440000` |
| `X-Signature` | HMAC-SHA256 簽名 | `a1b2c3d4e5f6...` |

---

## 1. Switch（開關）

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
curl -X POST "http://homeassistant.local:8123/api/smartly/control" \
  -H "Content-Type: application/json" \
  -H "X-Client-Id: ha_abc123def456" \
  -H "X-Timestamp: 1735228800" \
  -H "X-Nonce: 550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Signature: a1b2c3d4e5f6789abcdef..." \
  -d '{
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
```

### Python 範例

```python
import requests
import hashlib
import hmac
import time
import uuid
import json

# 配置
BASE_URL = "http://homeassistant.local:8123"
CLIENT_ID = "ha_abc123def456"
CLIENT_SECRET = "your_secret_key"

# 準備請求
method = "POST"
path = "/api/smartly/control"
timestamp = str(int(time.time()))
nonce = str(uuid.uuid4())

body = {
    "entity_id": "light.bedroom",
    "action": "turn_on",
    "service_data": {
        "brightness": 200
    },
    "actor": {
        "user_id": "u_123",
        "role": "tenant"
    }
}

body_json = json.dumps(body)
body_hash = hashlib.sha256(body_json.encode()).hexdigest()

# 計算簽名
payload = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
signature = hmac.new(
    CLIENT_SECRET.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

# 發送請求
headers = {
    "Content-Type": "application/json",
    "X-Client-Id": CLIENT_ID,
    "X-Timestamp": timestamp,
    "X-Nonce": nonce,
    "X-Signature": signature
}

response = requests.post(
    f"{BASE_URL}{path}",
    headers=headers,
    json=body
)

print(response.json())
```

### JavaScript 範例

```javascript
const crypto = require('crypto');

const BASE_URL = 'http://homeassistant.local:8123';
const CLIENT_ID = 'ha_abc123def456';
const CLIENT_SECRET = 'your_secret_key';

async function controlDevice(entityId, action, serviceData = {}) {
  const method = 'POST';
  const path = '/api/smartly/control';
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const nonce = crypto.randomUUID();
  
  const body = {
    entity_id: entityId,
    action: action,
    service_data: serviceData,
    actor: {
      user_id: 'u_123',
      role: 'tenant'
    }
  };
  
  const bodyJson = JSON.stringify(body);
  const bodyHash = crypto.createHash('sha256').update(bodyJson).digest('hex');
  
  const payload = `${method}\n${path}\n${timestamp}\n${nonce}\n${bodyHash}`;
  const signature = crypto
    .createHmac('sha256', CLIENT_SECRET)
    .update(payload)
    .digest('hex');
  
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Client-Id': CLIENT_ID,
      'X-Timestamp': timestamp,
      'X-Nonce': nonce,
      'X-Signature': signature
    },
    body: bodyJson
  });
  
  return response.json();
}

// 使用範例
controlDevice('light.bedroom', 'turn_on', { brightness: 200 })
  .then(result => console.log(result))
  .catch(error => console.error(error));
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
    "friendly_name": "Bedroom Light"
  }
}
```

### 錯誤回應

#### 401 Unauthorized - 認證失敗
```json
{
  "error": "invalid_signature"
}
```

可能的錯誤碼：
- `missing_headers` - 缺少必要的標頭
- `invalid_timestamp` - 時間戳無效或超出容許範圍
- `nonce_reused` - Nonce 已被使用
- `invalid_signature` - 簽名驗證失敗
- `ip_not_allowed` - IP 地址不在允許清單中

#### 403 Forbidden - 權限不足
```json
{
  "error": "entity_not_allowed"
}
```

可能的錯誤碼：
- `entity_not_allowed` - 實體未標記為 `smartly` 標籤
- `service_not_allowed` - 服務不在允許清單中

#### 400 Bad Request - 請求格式錯誤
```json
{
  "error": "missing_required_fields"
}
```

可能的錯誤碼：
- `invalid_json` - JSON 格式錯誤
- `missing_required_fields` - 缺少必要欄位

#### 429 Too Many Requests - 超過速率限制
```json
{
  "error": "rate_limited"
}
```

標頭：
- `Retry-After: 60`
- `X-RateLimit-Remaining: 0`

#### 500 Internal Server Error - 服務調用失敗
```json
{
  "error": "service_call_failed"
}
```

---

## 🔒 安全注意事項

1. **HMAC 簽名**：所有請求必須包含有效的 HMAC-SHA256 簽名
2. **時間戳驗證**：時間戳必須在伺服器時間的 ±30 秒內
3. **Nonce 防重放**：每個 Nonce 只能使用一次，5 分鐘內不可重複
4. **IP 白名單**：可選配置允許的 CIDR 範圍
5. **速率限制**：預設每分鐘 60 次請求

---

## 📚 相關文檔

- [OpenAPI 規格](./openapi.yaml)
- [認證機制說明](../README.md#authentication)
- [配置指南](../README.md#configuration)
- [安全最佳實踐](../SECURITY.md)

---

## 🆘 故障排除

### 常見問題

#### 1. 簽名驗證失敗
- 確認 `client_secret` 正確
- 檢查簽名計算的 payload 格式
- 確保 body 的 SHA256 雜湊值正確

#### 2. 實體不允許控制
- 確認實體已添加 `smartly` 標籤
- 在 Home Assistant 介面：設定 → 實體 → 選擇實體 → 標籤

#### 3. 服務不允許
- 檢查 `const.py` 中的 `ALLOWED_SERVICES` 配置
- 確認動作名稱正確（例如 `turn_on` 而非 `turnOn`）

#### 4. 時間戳錯誤
- 同步伺服器時間
- 使用 NTP 服務確保時間準確

---

## 📝 更新記錄

- **2025-12-26**：初始版本，包含 9 種設備類型的完整範例
