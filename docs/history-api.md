# History API - 設備歷史數據查詢

## 概述

History API 提供查詢 Home Assistant 實體歷史狀態的功能，支援單一實體查詢、批量查詢和統計數據查詢。所有請求都需要通過 HMAC-SHA256 簽名驗證。

**版本：** 1.2.0  
**基礎 URL：** `http://your-home-assistant:8123`

---

## 🔐 認證機制

所有 History API 請求都需要以下 HTTP Headers：

| Header | 類型 | 說明 |
|--------|------|------|
| `X-Client-Id` | string | 客戶端 ID |
| `X-Timestamp` | string | Unix 時間戳（秒） |
| `X-Nonce` | string | 隨機字串（建議使用 UUID） |
| `X-Signature` | string | HMAC-SHA256 簽名 |

### 簽名計算方式

```
signature = HMAC-SHA256(client_secret, message)

message = METHOD + "\n" +
          PATH_WITH_QUERY + "\n" +
          TIMESTAMP + "\n" +
          NONCE + "\n" +
          BODY_HASH

BODY_HASH = SHA256(request_body)  # GET 請求為空字串
```

**⚠️ 重要事項：**
1. **PATH_WITH_QUERY 必須包含完整的查詢參數**
2. 查詢參數使用**未編碼**的值（與 aiohttp `request.path_qs` 一致）
3. 時間戳有效期限為 5 分鐘
4. Nonce 在時間窗口內不可重複使用

### 簽名範例（Python）

```python
import hashlib
import hmac
from datetime import datetime

def calculate_signature(
    client_secret: str,
    method: str,
    path_with_query: str,
    timestamp: str,
    nonce: str,
    body: str = ""
) -> str:
    """計算 HMAC-SHA256 簽名"""
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    message = f"{method}\n{path_with_query}\n{timestamp}\n{nonce}\n{body_hash}"
    
    signature = hmac.new(
        client_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature

# 範例
method = "GET"
path_with_query = "/api/smartly/history/camera.test?start_time=2026-01-09T00:00:00Z&end_time=2026-01-10T00:00:00Z&limit=1000"
timestamp = str(int(datetime.now().timestamp()))
nonce = "uuid-v4-string"
client_secret = "your-client-secret"

signature = calculate_signature(
    client_secret, method, path_with_query, timestamp, nonce
)
```

### Postman Pre-request Script

```javascript
// Smartly Bridge HMAC Signature Authentication

const clientId = pm.environment.get("client_id");
const clientSecret = pm.environment.get("client_secret");

if (!clientId || !clientSecret) {
    throw new Error("Missing client_id or client_secret in environment variables");
}

// 獲取當前時間戳（秒）
const timestamp = Math.floor(Date.now() / 1000).toString();

// 生成隨機 nonce (UUID v4)
const nonce = [...Array(36)].map((_, i) => 
    [8, 13, 18, 23].includes(i) ? '-' : 
    i === 14 ? '4' : 
    (Math.random() * 16 | 0).toString(16)
).join('');

// 設置請求頭
pm.request.headers.upsert({ key: "X-Client-Id", value: clientId });
pm.request.headers.upsert({ key: "X-Timestamp", value: timestamp });
pm.request.headers.upsert({ key: "X-Nonce", value: nonce });

// 遞歸替換所有變量
function replaceVariables(str, maxDepth = 10) {
    let result = str;
    let depth = 0;
    
    while (depth < maxDepth && /\{\{.+?\}\}/.test(result)) {
        const originalResult = result;
        
        result = result.replace(/\{\{(.+?)\}\}/g, (match, varName) => {
            const value = pm.environment.get(varName) || 
                         pm.variables.get(varName) || 
                         pm.collectionVariables.get(varName);
            return value !== undefined ? value : match;
        });
        
        if (result === originalResult) break;
        depth++;
    }
    
    return result;
}

let fullUrl = pm.request.url.toString();
fullUrl = replaceVariables(fullUrl);

// 提取路徑 + 查詢參數
let path = '/';
try {
    const urlObj = new URL(fullUrl);
    path = urlObj.pathname + urlObj.search;
} catch (e) {
    const urlWithoutProtocol = fullUrl.replace(/^https?:\/\/[^\/]+/, '');
    path = urlWithoutProtocol;
}

const method = pm.request.method;
const body = pm.request.body && pm.request.body.raw ? pm.request.body.raw : "";

// 計算 body hash (SHA256)
const bodyHash = CryptoJS.SHA256(body).toString(CryptoJS.enc.Hex);

// 構建簽名消息
const message = `${method}\n${path}\n${timestamp}\n${nonce}\n${bodyHash}`;

// 計算 HMAC-SHA256 簽名
const signature = CryptoJS.HmacSHA256(message, clientSecret).toString(CryptoJS.enc.Hex);

// 設置簽名請求頭
pm.request.headers.upsert({ key: "X-Signature", value: signature });

console.log("Path:", path);
console.log("Message to sign:\n" + message);
```

