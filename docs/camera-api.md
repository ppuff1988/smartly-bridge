# Camera API 說明文件

## 目錄

- [概述](#概述)
- [認證方式](#認證方式)
- [API 端點](#api-端點)
  - [1. 取得攝影機快照](#1-取得攝影機快照)
  - [2. 即時串流 (MJPEG)](#2-即時串流-mjpeg)
  - [3. 取得攝影機清單](#3-取得攝影機清單)
  - [4. 攝影機設定管理](#4-攝影機設定管理)
  - [5. HLS 串流管理](#5-hls-串流管理)
- [錯誤碼](#錯誤碼)
- [快取機制](#快取機制)
- [使用範例](#使用範例)

---

## 概述

Smartly Bridge Camera API 提供完整的 IP 攝影機管理功能，包含：

- **快照擷取**：靜態影像擷取，支援 ETag 快取機制
- **MJPEG 串流**：即時影像串流，適合低延遲需求
- **HLS 串流**：自適應碼率串流，適合行動裝置與網頁播放
- **攝影機管理**：註冊、移除攝影機及快取管理

所有 API 端點皆需 HMAC 簽章認證，並支援速率限制與 IP 白名單控制。

---

## 認證方式

所有 Camera API 端點皆需包含以下 HTTP 標頭：

```http
X-Client-Id: your-client-id
X-Timestamp: 1735228800
X-Nonce: unique-random-string
X-Signature: hmac-sha256-signature
```

**簽章演算法：**
```
signature = HMAC-SHA256(client_secret, 
    "GET\n" +
    "/api/smartly/camera/{entity_id}/snapshot\n" +
    timestamp + "\n" +
    nonce + "\n" +
    ""
)
```

詳細認證說明請參考 [control/security.md](control/security.md)

---

## API 端點

### 1. 取得攝影機快照

擷取攝影機靜態影像，支援條件式請求（ETag）與快取機制。

#### 端點

```
GET /api/smartly/camera/{entity_id}/snapshot
```

#### 路徑參數

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `entity_id` | string | 是 | 攝影機實體 ID，格式：`camera.*` |

#### Query 參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `refresh` | boolean | false | 是否強制重新擷取，略過快取 |

#### Request Headers

```http
GET /api/smartly/camera/camera.front_door/snapshot?refresh=false HTTP/1.1
Host: homeassistant.local:8123
X-Client-Id: mobile-app-001
X-Timestamp: 1735228800
X-Nonce: abc123def456
X-Signature: a3f8b2c1d4e5f6...
If-None-Match: "etag-value-from-previous-response"
```

#### Response (成功 - 200 OK)

```http
HTTP/1.1 200 OK
Content-Type: image/jpeg
Content-Length: 245678
ETag: "a3f8b2c1d4e5f6..."
Cache-Control: private, max-age=10
X-Snapshot-Timestamp: 1735228800.123

[Binary Image Data]
```

#### Response Headers 說明

| Header | 說明 |
|--------|------|
| `Content-Type` | 影像格式，通常為 `image/jpeg` |
| `ETag` | 影像快取標籤，用於條件式請求 |
| `Cache-Control` | 快取策略，預設為 10 秒 |
| `X-Snapshot-Timestamp` | 快照時間戳（Unix 時間） |

#### Response (未修改 - 304 Not Modified)

當 `If-None-Match` 標頭與 ETag 相符時：

```http
HTTP/1.1 304 Not Modified
ETag: "a3f8b2c1d4e5f6..."
```

#### Error Response

```json
{
  "error": "invalid_entity_id"
}
```

**可能的錯誤碼：**

| HTTP Status | Error Code | 說明 |
|-------------|------------|------|
| 400 | `invalid_entity_id` | entity_id 格式錯誤或不存在 |
| 401 | `invalid_signature` | HMAC 簽章驗證失敗 |
| 403 | `entity_not_allowed` | 攝影機未被授權存取 |
| 404 | `snapshot_unavailable` | 快照無法取得 |
| 429 | `rate_limited` | 超過速率限制 |
| 500 | `integration_not_configured` | 整合尚未設定 |

---

### 2. 即時串流 (MJPEG)

提供即時 MJPEG 影像串流，適合低延遲即時監控需求。

#### 端點

```
GET /api/smartly/camera/{entity_id}/stream
```

#### 路徑參數

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `entity_id` | string | 是 | 攝影機實體 ID，格式：`camera.*` |

#### Request

```http
GET /api/smartly/camera/camera.front_door/stream HTTP/1.1
Host: homeassistant.local:8123
X-Client-Id: mobile-app-001
X-Timestamp: 1735228800
X-Nonce: abc123def456
X-Signature: a3f8b2c1d4e5f6...
```

#### Response (成功 - 200 OK)

```http
HTTP/1.1 200 OK
Content-Type: multipart/x-mixed-replace;boundary=frame

--frame
Content-Type: image/jpeg
Content-Length: 12345

[Binary Image Frame 1]
--frame
Content-Type: image/jpeg
Content-Length: 12678

[Binary Image Frame 2]
--frame
...
```

#### Response 說明

- **Content-Type**: `multipart/x-mixed-replace` 用於持續推送影像幀
- **Boundary**: 每個影像幀以 `--frame` 分隔
- 連線會保持開啟直到客戶端斷線或串流停止

#### Error Response

```json
{
  "error": "invalid_entity_id"
}
```

**可能的錯誤碼：** 與快照 API 相同

---

### 3. 取得攝影機清單

取得所有已授權的攝影機清單，包含狀態與串流能力。

#### 端點

```
GET /api/smartly/camera/list
```

#### Query 參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `capabilities` | boolean | false | 是否包含詳細串流能力資訊 |

#### Request

```http
GET /api/smartly/camera/list?capabilities=true HTTP/1.1
Host: homeassistant.local:8123
X-Client-Id: mobile-app-001
X-Timestamp: 1735228800
X-Nonce: abc123def456
X-Signature: a3f8b2c1d4e5f6...
```

#### Response (成功 - 200 OK)

```json
{
  "cameras": [
    {
      "entity_id": "camera.front_door",
      "name": "前門攝影機",
      "state": "idle",
      "is_streaming": false,
      "brand": "Hikvision",
      "model": "DS-2CD2085G1",
      "supported_features": 3,
      "capabilities": {
        "snapshot": true,
        "mjpeg": true,
        "hls": true,
        "webrtc": false
      },
      "endpoints": {
        "snapshot": "/api/smartly/camera/camera.front_door/snapshot",
        "mjpeg": "/api/smartly/camera/camera.front_door/stream",
        "hls": "/api/smartly/camera/camera.front_door/stream/hls"
      }
    },
    {
      "entity_id": "camera.backyard",
      "name": "後院攝影機",
      "state": "streaming",
      "is_streaming": true,
      "brand": "Dahua",
      "model": "IPC-HFW5831E-Z5E",
      "supported_features": 3,
      "capabilities": {
        "snapshot": true,
        "mjpeg": true,
        "hls": true,
        "webrtc": false
      },
      "endpoints": {
        "snapshot": "/api/smartly/camera/camera.backyard/snapshot",
        "mjpeg": "/api/smartly/camera/camera.backyard/stream",
        "hls": "/api/smartly/camera/camera.backyard/stream/hls"
      }
    }
  ],
  "count": 2,
  "cache_stats": {
    "total_snapshots": 15,
    "total_size_bytes": 3145728,
    "hit_rate": 0.85
  },
  "hls_stats": {
    "active_streams": 1,
    "total_sessions": 5
  }
}
```

#### Response 欄位說明

**cameras 陣列元素：**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `entity_id` | string | 攝影機實體 ID |
| `name` | string | 攝影機名稱 |
| `state` | string | 目前狀態：`idle`, `streaming`, `recording`, `unavailable` |
| `is_streaming` | boolean | 是否正在串流 |
| `brand` | string | 攝影機品牌 |
| `model` | string | 攝影機型號 |
| `supported_features` | number | Home Assistant 支援的功能位元遮罩 |
| `capabilities` | object | 串流能力（僅當 `?capabilities=true`） |
| `endpoints` | object | API 端點 URL（僅當 `?capabilities=true`） |

**cache_stats 物件：**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `total_snapshots` | number | 快取中的快照數量 |
| `total_size_bytes` | number | 快取總大小（位元組） |
| `hit_rate` | number | 快取命中率（0.0 - 1.0） |

**hls_stats 物件：**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `active_streams` | number | 活躍的 HLS 串流數量 |
| `total_sessions` | number | 總 HLS 工作階段數 |

#### Error Response

```json
{
  "error": "invalid_signature"
}
```

---

### 4. 攝影機設定管理

管理攝影機設定，包含註冊、移除及快取清理。

#### 端點

```
POST /api/smartly/camera/config
```

#### Request (註冊攝影機)

```http
POST /api/smartly/camera/config HTTP/1.1
Host: homeassistant.local:8123
Content-Type: application/json
X-Client-Id: mobile-app-001
X-Timestamp: 1735228800
X-Nonce: abc123def456
X-Signature: a3f8b2c1d4e5f6...

{
  "action": "register",
  "entity_id": "camera.front_door",
  "name": "前門攝影機",
  "snapshot_url": "rtsp://192.168.1.100:554/snapshot",
  "stream_url": "rtsp://192.168.1.100:554/stream",
  "username": "admin",
  "password": "password123",
  "verify_ssl": true,
  "extra_headers": {
    "User-Agent": "Smartly-Bridge/1.0"
  }
}
```

#### Request 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `action` | string | 是 | 動作：`register`, `unregister`, `clear_cache`, `list` |
| `entity_id` | string | 視動作而定 | 攝影機實體 ID |
| `name` | string | 否 | 攝影機名稱 |
| `snapshot_url` | string | 否 | 快照 URL（支援 HTTP/RTSP） |
| `stream_url` | string | 否 | 串流 URL（支援 RTSP） |
| `username` | string | 否 | 驗證使用者名稱 |
| `password` | string | 否 | 驗證密碼 |
| `verify_ssl` | boolean | 否 | 是否驗證 SSL 憑證（預設：true） |
| `extra_headers` | object | 否 | 額外 HTTP 標頭 |

#### Response (註冊成功 - 200 OK)

```json
{
  "success": true,
  "action": "registered",
  "entity_id": "camera.front_door"
}
```

#### Request (移除攝影機)

```json
{
  "action": "unregister",
  "entity_id": "camera.front_door"
}
```

#### Response (移除成功 - 200 OK)

```json
{
  "success": true,
  "action": "unregistered",
  "entity_id": "camera.front_door"
}
```

#### Request (清除快取)

```json
{
  "action": "clear_cache",
  "entity_id": "camera.front_door"
}
```

若 `entity_id` 為 `null` 或未提供，則清除所有快取。

#### Response (清除成功 - 200 OK)

```json
{
  "success": true,
  "action": "cache_cleared",
  "cleared_count": 5
}
```

#### Request (列出已註冊攝影機)

```json
{
  "action": "list"
}
```

#### Response (列出成功 - 200 OK)

```json
{
  "cameras": [
    {
      "entity_id": "camera.front_door",
      "name": "前門攝影機",
      "has_snapshot_url": true,
      "has_stream_url": true,
      "has_credentials": true
    }
  ],
  "count": 1
}
```

#### Error Response

```json
{
  "error": "missing_action"
}
```

**可能的錯誤碼：**

| HTTP Status | Error Code | 說明 |
|-------------|------------|------|
| 400 | `missing_action` | 缺少 action 參數 |
| 400 | `missing_entity_id` | 缺少 entity_id 參數 |
| 400 | `unknown_action` | 未知的 action 值 |
| 400 | `invalid_json` | JSON 格式錯誤 |

---

### 5. HLS 串流管理

管理 HLS（HTTP Live Streaming）串流，支援自適應碼率與低延遲播放。

#### 端點

```
GET /api/smartly/camera/{entity_id}/stream/hls
```

#### 路徑參數

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `entity_id` | string | 是 | 攝影機實體 ID，格式：`camera.*` |

#### Query 參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `action` | string | `start` | 動作：`start`, `stop`, `info`, `stats` |

---

#### 5.1 啟動 HLS 串流

#### Request

```http
GET /api/smartly/camera/camera.front_door/stream/hls?action=start HTTP/1.1
Host: homeassistant.local:8123
X-Client-Id: mobile-app-001
X-Timestamp: 1735228800
X-Nonce: abc123def456
X-Signature: a3f8b2c1d4e5f6...
```

#### Response (成功 - 200 OK)

```json
{
  "entity_id": "camera.front_door",
  "hls_url": "/api/smartly/camera/camera.front_door/stream/hls/master.m3u8",
  "master_playlist": "/api/smartly/camera/camera.front_door/stream/hls/master.m3u8",
  "playlist": "/api/smartly/camera/camera.front_door/stream/hls/playlist.m3u8",
  "init_segment": "/api/smartly/camera/camera.front_door/stream/hls/init.mp4",
  "is_streaming": true,
  "stream_id": "hls_1735228800_abc123",
  "started_at": 1735228800.123,
  "format": "fmp4",
  "supported_features": {
    "low_latency": true,
    "partial_segments": true,
    "preload_hints": false
  }
}
```

#### Response 欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `entity_id` | string | 攝影機實體 ID |
| `hls_url` | string | Master Playlist URL（主要入口點） |
| `master_playlist` | string | Master Playlist URL |
| `playlist` | string | Media Playlist URL |
| `init_segment` | string | 初始化片段 URL（fMP4 格式） |
| `is_streaming` | boolean | 是否正在串流 |
| `stream_id` | string | 串流工作階段 ID |
| `started_at` | number | 串流開始時間（Unix 時間戳） |
| `format` | string | 串流格式：`fmp4` 或 `ts` |
| `supported_features` | object | 支援的 HLS 功能 |

---

#### 5.2 取得 HLS 串流資訊

不啟動串流，僅取得串流資訊與能力。

#### Request

```http
GET /api/smartly/camera/camera.front_door/stream/hls?action=info HTTP/1.1
```

#### Response (成功 - 200 OK)

```json
{
  "entity_id": "camera.front_door",
  "name": "前門攝影機",
  "capabilities": {
    "snapshot": true,
    "mjpeg": true,
    "hls": true,
    "webrtc": false
  },
  "hls_url": "/api/smartly/camera/camera.front_door/stream/hls/master.m3u8",
  "mjpeg_url": "/api/smartly/camera/camera.front_door/stream",
  "stream_source": "rtsp://192.168.1.100:554/stream",
  "is_streaming": false
}
```

---

#### 5.3 停止 HLS 串流

停止指定攝影機的 HLS 串流。

#### Request

```http
GET /api/smartly/camera/camera.front_door/stream/hls?action=stop HTTP/1.1
```

#### Response (成功 - 200 OK)

```json
{
  "success": true,
  "action": "stopped"
}
```

#### Response (串流不存在 - 404 Not Found)

```json
{
  "success": false,
  "action": "stopped"
}
```

---

#### 5.4 取得 HLS 統計資訊

取得所有 HLS 串流的統計資訊。

#### Request

```http
GET /api/smartly/camera/camera.front_door/stream/hls?action=stats HTTP/1.1
```

#### Response (成功 - 200 OK)

```json
{
  "active_streams": 2,
  "total_sessions": 15,
  "streams": [
    {
      "entity_id": "camera.front_door",
      "stream_id": "hls_1735228800_abc123",
      "started_at": 1735228800.123,
      "duration": 125.5,
      "segments_created": 25,
      "bytes_sent": 5242880,
      "clients_connected": 1
    },
    {
      "entity_id": "camera.backyard",
      "stream_id": "hls_1735229000_def456",
      "started_at": 1735229000.456,
      "duration": 45.2,
      "segments_created": 9,
      "bytes_sent": 1887436,
      "clients_connected": 2
    }
  ]
}
```

---

#### Error Response

```json
{
  "error": "hls_not_supported"
}
```

**可能的錯誤碼：**

| HTTP Status | Error Code | 說明 |
|-------------|------------|------|
| 400 | `invalid_entity_id` | entity_id 格式錯誤 |
| 400 | `hls_not_supported` | 攝影機不支援 HLS 串流 |
| 400 | `unknown_action` | 未知的 action 值 |
| 404 | `camera_not_found` | 找不到指定攝影機 |

---

## 錯誤碼

所有 Camera API 端點共用的錯誤回應格式：

```json
{
  "error": "error_code",
  "message": "人類可讀的錯誤訊息（可選）"
}
```

### 通用錯誤碼

| HTTP Status | Error Code | 說明 | 建議處理 |
|-------------|------------|------|----------|
| 400 | `invalid_entity_id` | entity_id 格式錯誤或不存在 | 檢查 entity_id 格式 |
| 400 | `invalid_json` | JSON 格式錯誤 | 檢查請求 body 格式 |
| 401 | `missing_auth_header` | 缺少認證標頭 | 加入 X-Client-Id, X-Signature 等 |
| 401 | `invalid_signature` | HMAC 簽章驗證失敗 | 檢查簽章計算方式 |
| 401 | `invalid_timestamp` | 時間戳不在有效範圍內 | 同步系統時間 |
| 401 | `nonce_already_used` | Nonce 已被使用過 | 產生新的隨機 nonce |
| 403 | `ip_not_allowed` | IP 不在白名單內 | 聯絡管理員將 IP 加入白名單 |
| 403 | `entity_not_allowed` | 實體未被授權存取 | 檢查 ACL 設定 |
| 404 | `snapshot_unavailable` | 無法取得快照 | 檢查攝影機狀態 |
| 404 | `camera_not_found` | 找不到指定攝影機 | 確認 entity_id 是否正確 |
| 429 | `rate_limited` | 超過速率限制 | 等待後重試，參考 Retry-After 標頭 |
| 500 | `integration_not_configured` | 整合尚未設定 | 檢查 Home Assistant 設定 |
| 500 | `camera_manager_not_initialized` | 攝影機管理器未初始化 | 重新載入整合 |

### 速率限制 Response Headers

當觸發速率限制（HTTP 429）時，回應會包含：

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Remaining: 0
Content-Type: application/json

{
  "error": "rate_limited"
}
```

---

## 快取機制

### 快照快取

Camera API 實作多層快取機制以優化效能：

#### 1. Server-Side Cache

- **預設 TTL**: 10 秒（可透過 `CAMERA_CACHE_TTL` 設定）
- **清理間隔**: 60 秒自動清理過期快照
- **快取鍵**: `entity_id` + `snapshot_timestamp`

#### 2. ETag Support

每個快照回應包含 ETag 標頭，客戶端可使用 `If-None-Match` 實現條件式請求：

```http
GET /api/smartly/camera/camera.front_door/snapshot
If-None-Match: "a3f8b2c1d4e5f6..."
```

若快照未變更，伺服器回應 `304 Not Modified`，節省頻寬。

#### 3. Cache-Control

所有快照回應包含 `Cache-Control: private, max-age=10`，建議客戶端快取 10 秒。

#### 快取統計

透過 `/api/smartly/camera/list` 取得快取統計資訊：

```json
{
  "cache_stats": {
    "total_snapshots": 15,
    "total_size_bytes": 3145728,
    "hit_rate": 0.85
  }
}
```

---

## 使用範例

### Python 範例：取得快照並儲存

```python
import hashlib
import hmac
import time
import uuid
import requests

def generate_hmac_signature(
    method: str,
    path: str,
    timestamp: int,
    nonce: str,
    body: str,
    secret: str
) -> str:
    """產生 HMAC-SHA256 簽章"""
    message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body}"
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

# 設定參數
BASE_URL = "http://homeassistant.local:8123"
CLIENT_ID = "mobile-app-001"
CLIENT_SECRET = "your-secret-key"
ENTITY_ID = "camera.front_door"

# 產生認證標頭
timestamp = int(time.time())
nonce = str(uuid.uuid4())
path = f"/api/smartly/camera/{ENTITY_ID}/snapshot"
method = "GET"

signature = generate_hmac_signature(
    method, path, timestamp, nonce, "", CLIENT_SECRET
)

headers = {
    "X-Client-Id": CLIENT_ID,
    "X-Timestamp": str(timestamp),
    "X-Nonce": nonce,
    "X-Signature": signature,
}

# 發送請求
response = requests.get(f"{BASE_URL}{path}", headers=headers)

if response.status_code == 200:
    # 儲存快照
    with open("snapshot.jpg", "wb") as f:
        f.write(response.content)
    print(f"快照已儲存，ETag: {response.headers.get('ETag')}")
    print(f"快照時間: {response.headers.get('X-Snapshot-Timestamp')}")
elif response.status_code == 304:
    print("快照未變更，使用快取版本")
else:
    print(f"錯誤: {response.json()}")
```

### JavaScript 範例：HLS 播放器

```javascript
// 使用 hls.js 播放 HLS 串流
import Hls from 'hls.js';

async function playHLSStream(entityId) {
  const baseUrl = 'http://homeassistant.local:8123';
  const clientId = 'web-app-001';
  const clientSecret = 'your-secret-key';
  
  // 產生認證標頭
  const timestamp = Math.floor(Date.now() / 1000);
  const nonce = crypto.randomUUID();
  const path = `/api/smartly/camera/${entityId}/stream/hls`;
  const method = 'GET';
  
  const signature = await generateHMACSignature(
    method, path, timestamp, nonce, '', clientSecret
  );
  
  const headers = {
    'X-Client-Id': clientId,
    'X-Timestamp': timestamp.toString(),
    'X-Nonce': nonce,
    'X-Signature': signature,
  };
  
  // 啟動 HLS 串流
  const response = await fetch(`${baseUrl}${path}?action=start`, { headers });
  const data = await response.json();
  
  if (data.hls_url) {
    const video = document.getElementById('video');
    const hlsUrl = `${baseUrl}${data.hls_url}`;
    
    if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 90,
      });
      hls.loadSource(hlsUrl);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play();
        console.log('HLS 串流已開始播放');
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari 原生支援
      video.src = hlsUrl;
      video.addEventListener('loadedmetadata', () => {
        video.play();
      });
    }
  }
}

async function generateHMACSignature(method, path, timestamp, nonce, body, secret) {
  const message = `${method}\n${path}\n${timestamp}\n${nonce}\n${body}`;
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const messageData = encoder.encode(message);
  
  const key = await crypto.subtle.importKey(
    'raw', keyData, { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign']
  );
  
  const signature = await crypto.subtle.sign('HMAC', key, messageData);
  return Array.from(new Uint8Array(signature))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

// 使用範例
playHLSStream('camera.front_door');
```

### curl 範例：取得攝影機清單

```bash
#!/bin/bash

CLIENT_ID="cli-client"
CLIENT_SECRET="your-secret-key"
BASE_URL="http://homeassistant.local:8123"
PATH="/api/smartly/camera/list"
METHOD="GET"

TIMESTAMP=$(date +%s)
NONCE=$(uuidgen)

# 產生 HMAC 簽章
MESSAGE="${METHOD}\n${PATH}\n${TIMESTAMP}\n${NONCE}\n"
SIGNATURE=$(echo -n "${MESSAGE}" | openssl dgst -sha256 -hmac "${CLIENT_SECRET}" | cut -d' ' -f2)

# 發送請求
curl -X GET "${BASE_URL}${PATH}?capabilities=true" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Timestamp: ${TIMESTAMP}" \
  -H "X-Nonce: ${NONCE}" \
  -H "X-Signature: ${SIGNATURE}" \
  | jq .
```

---

## 相關文件

- [API 基礎概念](control/api-basics.md) - 認證機制與基礎架構
- [安全性指南](control/security.md) - HMAC 簽章詳細說明
- [程式碼範例](control-examples.md) - 更多實作範例
- [故障排除](control/troubleshooting.md) - 常見問題解決

---

## 版本歷史

- **v1.0.0** (2026-01-08)
  - 初始版本
  - 支援快照、MJPEG 串流、HLS 串流
  - 實作 ETag 快取機制
  - 新增攝影機設定管理 API

---

## 授權

本文件依據專案主要授權條款發佈。
