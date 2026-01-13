# WebRTC 串流 API 文件

## 目錄

- [概述](#概述)
- [認證流程](#認證流程)
- [API 端點總覽](#api-端點總覽)
- [詳細 API 規格](#詳細-api-規格)
  - [1. 請求 WebRTC Token](#1-請求-webrtc-token)
  - [2. SDP Offer/Answer 交換](#2-sdp-offeranswer-交換)
  - [3. ICE Candidate 交換](#3-ice-candidate-交換)
  - [4. 關閉 WebRTC Session](#4-關閉-webrtc-session)
- [完整流程範例](#完整流程範例)
- [錯誤碼](#錯誤碼)
- [Session 生命週期管理](#session-生命週期管理)
- [go2rtc 整合架構](#go2rtc-整合架構)
- [前置需求](#前置需求)
  - [go2rtc 安裝](#go2rtc-安裝)
  - [攝影機 Stream Source](#攝影機-stream-source)
  - [網路配置](#網路配置)
  - [TURN 伺服器設定](#turn-伺服器設定)
- [Python 完整範例](#python-完整範例)
- [除錯技巧](#除錯技巧)

---

## 概述

Smartly Bridge WebRTC API 提供**點對點（Peer-to-Peer）視訊串流**功能，直接在 Platform 與 Home Assistant 之間建立連線，具備以下優勢：

- ✅ **低延遲**：P2P 直連，減少中繼延遲
- ✅ **節省頻寬**：直接傳輸，不佔用伺服器頻寬
- ✅ **高品質**：支援自適應碼率與解析度
- ✅ **零配置**：自動串流註冊，無需手動配置 go2rtc

**技術特性：**
- Token-based 認證（5 分鐘 TTL）
- 單次使用 Token，防止重放攻擊
- 自動整合 Home Assistant 的 go2rtc 媒體伺服器
- 支援 STUN/TURN NAT 穿透
- Session 自動管理與清理（10 分鐘閒置超時）

---

## 認證流程

WebRTC 使用**兩階段認證機制**：

### 階段 1：Token 請求（HMAC 認證）

Platform 使用 HMAC 簽章認證請求短期 Token：

```
Platform → Home Assistant
  POST /api/smartly/camera/{entity_id}/webrtc
  Headers: X-Client-Id, X-Timestamp, X-Nonce, X-Signature
  
Home Assistant → Platform
  Response: { token, expires_at, ice_servers, ... }
```

### 階段 2：信令交換（Token 認證）

使用 Token 進行 WebRTC 信令交換（SDP、ICE）：

```
Platform → Home Assistant
  POST /api/smartly/camera/{entity_id}/webrtc/offer
  Body: { token, sdp, type }
  
Home Assistant → Platform
  Response: { type: "answer", sdp, session_id }
```

**重要特性：**
- Token 單次使用後即失效
- Token 綁定特定攝影機（entity_id）
- Token 有效期 5 分鐘
- Session 閒置 10 分鐘自動關閉

---

## API 端點總覽

| 端點 | 方法 | 認證方式 | 說明 |
|------|------|---------|------|
| `/api/smartly/camera/{entity_id}/webrtc` | POST | HMAC | 請求 WebRTC Token |
| `/api/smartly/camera/{entity_id}/webrtc/offer` | POST | Token | SDP Offer/Answer 交換 |
| `/api/smartly/camera/{entity_id}/webrtc/ice` | POST | Session | ICE Candidate 交換 |
| `/api/smartly/camera/{entity_id}/webrtc/hangup` | POST | Session | 關閉 WebRTC Session |

---

## 詳細 API 規格

### 1. 請求 WebRTC Token

Platform 使用 HMAC 認證請求短期 Token，用於後續的 WebRTC 信令交換。

#### 端點

```
POST /api/smartly/camera/{entity_id}/webrtc
```

#### 路徑參數

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `entity_id` | string | 是 | 攝影機實體 ID，格式：`camera.*` |

#### Request Headers

```http
X-Client-Id: mobile-app-001
X-Timestamp: 1735228800
X-Nonce: abc123def456
X-Signature: a3f8b2c1d4e5f6...
Content-Type: application/json
```

#### Request Body

```json
{}
```

#### Response (成功 - 200 OK)

```json
{
  "token": "xxxxx...",
  "expires_at": 1735229100,
  "expires_in": 300,
  "entity_id": "camera.front_door",
  "offer_endpoint": "/api/smartly/camera/camera.front_door/webrtc/offer",
  "ice_endpoint": "/api/smartly/camera/camera.front_door/webrtc/ice",
  "hangup_endpoint": "/api/smartly/camera/camera.front_door/webrtc/hangup",
  "ice_servers": [
    {
      "urls": "stun:stun.l.google.com:19302"
    },
    {
      "urls": "stun:stun1.l.google.com:19302"
    },
    {
      "urls": "stun:stun2.l.google.com:19302"
    }
  ]
}
```

#### Response 欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `token` | string | WebRTC 認證 Token（256-bit，單次使用） |
| `expires_at` | number | Token 到期時間（Unix 時間戳） |
| `expires_in` | number | Token 剩餘有效秒數 |
| `entity_id` | string | 攝影機實體 ID |
| `offer_endpoint` | string | SDP Offer 交換端點 |
| `ice_endpoint` | string | ICE Candidate 交換端點 |
| `hangup_endpoint` | string | 關閉 Session 端點 |
| `ice_servers` | array | ICE 伺服器列表（STUN/TURN） |

#### 重要特性

- ✅ Token 有效期：5 分鐘（300 秒）
- ✅ 單次使用：消費後即失效，防止重放攻擊
- ✅ 實體綁定：Token 只能用於請求的攝影機
- ✅ 動態 ICE Servers：根據設定返回 STUN 或 STUN+TURN

#### HMAC 簽章計算

```python
import hashlib
import hmac

def generate_signature(client_secret, method, path, timestamp, nonce, body=""):
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    signature = hmac.new(
        client_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature
```

---

### 2. SDP Offer/Answer 交換

使用 Token 交換 SDP（Session Description Protocol），建立 WebRTC 連線。

#### 端點

```
POST /api/smartly/camera/{entity_id}/webrtc/offer
```

#### Request

```http
POST /api/smartly/camera/camera.front_door/webrtc/offer HTTP/1.1
Content-Type: application/json

{
  "token": "xxxxx...",
  "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\n...",
  "type": "offer"
}
```

#### Request 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `token` | string | 是 | 從 Token 請求端點取得的 Token |
| `sdp` | string | 是 | SDP Offer 內容 |
| `type` | string | 是 | 固定為 `"offer"` |

#### Response (成功 - 200 OK)

```json
{
  "type": "answer",
  "sdp": "v=0\r\no=- 789012 2 IN IP4 192.168.1.100\r\n...",
  "session_id": "abcdefghijklmnop"
}
```

#### Response 欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `type` | string | 固定為 `"answer"` |
| `sdp` | string | SDP Answer 內容 |
| `session_id` | string | WebRTC Session ID（用於後續操作） |

#### 技術說明

**Token 消費機制：**
- Token 在此步驟被**消費**，之後無法再次使用
- 成功交換後產生 Session ID，用於後續 ICE 和 Hangup 操作

**go2rtc 整合：**
- SDP Answer 由 go2rtc 生成
- 自動從 Home Assistant 取得攝影機串流來源
- 若串流未在 go2rtc 註冊，自動執行動態註冊

---

### 3. ICE Candidate 交換

交換 ICE（Interactive Connectivity Establishment）候選者，用於 NAT 穿越。

#### 端點

```
POST /api/smartly/camera/{entity_id}/webrtc/ice
```

#### Request

```http
POST /api/smartly/camera/camera.front_door/webrtc/ice HTTP/1.1
Content-Type: application/json

{
  "session_id": "abcdefghijklmnop",
  "candidate": {
    "candidate": "candidate:1 1 UDP 2130706431 192.168.1.100 54321 typ host",
    "sdpMid": "0",
    "sdpMLineIndex": 0
  }
}
```

#### Request 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `session_id` | string | 是 | 從 SDP 交換取得的 Session ID |
| `candidate` | object | 是 | ICE Candidate 物件 |
| `candidate.candidate` | string | 是 | ICE Candidate 字串 |
| `candidate.sdpMid` | string | 是 | Media Stream ID |
| `candidate.sdpMLineIndex` | number | 是 | Media Line Index |

#### Response (成功 - 200 OK)

```json
{
  "status": "accepted",
  "candidates": []
}
```

#### Response 欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `status` | string | 固定為 `"accepted"` |
| `candidates` | array | 伺服器端的 ICE Candidates（如有） |

#### ICE Candidate 類型

| Type | 說明 | 優先級 |
|------|------|--------|
| `host` | 本地網路位址 | 最高（最佳） |
| `srflx` | 透過 STUN 取得的公網 IP | 高（良好） |
| `relay` | 透過 TURN 中繼 | 中（嚴格 NAT 必須） |

---

### 4. 關閉 WebRTC Session

主動關閉 WebRTC 連線，釋放資源。

#### 端點

```
POST /api/smartly/camera/{entity_id}/webrtc/hangup
```

#### Request

```http
POST /api/smartly/camera/camera.front_door/webrtc/hangup HTTP/1.1
Content-Type: application/json

{
  "session_id": "abcdefghijklmnop"
}
```

#### Request 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `session_id` | string | 是 | WebRTC Session ID |

#### Response (成功 - 200 OK)

```json
{
  "status": "closed"
}
```

#### 自動清理機制

即使未主動呼叫 Hangup，Session 也會自動清理：
- **閒置超時**：10 分鐘無活動自動關閉
- **背景清理**：每 60 秒檢查並清理過期資源

---

## 完整流程範例

### JavaScript (瀏覽器)

```javascript
// 1. 請求 Token
const tokenResponse = await fetch('/api/smartly/camera/camera.front_door/webrtc', {
  method: 'POST',
  headers: {
    'X-Client-Id': clientId,
    'X-Timestamp': timestamp,
    'X-Nonce': nonce,
    'X-Signature': signature,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({})
});
const { token, ice_servers, offer_endpoint } = await tokenResponse.json();

// 2. 建立 RTCPeerConnection
const pc = new RTCPeerConnection({ iceServers: ice_servers });

// 3. 建立 Offer
const offer = await pc.createOffer();
await pc.setLocalDescription(offer);

// 4. 交換 SDP Offer
const offerResponse = await fetch(offer_endpoint, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    token: token,
    sdp: offer.sdp,
    type: 'offer'
  })
});
const { sdp: answerSdp, session_id } = await offerResponse.json();

// 5. 設定 Remote Description
await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

// 6. 交換 ICE Candidates
pc.onicecandidate = async (event) => {
  if (event.candidate) {
    await fetch('/api/smartly/camera/camera.front_door/webrtc/ice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: session_id,
        candidate: {
          candidate: event.candidate.candidate,
          sdpMid: event.candidate.sdpMid,
          sdpMLineIndex: event.candidate.sdpMLineIndex
        }
      })
    });
  }
};

// 7. 接收媒體串流
pc.ontrack = (event) => {
  videoElement.srcObject = event.streams[0];
};

// 8. 結束時關閉 Session
window.addEventListener('beforeunload', async () => {
  await fetch('/api/smartly/camera/camera.front_door/webrtc/hangup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: session_id })
  });
  pc.close();
});
```

---

## 錯誤碼

### Token 請求錯誤

| HTTP Status | Error Code | 說明 |
|-------------|------------|------|
| 400 | `invalid_entity_id` | entity_id 格式錯誤或不存在 |
| 401 | `invalid_signature` | HMAC 簽章驗證失敗 |
| 401 | `invalid_timestamp` | 時間戳不在有效範圍內 |
| 401 | `nonce_already_used` | Nonce 已被使用過 |
| 403 | `ip_not_allowed` | IP 不在白名單內 |
| 403 | `entity_not_allowed` | 攝影機未被授權存取 |
| 404 | `entity_not_found` | 找不到指定攝影機 |
| 429 | `rate_limited` | 超過速率限制 |
| 500 | `integration_not_configured` | 整合尚未設定 |
| 500 | `webrtc_not_available` | WebRTC 服務未初始化 |

### SDP 交換錯誤

| HTTP Status | Error Code | 說明 |
|-------------|------------|------|
| 400 | `missing_token` | 缺少 token 參數 |
| 400 | `missing_sdp` | 缺少 SDP offer |
| 400 | `invalid_sdp_type` | SDP type 必須為 'offer' |
| 401 | `invalid_or_expired_token` | Token 無效或已過期 |
| 403 | `entity_not_allowed` | 攝影機未被授權存取 |
| 404 | `entity_not_found` | 找不到指定攝影機 |
| 500 | `webrtc_failed` | WebRTC 連線建立失敗 |
| 500 | `go2rtc_not_available` | go2rtc 服務不可用 |
| 500 | `stream_source_not_found` | 攝影機無可用串流來源 |

### Session 操作錯誤

| HTTP Status | Error Code | 說明 |
|-------------|------------|------|
| 400 | `missing_session_id` | 缺少 session_id |
| 404 | `session_not_found` | Session 不存在或已過期 |

---

## Session 生命週期管理

### Token 生命週期

```
Token 生成
  ↓
有效期: 5 分鐘
  ↓
單次消費（SDP 交換）
  ↓
Token 失效
```

### Session 生命週期

```
Session 建立（SDP 交換後）
  ↓
活動狀態（接收 ICE Candidate）
  ↓
閒置檢測（10 分鐘無活動）
  ↓
自動清理 或 手動 Hangup
```

### 自動清理機制

**背景任務：** 每 60 秒執行一次

**清理對象：**
- 過期的 Token（超過 5 分鐘）
- 閒置的 Session（超過 10 分鐘無活動）

**日誌範例：**
```
INFO Cleaned up 3 expired tokens and 1 idle session
```

---

## go2rtc 整合架構

### 架構圖

```
┌─────────────────┐     ┌─────────────────────────────────────────┐
│                 │     │           Home Assistant                 │
│    Platform     │     │  ┌─────────────────────────────────────┐ │
│   (Browser/App) │     │  │        Smartly Bridge               │ │
│                 │     │  │                                     │ │
│  ┌───────────┐  │     │  │  ┌─────────────┐   ┌─────────────┐ │ │
│  │RTCPeer    │◄─┼─────┼──┼──┤WebRTC Views │◄──┤Token Manager│ │ │
│  │Connection │  │     │  │  └──────┬──────┘   └─────────────┘ │ │
│  └───────────┘  │     │  │         │                          │ │
│                 │     │  │         │ HTTP API                 │ │
│                 │     │  │         ▼                          │ │
│                 │     │  │  ┌─────────────┐                   │ │
│                 │     │  │  │  go2rtc     │◄── RTSP/Stream    │ │
│                 │     │  │  │ (Port 1984) │    Source         │ │
│                 │     │  │  └─────────────┘                   │ │
│                 │     │  └─────────────────────────────────────┘ │
└─────────────────┘     └─────────────────────────────────────────┘
```

### go2rtc 配置

**預設設定：**

| 常數 | 值 | 說明 |
|------|-----|------|
| `GO2RTC_URL` | `http://localhost:1984` | go2rtc 伺服器 URL |
| `GO2RTC_WEBRTC_TIMEOUT` | `10.0` 秒 | WebRTC 操作超時時間 |

### SDP 交換流程

```
1. Platform 發送 SDP Offer
       │
       ▼
2. 驗證 Token（消費後失效）
       │
       ▼
3. 從 Home Assistant 取得 Camera Stream Source
   └─► async_get_stream_source(hass, entity_id)
       │
       ▼
4. 向 go2rtc 發送 SDP Offer
   └─► POST http://localhost:1984/api/webrtc?src={entity_id}
       │
       ├─► 成功 (200)：取得 SDP Answer
       │
       └─► 失敗 (404)：Stream 不存在
           │
           ▼
5. 動態註冊 Stream 到 go2rtc
   └─► PUT http://localhost:1984/api/streams?name={entity_id}&src={rtsp_url}
       │
       ▼
6. 重試 SDP Offer
       │
       ▼
7. 返回 SDP Answer 給 Platform
```

### go2rtc API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/webrtc?src={stream}` | POST | WHEP 風格 SDP 交換 |
| `/api/streams?name={name}&src={url}` | PUT | 動態新增串流 |

### 自動串流註冊

**零配置體驗：**
- 當攝影機在 go2rtc 中尚未註冊時，Smartly Bridge 自動：
  1. 從 Home Assistant 取得攝影機的 RTSP/Stream Source
  2. 向 go2rtc 動態註冊該串流
  3. 重試 WebRTC 連線

**優勢：**
- ✅ 無需手動在 go2rtc 配置檔中添加攝影機
- ✅ 新增攝影機時自動生效
- ✅ 簡化部署流程

---

## 前置需求

### go2rtc 安裝

#### Docker 方式（推薦）

```bash
docker run -d --name go2rtc \
  --network host \
  ghcr.io/alexxit/go2rtc:latest
```

#### 獨立安裝

```bash
# 下載最新版本
wget https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_amd64

# 給予執行權限
chmod +x go2rtc_linux_amd64

# 啟動
./go2rtc_linux_amd64
```

#### 驗證安裝

```bash
curl http://localhost:1984/api/streams
# 應返回 {} 或已配置的串流列表
```

---

### 攝影機 Stream Source

攝影機必須在 Home Assistant 中配置有效的串流來源（RTSP URL）。

#### 驗證方式

**方法 1：Developer Tools**

```yaml
# Home Assistant Developer Tools > Services
service: camera.request_stream
data:
  entity_id: camera.front_door
```

**方法 2：檢查實體屬性**

```python
# Home Assistant > Developer Tools > States
# 查找 camera.front_door
# 檢查 attributes 中是否有 stream_source 或 rtsp_url
```

**方法 3：日誌檢查**

```bash
# 啟用 DEBUG 日誌後檢查
grep "stream source" home-assistant.log
```

---

### 網路配置

#### STUN 伺服器（預設）

Smartly Bridge 預設使用 **Google 公共 STUN 伺服器**進行 NAT 穿透：

```json
{
  "ice_servers": [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {"urls": "stun:stun2.l.google.com:19302"}
  ]
}
```

**適用環境：**
- 一般家用網路（約 85% 的情況）
- 簡單 NAT 環境
- 直連網路

**不適用環境：**
- 嚴格 NAT（Strict NAT）
- 對稱型 NAT（Symmetric NAT）
- 企業防火牆後方
- 多層 NAT

---

### TURN 伺服器設定

對於嚴格 NAT 環境或需要保證連線成功率，**強烈建議設定 TURN 伺服器**。

#### Home Assistant 設定步驟

1. 前往 **Settings → Devices & Services → Smartly Bridge**
2. 點擊 **Configure**
3. 填入 TURN 伺服器資訊：
   - **TURN URL**: `turn:turn.example.com:3478` 或 `turns:turn.example.com:5349`（TLS）
   - **TURN Username**: 認證使用者名稱
   - **TURN Credential**: 認證密碼或 Token

#### 常見 TURN 伺服器提供商

| 服務 | 類型 | 說明 | 費用 |
|------|------|------|------|
| [Coturn](https://github.com/coturn/coturn) | 自架 | 開源 TURN 伺服器 | 免費（需自行架設） |
| [Twilio STUN/TURN](https://www.twilio.com/stun-turn) | 商用 | 全球分佈式 TURN | 免費額度：3GB/月 |
| [Xirsys](https://xirsys.com/) | 商用 | WebRTC 基礎設施 | 免費額度：500MB/月 |
| [Metered TURN](https://www.metered.ca/tools/openrelay/) | 免費 | 公開測試用 | 完全免費（測試用） |

#### 自架 Coturn 範例

**Docker Compose：**

```yaml
version: '3'
services:
  coturn:
    image: coturn/coturn
    network_mode: host
    volumes:
      - ./turnserver.conf:/etc/coturn/turnserver.conf
    restart: unless-stopped
```

**turnserver.conf：**

```ini
# TURN 伺服器監聽埠
listening-port=3478
tls-listening-port=5349

# 公網 IP（必須設定）
external-ip=YOUR_PUBLIC_IP

# 認證方式
lt-cred-mech
user=myuser:mypassword
realm=turn.example.com

# 日誌
verbose
log-file=/var/log/turnserver.log
```

**啟動：**

```bash
docker-compose up -d
```

#### 防火牆規則

確保以下端口開放：

| 端口 | 協議 | 用途 | 必須 |
|------|------|------|------|
| 40000-60000 | UDP | WebRTC 媒體傳輸 | ✅ 是 |
| 1984 | TCP | go2rtc API（內部） | ⚠️ 僅內部網路 |
| 3478 | UDP/TCP | TURN 伺服器 | 若使用 TURN |
| 5349 | TCP | TURN over TLS | 若使用 TURN/TLS |

#### 網路測試工具

**測試 STUN 伺服器：**

```bash
# 安裝 stun-client
sudo apt-get install stun-client

# 測試
stunclient stun.l.google.com 19302
```

**測試 TURN 伺服器：**

```bash
# 安裝 coturn 測試工具
sudo apt-get install coturn

# 測試 TURN 連線
turnutils_uclient -v \
  -u myuser \
  -w mypassword \
  turn.example.com
```

**預期輸出：**
```
Total connect time is 0
start_mclient: tot_send_msgs=0, tot_recv_msgs=0, tot_send_bytes ~ 100, tot_recv_bytes ~ 100
```

---

## Python 完整範例

```python
import asyncio
import hashlib
import hmac
import json
import time
import uuid

import aiohttp


class SmartlyWebRTCClient:
    """Smartly Bridge WebRTC 客戶端範例"""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    def _generate_signature(
        self, method: str, path: str, body: str = ""
    ) -> dict[str, str]:
        """產生 HMAC 認證標頭"""
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        
        message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
        signature = hmac.new(
            self.client_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return {
            "X-Client-Id": self.client_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
            "Content-Type": "application/json",
        }

    async def request_token(self, entity_id: str) -> dict:
        """請求 WebRTC Token"""
        path = f"/api/smartly/camera/{entity_id}/webrtc"
        body = "{}"
        headers = self._generate_signature("POST", path, body)

        async with self.session.post(
            f"{self.base_url}{path}",
            headers=headers,
            data=body,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def send_offer(
        self, entity_id: str, token: str, sdp_offer: str
    ) -> dict:
        """發送 SDP Offer 並取得 Answer"""
        path = f"/api/smartly/camera/{entity_id}/webrtc/offer"
        body = json.dumps({
            "token": token,
            "sdp": sdp_offer,
            "type": "offer",
        })

        async with self.session.post(
            f"{self.base_url}{path}",
            headers={"Content-Type": "application/json"},
            data=body,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def send_ice_candidate(
        self, entity_id: str, session_id: str, candidate: dict
    ) -> dict:
        """發送 ICE Candidate"""
        path = f"/api/smartly/camera/{entity_id}/webrtc/ice"
        body = json.dumps({
            "session_id": session_id,
            "candidate": candidate,
        })

        async with self.session.post(
            f"{self.base_url}{path}",
            headers={"Content-Type": "application/json"},
            data=body,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def hangup(self, entity_id: str, session_id: str) -> dict:
        """關閉 WebRTC Session"""
        path = f"/api/smartly/camera/{entity_id}/webrtc/hangup"
        body = json.dumps({"session_id": session_id})

        async with self.session.post(
            f"{self.base_url}{path}",
            headers={"Content-Type": "application/json"},
            data=body,
        ) as response:
            response.raise_for_status()
            return await response.json()


async def main():
    """示範 WebRTC 連線流程"""
    async with SmartlyWebRTCClient(
        base_url="http://homeassistant.local:8123",
        client_id="ha_abc123def456",
        client_secret="your-secret-key-at-least-32-chars",
    ) as client:
        entity_id = "camera.front_door"

        # 1. 請求 Token
        print("1. 請求 WebRTC Token...")
        token_response = await client.request_token(entity_id)
        print(f"   Token: {token_response['token'][:20]}...")
        print(f"   有效期: {token_response['expires_in']} 秒")
        print(f"   ICE Servers: {len(token_response['ice_servers'])} 個")

        # 檢查是否有 TURN 伺服器
        has_turn = any('turn' in server.get('urls', '') for server in token_response['ice_servers'])
        print(f"   TURN 已設定: {'是' if has_turn else '否'}")

        # 2. 模擬 SDP Offer（實際應由 WebRTC library 產生）
        mock_sdp_offer = """v=0
o=- 123456789 2 IN IP4 127.0.0.1
s=-
t=0 0
m=video 9 UDP/TLS/RTP/SAVPF 96
c=IN IP4 0.0.0.0
a=rtcp:9 IN IP4 0.0.0.0
a=recvonly
"""

        # 3. 發送 SDP Offer
        print("\n2. 發送 SDP Offer...")
        try:
            offer_response = await client.send_offer(
                entity_id,
                token_response["token"],
                mock_sdp_offer,
            )
            print(f"   Session ID: {offer_response['session_id']}")
            print(f"   Answer Type: {offer_response['type']}")
            print(f"   Answer SDP 長度: {len(offer_response.get('sdp', ''))} 字元")
        except aiohttp.ClientResponseError as e:
            print(f"   錯誤: {e.status} - {e.message}")
            return

        # 4. 發送 ICE Candidate（示範）
        print("\n3. 發送 ICE Candidate...")
        ice_response = await client.send_ice_candidate(
            entity_id,
            offer_response["session_id"],
            {
                "candidate": "candidate:0 1 UDP 2122252543 192.168.1.100 12345 typ host",
                "sdpMid": "0",
                "sdpMLineIndex": 0,
            },
        )
        print(f"   狀態: {ice_response['status']}")

        # 5. 關閉 Session
        print("\n4. 關閉 WebRTC Session...")
        hangup_response = await client.hangup(entity_id, offer_response["session_id"])
        print(f"   狀態: {hangup_response['status']}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 除錯技巧

### 檢查 go2rtc 狀態

```bash
# 檢查 go2rtc 是否運行
curl -s http://localhost:1984/api/streams | jq .

# 檢查特定串流
curl -s "http://localhost:1984/api/streams?name=camera.front_door" | jq .

# 檢查 go2rtc 版本
curl -s http://localhost:1984/api/config | jq .version
```

### 查看 Home Assistant 日誌

**啟用詳細日誌：**

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.smartly_bridge.views.webrtc: debug
    custom_components.smartly_bridge.webrtc: debug
```

**日誌範例：**

```
INFO  WebRTC offer received - entity_id: camera.front_door, client_id: ha_abc123, token: aBcDeFgHiJkL..., sdp_length: 1234
DEBUG Sending WebRTC offer to go2rtc for camera.front_door: http://localhost:1984/api/webrtc
DEBUG Using ICE servers with TURN: turn:turn.example.com:3478
INFO  Successfully got WebRTC answer from go2rtc for camera.front_door
INFO  WebRTC answer generated - entity_id: camera.front_door, session_id: aBcDeFgHiJkL, sdp_length: 2345
```

### 常見問題診斷

| 問題 | 原因 | 解決方案 |
|------|------|---------|
| `webrtc_failed: Failed to connect to go2rtc` | go2rtc 未運行 | 啟動 go2rtc 服務：`docker restart go2rtc` |
| `No stream source available` | 攝影機無 RTSP 來源 | 檢查攝影機配置，確認 stream_source 存在 |
| `invalid_or_expired_token` | Token 過期或已使用 | 重新請求 Token，確保 5 分鐘內使用 |
| 連線建立但無影像 | ICE 失敗（STUN 無法穿透） | 1. 檢查防火牆 UDP 40000-60000<br>2. 設定 TURN 伺服器 |
| WebRTC 連線緩慢或不穩定 | STUN only，透過公網中繼 | 設定 TURN 伺服器提升連線品質 |
| TURN 伺服器設定無效 | 認證失敗或伺服器不可達 | 使用 `turnutils_uclient` 測試 TURN 連線 |
| 嚴格 NAT 環境無法建立連線 | 對稱型 NAT 阻擋 P2P | 必須設定 TURN 伺服器進行中繼 |
| Session 自動斷開 | 閒置超過 10 分鐘 | 定期發送 ICE Candidate 保持活動狀態 |

### TURN 伺服器測試

```bash
# 安裝 coturn 測試工具
sudo apt-get install coturn

# 測試 TURN 伺服器連線
turnutils_uclient -v \
  -u myuser \
  -w mypassword \
  turn.example.com

# 預期輸出包含：
# - "start_mclient: tot_send_msgs=0, tot_recv_msgs=0, tot_send_bytes ~ 100, tot_recv_bytes ~ 100"
# - "Total connect time is ..."
```

### 檢查 ICE Servers 設定

在 WebRTC Token Response 中檢查 `ice_servers` 欄位：

```json
{
  "token": "...",
  "ice_servers": [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {"urls": "stun:stun2.l.google.com:19302"},
    {
      "urls": "turn:turn.example.com:3478",
      "username": "myuser",
      "credential": "mypassword"
    }
  ]
}
```

**如果未看到 TURN 伺服器資訊：**
1. 檢查 Home Assistant 整合設定是否正確填入 TURN URL/Username/Credential
2. 重新載入 Smartly Bridge 整合
3. 檢查 Home Assistant 日誌是否有 TURN 相關錯誤

### WebRTC 連線品質測試

**瀏覽器 WebRTC Internals：**

1. **Chrome**：前往 `chrome://webrtc-internals/`
2. **Firefox**：前往 `about:webrtc`

**重點檢查項目：**

| 項目 | 說明 | 良好狀態 |
|------|------|---------|
| **ICE Candidate Type** | 連線類型 | `host` > `srflx` > `relay` |
| **RTCPeerConnection State** | 連線狀態 | `connected` 或 `completed` |
| **Bitrate** | 碼率 | 500-2000 kbps（視解析度） |
| **Packets Lost** | 丟包率 | < 1% |
| **Round Trip Time (RTT)** | 往返延遲 | < 100ms |

**ICE Candidate Type 說明：**

- **host**：本地網路（最佳，延遲最低）
- **srflx**：透過 STUN 取得的公網 IP（良好，適用於一般 NAT）
- **relay**：透過 TURN 中繼（可接受，適用於嚴格 NAT）

### 效能監控

**Session 統計：**

```python
# 透過 WebRTCTokenManager 取得統計
stats = webrtc_manager.get_stats()
print(f"Active Tokens: {stats['active_tokens']}")
print(f"Active Sessions: {stats['active_sessions']}")
```

**go2rtc 統計：**

```bash
# 檢查 go2rtc 統計資訊
curl -s http://localhost:1984/api/stats | jq .
```

---

## 相關文件

- [Camera API 完整文件](camera-api.md) - 包含快照、MJPEG、HLS 等其他攝影機功能
- [API 基礎概念](control/api-basics.md) - HMAC 認證機制詳細說明
- [安全性指南](control/security.md) - 安全最佳實作
- [故障排除](control/troubleshooting.md) - 常見問題解決

---

## 版本歷史

- **v1.2.0** (2026-01-12)
  - 🚀 實作 go2rtc 整合與自動串流註冊
  - 🌐 新增 TURN 伺服器支援（Config Flow 設定）
  - 📝 完整文件更新（含 TURN 設定指南）

- **v1.1.0** (2026-01-12)
  - ✨ 新增 WebRTC P2P 串流支援
  - 實作 Token-based 認證機制（5 分鐘 TTL）
  - 支援 SDP Offer/Answer 和 ICE Candidate 交換
  - Session 自動管理與清理（10 分鐘閒置超時）
  - 新增 37 個 WebRTC 相關測試案例

---

## 授權

本文件依據專案主要授權條款發佈。
