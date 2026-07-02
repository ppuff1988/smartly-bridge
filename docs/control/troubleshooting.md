# 故障排除

> **返回**：[控制 API 指南](./README.md)

本文檔列出 `/api/smartly/control` API vNext 常見問題與排查方式。

---

## 1. 簽名驗證失敗

### 症狀

HTTP 401，`errors[].code` 為 `invalid_signature`。

### 檢查項目

- Body JSON 必須與送出的內容完全一致。
- HMAC payload 格式必須是 `{METHOD}\n{PATH}\n{TIMESTAMP}\n{NONCE}\n{BODY_SHA256}`。
- `X-Signature` 必須是小寫十六進位。
- Client secret 必須與 Home Assistant 設定一致。

---

## 2. Timestamp 或 Nonce 無效

| 錯誤碼 | 原因 | 解法 |
|--------|------|------|
| `invalid_timestamp` | 時間差超過允許窗口 | 對齊 NTP，重新送出 |
| `nonce_reused` | 同一 nonce 在有效窗口內重複使用 | 每次請求產生新的 UUID |

---

## 3. 缺少 SmartlyCommand 欄位

### 症狀

HTTP 400，`errors[].code` 為 `missing_required_fields`。

### 正確格式

```json
{
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
}
```

### 常見原因

- 使用了舊的 source service-call body。
- `device_id` 不是 Sync API 回傳的邏輯設備 ID。
- `capability` 或 `command` 與設備支援的 contract 不一致。

---

## 4. Capability 或 Command 不支援

### 症狀

HTTP 400 或 422，`errors[].code` 為 `invalid_command`、`command_not_supported` 或 `command_failed`。

### 解法

1. 先呼叫 sync/state API 取得該邏輯設備的 capabilities。
2. 確認 `capability` 是 canonical capability 名稱。
3. 確認 `command` 是該 capability 支援的 command。
4. 確認 `params` 欄位符合 capability schema。

---

## 5. Params 驗證失敗

### 症狀

HTTP 400，`errors[].code` 為 `invalid_params`。

### 範例

```json
{
  "command_id": "cmd_bad_brightness",
  "device_id": "ldev_bedroom_light",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "value": 180
  }
}
```

上例錯誤原因是 `brightness.value` 應為 0 到 100 的百分比。

```json
{
  "command_id": "cmd_good_brightness",
  "device_id": "ldev_bedroom_light",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "value": 78
  }
}
```

---

## 6. 權限不足

| 錯誤碼 | 說明 |
|--------|------|
| `entity_not_allowed` | resolved source 未授權給該 client |
| `service_not_allowed` | resolved source service 不在允許清單中 |
| `acl_denied` | ACL 規則拒絕操作 |
| `insufficient_permissions` | `source.role` 權限不足 |

確認 Home Assistant entity 已標記 `smartly` label，並確認 client ACL 規則允許該邏輯設備與 capability。

---

## 7. Runtime Adapter 不可用

### 症狀

HTTP 503，`errors[].code` 為 `smartly_command_executor_unavailable`。

### 解法

1. 確認 integration 已完成 setup。
2. 重新載入 Smartly Bridge integration。
3. 檢查 Home Assistant log 是否有 runtime adapter 建立失敗。

---

## 8. 速率限制

### 症狀

HTTP 429，`errors[].code` 為 `rate_limited`。

### 解法

- 讀取 `Retry-After` header 或 `data.retry_after`。
- 降低 client 端重試頻率。
- 必要時調整設定：

```yaml
smartly_bridge:
  rate_limit:
    requests_per_minute: 120
```

---

## 簽名計算測試工具

```python
#!/usr/bin/env python3
"""Signature calculation helper for API vNext SmartlyCommand."""

import hashlib
import hmac
import json

client_secret = "your_secret_key"
method = "POST"
path = "/api/smartly/control"
timestamp = "1735228800"
nonce = "550e8400-e29b-41d4-a716-446655440000"

body = {
    "command_id": "cmd_20260627_0001",
    "device_id": "ldev_bedroom_light",
    "capability": "brightness",
    "command": "set_brightness",
    "params": {"value": 78},
    "source": {"user_id": "u_123", "role": "tenant"},
}

body_json = json.dumps(body, separators=(",", ":"))
body_hash = hashlib.sha256(body_json.encode()).hexdigest()
payload = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
signature = hmac.new(
    client_secret.encode(),
    payload.encode(),
    hashlib.sha256,
).hexdigest()

print(f"Body JSON: {body_json}")
print(f"Body Hash: {body_hash}")
print(f"Payload:\n{payload}")
print(f"Signature: {signature}")
```

---

## 取得協助

提交問題時請包含：

- Home Assistant 版本
- Smartly Bridge 版本
- 完整錯誤 envelope，請移除敏感資訊
- 相關日誌片段
- 最小化重現步驟

---

## 📚 相關文檔

- **[API 基礎與認證](./api-basics.md)** - 端點資訊與簽名計算
- **[回應格式](./responses.md)** - 成功與錯誤回應說明
- **[安全指南](./security.md)** - 安全最佳實踐

---

**返回**：[控制 API 指南](./README.md)