---

## 📡 API 端點

### 1. 查詢單一實體歷史

**端點：** `GET /api/smartly/history/{entity_id}`

查詢指定實體的歷史狀態數據。

#### 路徑參數

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `entity_id` | string | ✅ | Home Assistant 實體 ID（例如：`camera.test`、`sensor.temperature`） |

#### 查詢參數

| 參數 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `start_time` | string | ❌ | 24小時前 | 開始時間（ISO 8601 格式，例如：`2026-01-09T00:00:00Z`） |
| `end_time` | string | ❌ | 現在 | 結束時間（ISO 8601 格式） |
| `limit` | integer | ❌ | 1000 | 返回的最大記錄數（最大 1000） |
| `significant_changes_only` | boolean | ❌ | true | 是否只返回顯著變化的狀態 |

#### 限制

- 時間範圍最長 30 天
- 單次查詢最多返回 1000 筆記錄
- 僅能查詢有權限的實體

#### 請求範例

```http
GET /api/smartly/history/camera.test?start_time=2026-01-09T00:00:00Z&end_time=2026-01-10T00:00:00Z&limit=100&significant_changes_only=true
Host: localhost:8123
X-Client-Id: ha_your-client-id
X-Timestamp: 1768018354
X-Nonce: uuid-v4-string
X-Signature: computed-hmac-signature
```

#### 成功響應（200 OK）

```json
{
  "entity_id": "camera.test",
  "history": [
    {
      "state": "idle",
      "attributes": {
        "friendly_name": "Test Camera",
        "supported_features": 1
      },
      "last_changed": "2026-01-09T10:30:00+00:00",
      "last_updated": "2026-01-09T10:30:00+00:00"
    },
    {
      "state": "recording",
      "attributes": {
        "friendly_name": "Test Camera",
        "supported_features": 1
      },
      "last_changed": "2026-01-09T12:15:30+00:00",
      "last_updated": "2026-01-09T12:15:30+00:00"
    }
  ],
  "count": 2,
  "truncated": false,
  "start_time": "2026-01-09T00:00:00+00:00",
  "end_time": "2026-01-10T00:00:00+00:00"
}
```

#### 錯誤響應

```json
// 401 Unauthorized - 簽名驗證失敗
{
  "error": "invalid_signature"
}

// 403 Forbidden - 無權限訪問該實體
{
  "error": "forbidden",
  "message": "No permission to access entity: camera.test"
}

// 404 Not Found - 實體不存在
{
  "error": "entity_not_found",
  "message": "Entity camera.test not found"
}

// 400 Bad Request - 時間範圍過長
{
  "error": "invalid_time_range",
  "message": "Time range cannot exceed 30 days"
}

// 500 Internal Server Error - 查詢失敗
{
  "error": "history_query_failed"
}
```

---

### 2. 批量查詢實體歷史

**端點：** `POST /api/smartly/history/batch`

同時查詢多個實體的歷史狀態數據。

#### 請求 Body

```json
{
  "entity_ids": [
    "camera.test",
    "sensor.temperature",
    "light.living_room"
  ],
  "start_time": "2026-01-09T00:00:00Z",
  "end_time": "2026-01-10T00:00:00Z",
  "limit": 500,
  "significant_changes_only": true
}
```

