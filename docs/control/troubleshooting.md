# 故障排除

> **返回**：[控制 API 指南](./README.md)

本文檔提供常見問題的解決方案與除錯步驟。

---

## 目錄

1. [簽名驗證失敗](#1-簽名驗證失敗invalid_signature)
2. [實體不允許控制](#2-實體不允許控制entity_not_allowed)
3. [服務不允許](#3-服務不允許service_not_allowed)
4. [時間戳錯誤](#4-時間戳錯誤invalid_timestamp)
5. [Nonce 重複使用](#5-nonce-重複使用nonce_reused)
6. [速率限制](#6-速率限制rate_limited)
7. [除錯工具](#除錯工具)
8. [取得協助](#取得協助)

---

## 1. 簽名驗證失敗（`invalid_signature`）

### 症狀

收到 401 錯誤，錯誤訊息為 `invalid_signature`

### 可能原因與解決方案

| 原因 | 解決方案 | 驗證方法 |
|------|---------|---------|
| `client_secret` 錯誤 | 確認密鑰與伺服器配置一致 | 檢查 `secrets.yaml` 中的配置 |
| Body JSON 格式不一致 | 確保 JSON 不含多餘空格/換行 | 使用 `json.dumps(separators=(',', ':'))` |
| 簽名計算錯誤 | 檢查 Payload 組合順序 | 參考範例程式碼 |
| 編碼問題 | 使用 UTF-8 編碼 | `str.encode('utf-8')` |
| 大小寫錯誤 | 簽名必須是小寫十六進位 | `.hexdigest()` 或 `.toLowerCase()` |

### 除錯步驟

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
```

### 啟用伺服器端 debug 日誌

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.smartly_bridge.auth: debug
```

---

## 2. 實體不允許控制（`entity_not_allowed`）

### 症狀

收到 403 錯誤，錯誤訊息為 `entity_not_allowed`

### 解決方案

#### 步驟 1：檢查實體是否存在

在 Home Assistant 開發者工具 → 狀態 中搜尋實體 ID

#### 步驟 2：確認實體已添加 `smartly` 標籤

**方法 1：介面操作**
1. 設定 → 實體
2. 選擇實體
3. 標籤 → 新增 `smartly`

**方法 2：檢查 entity registry**
```bash
cat .storage/core.entity_registry | grep "smartly"
```

#### 步驟 3：重新載入整合

設定 → 裝置與服務 → Smartly Bridge → 重新載入

---

## 3. 服務不允許（`service_not_allowed`）

### 症狀

收到 403 錯誤，錯誤訊息為 `service_not_allowed`

### 解決方案

#### 確認動作名稱正確

| ✅ 正確 | ❌ 錯誤 |
|--------|--------|
| `turn_on`（小寫，底線分隔） | `turnOn`（駝峰式） |
| `set_temperature` | `TURN_ON`（大寫） |
| `open_cover` | `setTemperature` |

#### 檢查允許的服務清單

```python
# custom_components/smartly_bridge/const.py
ALLOWED_SERVICES = {
    "switch": ["turn_on", "turn_off", "toggle"],
    "light": ["turn_on", "turn_off", "toggle"],
    "cover": ["open_cover", "close_cover", "stop_cover", "set_cover_position"],
    "climate": ["set_temperature", "set_hvac_mode", "set_fan_mode"],
    "fan": ["turn_on", "turn_off", "set_percentage", "set_preset_mode"],
    "lock": ["lock", "unlock"],
    "scene": ["turn_on"],
    "script": ["turn_on", "turn_off"],
    "automation": ["trigger", "turn_on", "turn_off"],
}
```

#### 檢查設備支援的功能

開發者工具 → 服務 → 選擇設備 → 查看可用服務

---

## 4. 時間戳錯誤（`invalid_timestamp`）

### 症狀

收到 401 錯誤，錯誤訊息為 `invalid_timestamp`

### 原因

客戶端時間與伺服器時間差異超過 30 秒

### 解決方案

#### 同步系統時間

```bash
# Linux/macOS
sudo ntpdate pool.ntp.org

# 或使用 systemd-timesyncd
sudo timedatectl set-ntp true

# Windows
w32tm /resync
```

#### 檢查時區設定

```python
import time
print(f"當前 Unix 時間戳: {int(time.time())}")
```

#### 比對伺服器時間

```bash
curl -I http://homeassistant.local:8123
# 檢查 Date 標頭
```

---

## 5. Nonce 重複使用（`nonce_reused`）

### 症狀

收到 401 錯誤，錯誤訊息為 `nonce_reused`

### 原因

同一個 Nonce 在 5 分鐘內被使用多次

### 解決方案

#### 確保每次請求生成新的 UUID

```python
import uuid

# ✅ 正確：每次請求生成新的 nonce
nonce = str(uuid.uuid4())

# ❌ 錯誤：重複使用固定值
nonce = "fixed-nonce-12345"
```

#### 檢查重試邏輯

```python
def retry_request():
    # 重試時必須生成新的 nonce 和 timestamp
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())  # 新的 nonce
    # ...
```

---

## 6. 速率限制（`rate_limited`）

### 症狀

收到 429 錯誤，錯誤訊息為 `rate_limited`

### 解決方案

#### 實作重試機制

```python
import time

response = requests.post(url, headers=headers, json=body)
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    time.sleep(retry_after)
    response = requests.post(url, headers=headers, json=body)
```

#### 調整速率限制配置

```yaml
# configuration.yaml
smartly_bridge:
  rate_limit:
    requests_per_minute: 120  # 預設 60
```

---

## 7. 服務調用失敗（`service_call_failed`）

### 症狀

收到 500 錯誤，錯誤訊息為 `service_call_failed`，日誌顯示類似：
```
Service call failed: ServiceRegistry.async_call() got an unexpected keyword argument 'limit'
```

### 原因

`service_data` 中包含了 Home Assistant 服務不支援的參數

### 解決方案

#### 檢查請求的 service_data

確保只傳遞設備服務支援的參數：

```json
// ❌ 錯誤：包含無效參數
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 200,
    "limit": 10  // 錯誤：light.turn_on 不支援 limit 參數
  }
}

// ✅ 正確：只包含支援的參數
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 200
  }
}
```

#### 查詢服務支援的參數

在 Home Assistant 介面：
1. 開發者工具 → 服務
2. 選擇對應的服務（例如 `light.turn_on`）
3. 查看「服務資料」區塊，了解支援的參數

#### 常見無效參數

| 參數 | 說明 |
|------|------|
| `limit` | 不是服務參數，可能誤傳 |
| `return_response` | 某些版本的 Home Assistant 不支援 |
| `context` | 不應在 service_data 中傳遞 |

---

## 除錯工具

### 簽名計算測試工具

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

### 連線測試

```bash
# 測試 Home Assistant 是否可連線
curl -v http://homeassistant.local:8123/api/

# 檢查 Smartly Bridge 端點
curl -v http://homeassistant.local:8123/api/smartly/control
```

---

## 取得協助

如果問題仍未解決：

### 1. 檢查 GitHub Issues

查看是否有類似問題：[專案 Issues 頁面](https://github.com/your-repo/smartly-bridge/issues)

### 2. 提交問題時請包含

- Home Assistant 版本
- Smartly Bridge 版本
- 完整錯誤訊息（隱藏敏感資訊）
- 相關日誌片段
- 最小化重現步驟

### 3. 問題範本

```markdown
## 問題描述
簡短描述問題

## 環境資訊
- Home Assistant 版本：2024.12.x
- Smartly Bridge 版本：1.0.0
- Python 版本：3.11
- 作業系統：Ubuntu 22.04

## 重現步驟
1. ...
2. ...
3. ...

## 預期行為
描述預期的結果

## 實際行為
描述實際發生的結果

## 錯誤訊息
```json
{
  "error": "...",
  "message": "..."
}
```

## 日誌片段
```
相關日誌（移除敏感資訊）
```
```

---

## 📚 相關文檔

- **[API 基礎與認證](./api-basics.md)** - 端點資訊與簽名計算
- **[回應格式](./responses.md)** - 成功與錯誤回應說明
- **[安全指南](./security.md)** - 安全最佳實踐

---

**返回**：[控制 API 指南](./README.md)
