# 回應格式

> **返回**：[控制 API 指南](./README.md)

本文檔說明 API 的成功回應格式與各種錯誤回應類型。

---

## 目錄

1. [成功回應](#成功回應)
2. [錯誤回應](#錯誤回應)
   - [400 Bad Request](#400-bad-request---請求格式錯誤)
   - [401 Unauthorized](#401-unauthorized---認證失敗)
   - [403 Forbidden](#403-forbidden---權限不足)
   - [404 Not Found](#404-not-found---實體不存在)
   - [422 Unprocessable Entity](#422-unprocessable-entity---服務調用失敗)
   - [429 Too Many Requests](#429-too-many-requests---超過速率限制)
   - [500 Internal Server Error](#500-internal-server-error---伺服器錯誤)
   - [503 Service Unavailable](#503-service-unavailable---服務不可用)

---

## 成功回應

### 200 OK

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

### 欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `success` | boolean | 是否成功，固定為 `true` |
| `entity_id` | string | 控制的實體 ID |
| `action` | string | 執行的動作 |
| `new_state` | string | 執行後的新狀態 |
| `new_attributes` | object | 執行後的實體屬性 |
| `timestamp` | string | 執行時間（ISO 8601 格式） |

---

## 錯誤回應

### 400 Bad Request - 請求格式錯誤

```json
{
  "error": "missing_required_fields",
  "message": "缺少必要欄位：entity_id",
  "details": {
    "missing_fields": ["entity_id"]
  }
}
```

#### 可能的錯誤碼

| 錯誤碼 | 說明 |
|--------|------|
| `invalid_json` | JSON 格式錯誤 |
| `missing_required_fields` | 缺少必要欄位（entity_id、action） |
| `invalid_entity_id` | 實體 ID 格式不正確 |
| `invalid_action` | 動作名稱不支援 |
| `invalid_service_data` | 服務參數格式錯誤 |

---

### 401 Unauthorized - 認證失敗

```json
{
  "error": "invalid_signature",
  "message": "HMAC 簽名驗證失敗"
}
```

#### 可能的錯誤碼

| 錯誤碼 | 說明 |
|--------|------|
| `missing_headers` | 缺少必要的 HTTP 標頭 |
| `invalid_client_id` | 客戶端 ID 不存在或無效 |
| `invalid_timestamp` | 時間戳無效或超出容許範圍（±30 秒） |
| `nonce_reused` | Nonce 已在 5 分鐘內使用過 |
| `invalid_signature` | HMAC-SHA256 簽名驗證失敗 |
| `ip_not_allowed` | IP 地址不在 CIDR 白名單中 |

---

### 403 Forbidden - 權限不足

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

#### 可能的錯誤碼

| 錯誤碼 | 說明 |
|--------|------|
| `entity_not_allowed` | 實體未標記為 `smartly` 標籤 |
| `service_not_allowed` | 服務不在允許清單中 |
| `acl_denied` | ACL 規則拒絕操作 |
| `insufficient_permissions` | 操作者權限不足 |

---

### 404 Not Found - 實體不存在

```json
{
  "error": "entity_not_found",
  "message": "找不到指定的實體",
  "details": {
    "entity_id": "light.nonexistent"
  }
}
```

---

### 422 Unprocessable Entity - 服務調用失敗

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

---

### 429 Too Many Requests - 超過速率限制

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

#### 回應標頭

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1735228845
Retry-After: 45
```

| 標頭 | 說明 |
|------|------|
| `X-RateLimit-Limit` | 速率限制上限 |
| `X-RateLimit-Remaining` | 剩餘可用次數 |
| `X-RateLimit-Reset` | 重置時間（Unix 時間戳） |
| `Retry-After` | 建議等待秒數 |

---

### 500 Internal Server Error - 伺服器錯誤

```json
{
  "error": "internal_server_error",
  "message": "伺服器發生內部錯誤",
  "details": {
    "request_id": "req_abc123def456"
  }
}
```

---

### 503 Service Unavailable - 服務不可用

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

## 錯誤處理最佳實踐

### Python 範例

```python
import requests

try:
    response = client.control_device(
        entity_id="light.bedroom",
        action="turn_on"
    )
    print("成功:", response)
    
except requests.HTTPError as e:
    status_code = e.response.status_code
    error_data = e.response.json()
    
    if status_code == 401:
        print("認證失敗:", error_data.get("message"))
    elif status_code == 403:
        print("權限不足:", error_data.get("message"))
    elif status_code == 429:
        retry_after = error_data.get("details", {}).get("retry_after", 60)
        print(f"速率限制，請等待 {retry_after} 秒")
    else:
        print(f"錯誤 {status_code}:", error_data)
```

### JavaScript 範例

```javascript
try {
  const result = await client.controlDevice('light.bedroom', 'turn_on');
  console.log('成功:', result);
  
} catch (error) {
  if (error.message.includes('401')) {
    console.error('認證失敗');
  } else if (error.message.includes('403')) {
    console.error('權限不足');
  } else if (error.message.includes('429')) {
    console.error('速率限制，請稍後重試');
  } else {
    console.error('錯誤:', error.message);
  }
}
```

---

## 📚 相關文檔

- **[API 基礎與認證](./api-basics.md)** - 端點資訊與簽名計算
- **[故障排除](./troubleshooting.md)** - 常見問題與解決方案
- **[安全指南](./security.md)** - 安全最佳實踐

---

**返回**：[控制 API 指南](./README.md)
