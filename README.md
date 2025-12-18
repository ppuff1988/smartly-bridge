# Smartly Bridge - Home Assistant Custom Integration

> **多社區 Home Assistant × 中央管理 Platform 架構的安全橋接器**

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fyourusername%2Fsmartifly_bridge)

Smartly Bridge 是一個 Home Assistant Custom Integration，用於連接社區級 Home Assistant 與中央管理平台（Smartly Platform）。設計原則：**Platform 永遠不持有 HA Token、HA 為社區安全邊界、Platform 為業務 RBAC 中樞**。

---

## 📋 目錄

- [系統架構](#系統架構)
- [功能特色](#功能特色)
- [安裝方式](#安裝方式)
- [設定流程](#設定流程)
- [API 規格](#api-規格)
- [安全機制](#安全機制)
- [開發指南](#開發指南)
- [測試](#測試)
- [檔案結構](#檔案結構)

---

## 系統架構

```
┌─────────────────┐
│   User / App    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Smartly Platform │  ← 使用者系統 / RBAC / Audit / 業務邏輯
│  - User Auth       │
│  - Role Management │
│  - Community Model │
└────────┬────────┘
         │ Signed Request (HMAC-SHA256)
         ▼
┌─────────────────┐
│  HA Integration   │  ← 社區邊界控制器 / 裝置白名單防線
│  (Smartly Bridge) │
│  - Auth Verify    │
│  - Entity Guard   │
│  - Service Guard  │
└────────┬────────┘
         │ hass.services.async_call()
         ▼
┌─────────────────┐
│  Home Assistant   │  ← 實際裝置控制
│  - Devices        │
│  - Entities       │
│  - Automations    │
└─────────────────┘
```

### 職責分離

| 層級 | 職責 |
|------|------|
| **Platform** | 決定「誰可以做什麼」- 使用者認證、RBAC、業務授權 |
| **Smartly Bridge** | 決定「平台最多能做什麼」- Entity 白名單、Service 白名單 |
| **Home Assistant** | 執行裝置操作 |

---

## 功能特色

### 🔐 安全機制
- **HMAC-SHA256 簽名認證** - 雙向驗證，無需 HA Long-Lived Token
- **Nonce 防重放攻擊** - 5 分鐘 TTL 記憶體快取
- **Timestamp 驗證** - ±30 秒容差
- **IP 白名單** - CIDR 格式（可選）
- **Rate Limiting** - 60 requests/minute sliding window

### 📡 API 端點
- `POST /api/smartly/control` - 裝置控制
- `GET /api/smartly/sync/structure` - 結構同步（Floors/Areas/Devices/Entities）

### 📤 狀態推送
- 主動推送狀態變化至 Platform Webhook
- 500ms 批次彙整
- 指數退避重試（最多 3 次）

### 🏷️ 存取控制
- Entity 需標記 `smartly_control` label 才可控制
- Service 白名單（switch/light/cover/climate/fan/lock/scene/script/automation）
- Area 過濾支援

---

## 安裝方式

### 手動安裝

1. 複製 `custom_components/smartly_bridge/` 至 Home Assistant 的 `custom_components/` 目錄
2. 重新啟動 Home Assistant
3. 前往 **設定 → 裝置與服務 → 新增整合**
4. 搜尋 **Smartly Bridge**

### HACS 安裝（未來支援）

```yaml
# 透過 HACS 自訂儲存庫
Repository: https://github.com/ppuff1988/smartly-bridge
Category: Integration
```

---

## 設定流程

### Step 1: 新增整合

在 HA UI 中新增 Smartly Bridge 整合，填寫：

| 欄位 | 說明 | 範例 |
|------|------|------|
| **Instance ID** | HA 實例識別碼 | `community_001` |
| **Platform Webhook URL** | Platform 接收狀態推送的端點 | `https://platform.example.com/webhooks/ha-events` |
| **Allowed IP Ranges** | CIDR 格式 IP 白名單（可選） | `10.0.0.0/8,192.168.0.0/16` |
| **Push Batch Interval** | 批次推送間隔（秒） | `0.5` |

### Step 2: 取得憑證

整合設定完成後，系統自動產生：
- **Client ID**: `ha_xxxxxxxxxxxx`
- **Client Secret**: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

請將這組憑證安全提供給 Platform 端儲存。

### Step 3: 標記可控 Entity

在 HA 中為需要開放給 Platform 控制的 Entity 添加 Label：

```
smartly_control
```

只有帶有此 Label 的 Entity 才會被 Smartly Bridge 授權控制。

---

## API 規格

### Control API

**Endpoint:** `POST /api/smartly/control`

**Request Headers:**
```http
X-Client-Id: ha_xxxxxxxxxxxx
X-Timestamp: 1702800000
X-Nonce: 550e8400-e29b-41d4-a716-446655440000
X-Signature: <HMAC-SHA256 signature>
```

**Request Body:**
```json
{
  "entity_id": "switch.room_101_light",
  "action": "turn_on",
  "service_data": {
    "brightness": 255
  },
  "actor": {
    "user_id": "u_123",
    "role": "room_admin"
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "entity_id": "switch.room_101_light",
  "action": "turn_on"
}
```

**Error Responses:**

| Status | Error | 說明 |
|--------|-------|------|
| 401 | `missing_headers` | 缺少認證 headers |
| 401 | `invalid_timestamp` | Timestamp 超出容差 |
| 401 | `nonce_reused` | Nonce 重複使用（重放攻擊） |
| 401 | `invalid_signature` | 簽名驗證失敗 |
| 401 | `ip_not_allowed` | IP 不在白名單 |
| 403 | `entity_not_allowed` | Entity 未標記 `smartly_control` |
| 403 | `service_not_allowed` | Service 不在白名單 |
| 429 | `rate_limited` | 超過速率限制 |

---

### Sync API

**Endpoint:** `GET /api/smartly/sync/structure`

**Request Headers:** 同 Control API

**Response (200 OK):**
```json
{
  "floors": [
    {
      "id": "floor_1",
      "name": "1F",
      "areas": [
        {
          "id": "area_101",
          "name": "Room 101",
          "devices": [
            {
              "id": "device_abc123",
              "name": "Smart Switch",
              "entities": [
                {
                  "entity_id": "switch.room_101_light",
                  "domain": "switch",
                  "name": "Light"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

> **注意**：Sync API 僅回傳結構 metadata，不含 state。狀態透過 Push 機制取得。

---

### Platform Webhook（Platform 端需實作）

**Endpoint:** `POST {webhook_url}/events`

**Request Headers（HA 推送時附帶）:**
```http
X-HA-Instance-Id: community_001
X-Timestamp: 1702800000
X-Nonce: 550e8400-e29b-41d4-a716-446655440000
X-Signature: <HMAC-SHA256 signature>
Content-Type: application/json
```

**Request Body:**
```json
{
  "events": [
    {
      "entity_id": "switch.room_101_light",
      "old_state": {
        "state": "off",
        "attributes": {},
        "last_changed": "2025-12-17T09:00:00+00:00",
        "last_updated": "2025-12-17T09:00:00+00:00"
      },
      "new_state": {
        "state": "on",
        "attributes": {"brightness": 255},
        "last_changed": "2025-12-17T10:30:00+00:00",
        "last_updated": "2025-12-17T10:30:00+00:00"
      },
      "timestamp": "2025-12-17T10:30:00.000Z"
    }
  ]
}
```

**Expected Response:**

| Status | 說明 |
|--------|------|
| 200 OK | 接收成功 |
| 401 Unauthorized | 簽名驗證失敗 |
| 429 Too Many Requests | 限流（HA 將 backoff） |

---

## 安全機制

### HMAC 簽名計算

**簽名內容（Signature Payload）:**
```
METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + SHA256(BODY)
```

**簽名計算:**
```python
import hmac
import hashlib

def compute_signature(secret, method, path, timestamp, nonce, body):
    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    return hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
```

### 驗證流程

1. **檢查 IP** - 若設定 CIDR 白名單，驗證來源 IP
2. **檢查 Headers** - 確認 X-Client-Id、X-Timestamp、X-Nonce、X-Signature 皆存在
3. **驗證 Timestamp** - ±30 秒內有效
4. **驗證 Nonce** - 未曾使用過（5 分鐘內）
5. **驗證簽名** - HMAC-SHA256 constant-time 比對
6. **檢查 Rate Limit** - 60 requests/minute
7. **驗證 Entity** - 需有 `smartly_control` label
8. **驗證 Service** - 需在 ALLOWED_SERVICES 白名單

### 允許的 Services

```python
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

---

## 開發指南

### 環境設定

```bash
# 安裝開發依賴
pip install -r requirements-dev.txt

# 執行測試
python -m pytest tests/ -v

# 執行測試（含覆蓋率）
python -m pytest tests/ --cov=custom_components.smartly_bridge --cov-report=html
```

### 使用 Dev Container

本專案支援 VS Code Dev Container，包含：
- Home Assistant 官方映像
- Python 開發工具（pytest、black、isort）
- HA 設定自動掛載

```bash
# 在 VS Code 中開啟專案
# 選擇 "Reopen in Container"
```

---

## 測試

### 測試結構

```
tests/
├── __init__.py           # 測試套件初始化
├── conftest.py           # 共用 fixtures
├── test_acl.py           # ACL 模組測試 (20 tests)
├── test_audit.py         # Audit 模組測試 (10 tests)
├── test_auth.py          # Auth 模組測試 (26 tests)
├── test_config_flow.py   # Config Flow 測試 (13 tests)
├── test_http.py          # HTTP API 測試 (7 tests)
├── test_init.py          # Integration 初始化測試 (7 tests)
└── test_push.py          # Push 模組測試 (8 tests)
```

### 測試覆蓋

| 模組 | 測試數量 | 覆蓋內容 |
|------|----------|----------|
| `auth.py` | 26 | HMAC 簽名、timestamp、IP CIDR、NonceCache、RateLimiter |
| `acl.py` | 20 | Entity/Service/Area 白名單 |
| `config_flow.py` | 13 | 憑證產生、驗證、表單、儲存 |
| `audit.py` | 10 | 各種 log 函數 |
| `http.py` | 7 | API 端點認證、Rate limiting |
| `__init__.py` | 7 | 生命週期管理 |
| `push.py` | 8 | 狀態推送、重試邏輯 |

### 執行測試

```bash
# 執行所有測試
python -m pytest tests/ -v

# 執行特定模組
python -m pytest tests/test_auth.py -v

# 僅執行失敗的測試
python -m pytest tests/ --lf
```

---

## 檔案結構

```
custom_components/smartly_bridge/
├── __init__.py           # Integration 入口、生命週期管理
├── manifest.json         # 套件描述 (domain, version, dependencies)
├── const.py              # 常數定義 (DOMAIN, ALLOWED_SERVICES, RATE_LIMIT)
├── config_flow.py        # UI 設定流程、憑證產生
├── auth.py               # HMAC 驗證/簽名、NonceCache、RateLimiter、IP 檢查
├── acl.py                # Entity/Service 白名單、結構同步
├── http.py               # HTTP API 端點 (Control, Sync)
├── push.py               # 狀態變化推送到 Platform
├── audit.py              # 操作紀錄 logging
├── strings.json          # UI 文字（英文）
└── translations/
    ├── en.json           # 英文翻譯
    └── zh-Hant.json      # 繁體中文翻譯
```

---

## 設計決策

### 為什麼不使用 HA Long-Lived Token？

| 方案 | 問題 |
|------|------|
| Platform 持有 HA Token | ❌ Token 洩漏 = 完全控制權、無法細粒度授權、難以 revoke |
| 使用 HMAC 簽名 | ✅ 雙向驗證、可隨時 revoke、支援 RBAC |

### 為什麼選擇主動推送而非 WebSocket Proxy？

| 方案 | 評估 |
|------|------|
| Platform 直連 HA WebSocket | ❌ 需要 Token，違反安全原則 |
| Integration 提供 WS Proxy | ⚠️ 實作複雜，需維護長連線 |
| **Integration 主動推送** | ✅ 符合安全原則、可擴展性最佳、實作簡單 |

### 為什麼 Rate Limit 設為 60 req/min？

- 一般智慧家庭控制場景足夠
- 防止 DoS 攻擊
- 可在 `const.py` 調整

---

## Phase 2 規劃

- [ ] Key Rotation API (`POST /api/smartly/rotate-key`)
- [ ] WebSocket Proxy（關鍵實體即時推送）
- [ ] Entity 動態白名單 API
- [ ] 更多 Domain 支援（media_player、vacuum 等）
- [ ] 多 Config Entry 支援（單 HA 對接多 Platform）

---

## License

MIT License

---

## 作者

- [@ppuff1988](https://github.com/ppuff1988)

---

> **一句話總結**：Platform 決定「誰可以做什麼」，Smartly Bridge 決定「平台最多能做什麼」。
