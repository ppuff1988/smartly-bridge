# API 基礎與認證機制

> **返回**：[控制 API 指南](./README.md)

本文檔說明 Smartly Bridge API 的端點資訊、請求結構與認證機制。

---

## 📡 端點資訊

```
POST /api/smartly/control
Content-Type: application/json
```

---

## 📋 必要的 HTTP 標頭

| 標頭 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `Content-Type` | string | 內容類型，必須為 `application/json` | `application/json` |
| `X-Client-Id` | string | 客戶端識別碼（由管理員配置） | `ha_abc123def456` |
| `X-Timestamp` | string | Unix 時間戳（秒，必須在伺服器時間 ±30 秒內） | `1735228800` |
| `X-Nonce` | string | UUID v4，每次請求唯一，5 分鐘內不可重複 | `550e8400-e29b-41d4-a716-446655440000` |
| `X-Signature` | string | HMAC-SHA256 簽名（小寫十六進位） | `a1b2c3d4e5f6789...` |

---

## 📦 請求 Body 結構

```json
{
  "command_id": "命令 ID（必填，用於冪等與追蹤）",
  "device_id": "邏輯設備 ID（必填）",
  "capability": "設備能力名稱（必填）",
  "command": "命令名稱（必填）",
  "params": {
    "參數名稱": "參數值（選填）"
  },
  "source": {
    "user_id": "操作者 ID（選填，用於審計）",
    "role": "操作者角色（選填）"
  }
}
```

### 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `command_id` | string | ✅ | 命令 ID，建議使用具唯一性的追蹤值，例如 `cmd_20260627_0001` |
| `device_id` | string | ✅ | API vNext 邏輯設備 ID，例如 `ldev_bedroom_light` |
| `capability` | string | ✅ | 要控制的能力，例如 `power`、`brightness`、`temperature` |
| `command` | string | ✅ | 要執行的命令，例如 `turn_on`、`set_brightness`、`set_temperature` |
| `params` | object | ❌ | 命令參數，依能力與命令而定 |
| `source` | object | ❌ | 操作者資訊，用於審計日誌 |
| `source.user_id` | string | ❌ | 操作者 ID |
| `source.role` | string | ❌ | 操作者角色（例如 `admin`、`tenant`） |

---

## 🔐 HMAC-SHA256 簽名計算

### Payload 格式

使用 `\n` 換行符連接以下欄位：

```
{METHOD}\n{PATH}\n{TIMESTAMP}\n{NONCE}\n{BODY_SHA256}
```

| 欄位 | 說明 |
|------|------|
| `METHOD` | HTTP 方法，固定為 `POST` |
| `PATH` | 請求路徑，固定為 `/api/smartly/control` |
| `TIMESTAMP` | Unix 時間戳（秒） |
| `NONCE` | UUID v4 字串 |
| `BODY_SHA256` | 請求 Body 的 SHA256 雜湊值（小寫十六進位） |

### Python 範例

```python
import hashlib
import hmac
import json

# 1. 計算 Body 的 SHA256 雜湊值
body = {
    "command_id": "cmd_20260627_0001",
    "device_id": "ldev_bedroom_light",
    "capability": "brightness",
    "command": "set_brightness",
    "params": {"value": 78},
    "source": {"user_id": "u_123", "role": "tenant"},
}
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

### JavaScript 範例

```javascript
import crypto from 'crypto';

// 1. 計算 Body 的 SHA256
const body = {
  command_id: "cmd_20260627_0001",
  device_id: "ldev_bedroom_light",
  capability: "brightness",
  command: "set_brightness",
  params: { value: 78 },
  source: { user_id: "u_123", role: "tenant" },
};
const bodyJson = JSON.stringify(body);
const bodyHash = crypto.createHash('sha256').update(bodyJson).digest('hex');

// 2. 組合 Payload
const method = "POST";
const path = "/api/smartly/control";
const timestamp = Math.floor(Date.now() / 1000).toString();
const nonce = crypto.randomUUID();
const payload = `${method}\n${path}\n${timestamp}\n${nonce}\n${bodyHash}`;

// 3. 計算 HMAC-SHA256
const clientSecret = "your_secret_key";
const signature = crypto
  .createHmac('sha256', clientSecret)
  .update(payload)
  .digest('hex');

console.log(`X-Signature: ${signature}`);
```

---

## ⚠️ 重要提醒

### Body JSON 格式

- Body JSON 必須與發送的內容**完全一致**（包括空格、換行、欄位順序）
- 建議使用 `json.dumps(separators=(',', ':'))` 移除多餘空格
- 使用 UTF-8 編碼

### 簽名格式

- 簽名必須使用**小寫十六進位字串**
- Python: `.hexdigest()`
- JavaScript: `.digest('hex')`

### 時間戳要求

- 時間戳必須在伺服器時間的 **±30 秒內**
- 確保客戶端時間同步（建議使用 NTP）

### Nonce 要求

- Nonce 在 **5 分鐘內不可重複使用**
- 必須使用 UUID v4 格式
- 每次請求都必須生成新的 Nonce

---

## 📚 相關文檔

- **[設備類型控制](./device-types.md)** - 各設備類型的動作與參數
- **[程式碼範例](./code-examples.md)** - 完整的實作範例
- **[安全指南](./security.md)** - 安全最佳實踐

---

**返回**：[控制 API 指南](./README.md)