#### 請求參數說明

| 參數 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `entity_ids` | array[string] | ✅ | - | 實體 ID 列表（最多 50 個） |
| `start_time` | string | ❌ | 24小時前 | 開始時間（ISO 8601 格式） |
| `end_time` | string | ❌ | 現在 | 結束時間（ISO 8601 格式） |
| `limit` | integer | ❌ | 1000 | 每個實體返回的最大記錄數 |
| `significant_changes_only` | boolean | ❌ | true | 是否只返回顯著變化 |

#### 限制

- 最多同時查詢 50 個實體
- 時間範圍最長 30 天
- 每個實體最多返回 1000 筆記錄

#### 請求範例

```http
POST /api/smartly/history/batch
Host: localhost:8123
Content-Type: application/json
X-Client-Id: ha_your-client-id
X-Timestamp: 1768018354
X-Nonce: uuid-v4-string
X-Signature: computed-hmac-signature

{
  "entity_ids": ["camera.test", "sensor.temperature"],
  "start_time": "2026-01-09T00:00:00Z",
  "end_time": "2026-01-10T00:00:00Z",
  "limit": 100
}
```

#### 成功響應（200 OK）

```json
{
  "results": {
    "camera.test": {
      "history": [
        {
          "state": "idle",
          "attributes": {...},
          "last_changed": "2026-01-09T10:30:00+00:00",
          "last_updated": "2026-01-09T10:30:00+00:00"
        }
      ],
      "count": 1,
      "truncated": false
    },
    "sensor.temperature": {
      "history": [
        {
          "state": "22.5",
          "attributes": {...},
          "last_changed": "2026-01-09T08:00:00+00:00",
          "last_updated": "2026-01-09T08:00:00+00:00"
        }
      ],
      "count": 1,
      "truncated": false
    }
  },
  "start_time": "2026-01-09T00:00:00+00:00",
  "end_time": "2026-01-10T00:00:00+00:00"
}
```

#### 錯誤響應

```json
// 400 Bad Request - 實體數量過多
{
  "error": "too_many_entities",
  "message": "Cannot query more than 50 entities at once"
}

// 400 Bad Request - entity_ids 不是列表
{
  "error": "invalid_request",
  "message": "entity_ids must be a list"
}
```

---

### 3. 查詢統計數據

**端點：** `POST /api/smartly/history/statistics`

查詢數值型實體的統計數據（平均值、最小值、最大值等）。

#### 請求 Body

```json
{
  "entity_ids": [
    "sensor.temperature",
    "sensor.humidity"
  ],
  "start_time": "2026-01-09T00:00:00Z",
  "end_time": "2026-01-10T00:00:00Z",
  "period": "hour"
}
```

#### 請求參數說明

| 參數 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `entity_ids` | array[string] | ✅ | - | 實體 ID 列表（最多 50 個） |
| `start_time` | string | ❌ | 24小時前 | 開始時間（ISO 8601 格式） |
| `end_time` | string | ❌ | 現在 | 結束時間（ISO 8601 格式） |
| `period` | string | ❌ | hour | 統計週期（`5minute`、`hour`、`day`、`week`、`month`） |

#### 限制

- 最多同時查詢 50 個實體
- 時間範圍最長 30 天
- 僅支援數值型實體（sensor、counter 等）

#### 請求範例

```http
POST /api/smartly/history/statistics
Host: localhost:8123
Content-Type: application/json
X-Client-Id: ha_your-client-id
X-Timestamp: 1768018354
X-Nonce: uuid-v4-string
X-Signature: computed-hmac-signature

{
  "entity_ids": ["sensor.temperature"],
  "start_time": "2026-01-09T00:00:00Z",
  "end_time": "2026-01-10T00:00:00Z",
  "period": "hour"
}
```

#### 成功響應（200 OK）

