# 回應格式

> **返回**：[控制 API 指南](./README.md)

`/api/smartly/control` 回傳 API vNext envelope。成功與錯誤都使用相同 top-level 結構：`schema_version`、`data`、`warnings`、`errors`，必要時也會包含 request correlation 欄位。

---

## 成功回應

### 200 OK

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "accepted",
    "command_id": "cmd_20260627_0001",
    "device_id": "ldev_bedroom_light",
    "capability": "brightness",
    "command": "set_brightness",
    "adapter_id": "home_assistant",
    "correlation_id": "cmd_20260627_0001",
    "source_entity_id": "light.bedroom",
    "source_action": "turn_on",
    "expected_state": {
      "capability": "brightness",
      "value": 78
    },
    "new_state": "on",
    "new_attributes": {
      "brightness": 199
    }
  },
  "warnings": [],
  "errors": []
}
```

### 欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `schema_version` | string | API vNext schema 版本 |
| `data.status` | string | 命令處理狀態，例如 `accepted`、`failed` |
| `data.command_id` | string | 呼叫端提供的命令 ID |
| `data.device_id` | string | 邏輯設備 ID |
| `data.capability` | string | canonical capability |
| `data.command` | string | canonical command |
| `data.adapter_id` | string | 實際執行的 adapter |
| `data.correlation_id` | string | 命令追蹤 ID |
| `data.source_entity_id` | string | 診斷用 source trace |
| `data.source_action` | string | 診斷用 source execution trace |
| `data.expected_state` | object | Platform 可用於 optimistic UI 的預期狀態 |
| `warnings` | array | 非阻斷警告 |
| `errors` | array | 結構化錯誤陣列 |

---

## 錯誤回應

錯誤回應仍使用 API vNext envelope。HTTP status 反映 shell 或 application failure 類型，錯誤碼位於 `errors[].code`。

### 400 Bad Request

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "missing_required_fields",
      "message": "Missing required SmartlyCommand fields.",
      "target": "body"
    }
  ]
}
```

| 錯誤碼 | 說明 |
|--------|------|
| `invalid_json` | JSON 格式錯誤 |
| `missing_required_fields` | 缺少 `command_id`、`device_id`、`capability` 或 `command` |
| `invalid_command` | capability 不支援指定 command |
| `invalid_params` | command params 不符合 capability schema |

### 401 Unauthorized

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "invalid_signature",
      "message": "HMAC signature verification failed.",
      "target": "headers.X-Signature"
    }
  ]
}
```

| 錯誤碼 | 說明 |
|--------|------|
| `missing_headers` | 缺少必要 HTTP header |
| `invalid_client_id` | Client ID 不存在或無效 |
| `invalid_timestamp` | Timestamp 無效或超出容許範圍 |
| `nonce_reused` | Nonce 已在有效窗口內使用過 |
| `invalid_signature` | HMAC-SHA256 簽名驗證失敗 |
| `ip_not_allowed` | IP 地址不在 CIDR 白名單中 |

### 403 Forbidden

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected",
    "device_id": "ldev_bedroom_light"
  },
  "warnings": [],
  "errors": [
    {
      "code": "entity_not_allowed",
      "message": "Resolved source is not allowed for this client.",
      "target": "device_id"
    }
  ]
}
```

| 錯誤碼 | 說明 |
|--------|------|
| `entity_not_allowed` | resolved source 未授權給該 client |
| `service_not_allowed` | resolved source service 不在允許清單中 |
| `acl_denied` | ACL 規則拒絕操作 |
| `insufficient_permissions` | 操作者權限不足 |

### 404 Not Found

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected",
    "device_id": "ldev_missing"
  },
  "warnings": [],
  "errors": [
    {
      "code": "device_not_found",
      "message": "Logical device was not found.",
      "target": "device_id"
    }
  ]
}
```

### 422 Unprocessable Entity

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "failed",
    "device_id": "ldev_bedroom_light",
    "capability": "brightness",
    "command": "set_brightness"
  },
  "warnings": [],
  "errors": [
    {
      "code": "command_failed",
      "message": "Source command execution failed.",
      "target": "command"
    }
  ]
}
```

### 429 Too Many Requests

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected",
    "retry_after": 45
  },
  "warnings": [],
  "errors": [
    {
      "code": "rate_limited",
      "message": "Rate limit exceeded.",
      "target": "client"
    }
  ]
}
```

#### 回應標頭

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1735228845
Retry-After: 45
```

### 500 Internal Server Error

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "failed"
  },
  "warnings": [],
  "errors": [
    {
      "code": "internal_server_error",
      "message": "Internal server error.",
      "target": "server"
    }
  ],
  "request_id": "req_abc123def456"
}
```

### 503 Service Unavailable

```json
{
  "schema_version": "2026.06",
  "data": {
    "status": "failed"
  },
  "warnings": [],
  "errors": [
    {
      "code": "smartly_command_executor_unavailable",
      "message": "Smartly command executor is unavailable.",
      "target": "runtime_adapters.smartly_command_executor"
    }
  ]
}
```

---

## 錯誤處理最佳實踐

1. 先檢查 HTTP status，再讀取 `errors[]`。
2. 不要依賴任何 top-level `error` 或 `success` 欄位。
3. 對 `rate_limited` 使用 `Retry-After` 或 `data.retry_after`。
4. 對 `missing_required_fields`、`invalid_command`、`invalid_params` 顯示使用者可修正的表單錯誤。
5. 對 `command_failed` 顯示設備暫時無法執行，並保留 `command_id` 供追蹤。

---

**返回**：[控制 API 指南](./README.md)