```json
{
  "results": {
    "sensor.temperature": [
      {
        "start": "2026-01-09T00:00:00+00:00",
        "end": "2026-01-09T01:00:00+00:00",
        "mean": 22.5,
        "min": 21.8,
        "max": 23.2,
        "last_reset": null,
        "state": 22.5,
        "sum": 0
      },
      {
        "start": "2026-01-09T01:00:00+00:00",
        "end": "2026-01-09T02:00:00+00:00",
        "mean": 22.1,
        "min": 21.5,
        "max": 22.7,
        "last_reset": null,
        "state": 22.1,
        "sum": 0
      }
    ]
  },
  "start_time": "2026-01-09T00:00:00+00:00",
  "end_time": "2026-01-10T00:00:00+00:00",
  "period": "hour"
}
```

#### 錯誤響應

```json
// 400 Bad Request - 無效的統計週期
{
  "error": "invalid_period",
  "message": "Period must be one of: 5minute, hour, day, week, month"
}

// 500 Internal Server Error - 統計查詢失敗
{
  "error": "statistics_query_failed"
}
```

---

## 🔧 整合範例

### Python 客戶端

```python
import hashlib
import hmac
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class SmartlyHistoryClient:
    """Smartly Bridge History API 客戶端"""
    
    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
    
    def _calculate_signature(
        self, 
        method: str, 
        path_with_query: str, 
        timestamp: str, 
        nonce: str,
        body: str = ""
    ) -> str:
        """計算 HMAC-SHA256 簽名"""
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        message = f"{method}\n{path_with_query}\n{timestamp}\n{nonce}\n{body_hash}"
        
        signature = hmac.new(
            self.client_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict:
        """發送經過簽名的 HTTP 請求"""
        import uuid
        
        timestamp = str(int(datetime.now().timestamp()))
        nonce = str(uuid.uuid4())
        
        # 構建完整路徑（包含查詢參數）
        path = endpoint
        if params:
            query_string = '&'.join(f"{k}={v}" for k, v in params.items())
            path = f"{path}?{query_string}"
        
        # 計算簽名
        body = ""
        if json_data:
            import json
            body = json.dumps(json_data, separators=(',', ':'))
        
        signature = self._calculate_signature(method, path, timestamp, nonce, body)
        
        # 發送請求
        url = f"{self.base_url}{path}"
        headers = {
            "X-Client-Id": self.client_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
        }
        
        if json_data:
            headers["Content-Type"] = "application/json"
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data
        )
        
        response.raise_for_status()
        return response.json()
    
    def get_entity_history(
        self,
        entity_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
        significant_changes_only: bool = True
    ) -> Dict:
        """查詢單一實體的歷史數據"""
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.now()
        
        params = {
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": str(limit),
            "significant_changes_only": str(significant_changes_only).lower()
        }
        
        return self._make_request(
            "GET",
            f"/api/smartly/history/{entity_id}",
            params=params
        )
    
    def get_batch_history(
        self,
        entity_ids: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
        significant_changes_only: bool = True
    ) -> Dict:
        """批量查詢實體歷史數據"""
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.now()
        
        json_data = {
            "entity_ids": entity_ids,
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": limit,
            "significant_changes_only": significant_changes_only
        }
        
        return self._make_request(
            "POST",
            "/api/smartly/history/batch",
            json_data=json_data
        )
    
    def get_statistics(
        self,
        entity_ids: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        period: str = "hour"
    ) -> Dict:
        """查詢統計數據"""
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.now()
        
        json_data = {
            "entity_ids": entity_ids,
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period": period
        }
        
        return self._make_request(
            "POST",
            "/api/smartly/history/statistics",
            json_data=json_data
        )

# 使用範例
client = SmartlyHistoryClient(
    base_url="http://localhost:8123",
    client_id="ha_your-client-id",
    client_secret="your-client-secret"
)

# 查詢單一實體歷史
history = client.get_entity_history(
    entity_id="camera.test",
    start_time=datetime(2026, 1, 9),
    end_time=datetime(2026, 1, 10),
    limit=100
)
print(f"Found {history['count']} records")

# 批量查詢
batch_result = client.get_batch_history(
    entity_ids=["camera.test", "sensor.temperature"],
    start_time=datetime(2026, 1, 9),
    end_time=datetime(2026, 1, 10)
)

# 查詢統計數據
stats = client.get_statistics(
    entity_ids=["sensor.temperature"],
    start_time=datetime(2026, 1, 9),
    end_time=datetime(2026, 1, 10),
    period="hour"
)
```

---

## ⚠️ 常見問題與注意事項

### 1. 簽名驗證失敗

**問題：** 返回 `{"error": "invalid_signature"}`

**可能原因：**
- 路徑中缺少查詢參數（必須包含完整的 `?start_time=...&limit=...`）
- 時間戳過期（超過 5 分鐘）
- Nonce 重複使用
- 路徑變量（如 `:entity_id`）未正確替換
- 環境變量（如 `{{baseUrl}}`）未展開

**解決方案：**
```javascript
// Postman: 確保從完整 URL 提取路徑
const fullUrl = pm.request.url.toString();
fullUrl = replaceVariables(fullUrl); // 替換所有變量
const urlObj = new URL(fullUrl);
const path = urlObj.pathname + urlObj.search; // 包含查詢參數
```

### 2. 時間範圍錯誤

**問題：** 返回 `{"error": "invalid_time_range"}`

**解決方案：**
- 確保時間範圍不超過 30 天
- 使用正確的 ISO 8601 格式：`2026-01-09T00:00:00Z`
- 確保 `end_time` 大於 `start_time`

### 3. 權限錯誤

**問題：** 返回 `{"error": "forbidden"}`

**解決方案：**
- 確認客戶端配置中 `allowed_entity_ids` 包含該實體
- 檢查 ACL 規則是否允許訪問
- 使用 `/api/smartly/sync/structure` 確認可訪問的實體列表

### 4. 實體不存在

**問題：** 返回 `{"error": "entity_not_found"}`

**解決方案：**
- 檢查 entity_id 拼寫是否正確
- 確認實體在 Home Assistant 中存在
- 使用 `/api/smartly/sync/states` 查看所有可用實體

### 5. 無歷史數據

**問題：** 返回空的 `history` 陣列

**可能原因：**
- Recorder 組件未啟用
- 該實體不在 Recorder 的記錄範圍內
- 查詢的時間範圍內確實沒有狀態變化

**解決方案：**
```yaml
# Home Assistant configuration.yaml
recorder:
  include:
    entities:
      - camera.test
      - sensor.temperature
```

---

## 📊 效能建議

### 1. 合理使用批量查詢

- ✅ 一次查詢多個實體：使用 `/batch` 端點
- ❌ 避免循環調用單一實體 API

### 2. 設置適當的 limit

- 預設 `limit=1000` 可能返回大量數據
- 根據實際需求調整（例如：圖表顯示設為 100）

### 3. 使用 significant_changes_only

- 對於高頻更新的實體（如 sensor），設置 `significant_changes_only=true`
- 可大幅減少返回的數據量

### 4. 縮短查詢時間範圍

- 避免一次查詢 30 天的數據
- 考慮分段查詢或使用統計 API

### 5. 使用統計 API 替代原始數據

- 對於趨勢分析，使用 `/statistics` 端點
- 統計數據已經過聚合，數據量更小

---

## 🔗 相關文檔

- [Sync API 文檔](sync-api.md) - 查詢實體結構和當前狀態
- [Camera API 文檔](camera-api.md) - 攝影機相關功能
- [Control API 文檔](control-examples.md) - 裝置控制功能
- [OpenAPI 規範](openapi.yaml) - 完整的 API 定義
- [安全審計文檔](security-audit.md) - 安全性說明

---

## 📝 更新日誌

### v1.2.0 (2026-01-10)
- ✨ 新增 History API 支援
- 新增單一實體歷史查詢
- 新增批量實體歷史查詢
- 新增統計數據查詢
- 整合 Home Assistant Recorder 組件

---

## 💬 技術支援

如有問題或建議，請聯繫開發團隊或提交 Issue。
