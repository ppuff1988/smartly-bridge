# History API - 設備歷史數據查詢

## 概述

History API 提供查詢 Home Assistant 實體歷史狀態的功能，支援單一實體查詢、批量查詢和統計數據查詢。所有請求都需要通過 HMAC-SHA256 簽名驗證。

**版本：** 1.5.1  
**基礎 URL：** `http://your-home-assistant:8123`

## ✨ 新功能

### v1.5.1
- **修正 cursor 分頁無限循環**：修正過濾邏輯使用嚴格小於比較，避免重複返回相同記錄
- **修正 total_count 準確性**：在第一頁時額外查詢完整時間範圍以計算正確的總記錄數
- **簡化 has_more 判斷**：移除 90% 閾值邏輯，僅當 `len(entity_states) > page_size` 時為 true

### v1.5.0
- **總筆數統計（total_count）**：第一頁查詢時返回查詢範圍內的總記錄數
- **改進分頁判斷**：使用 90% 閾值更保守地判斷是否還有更多資料，避免過早停止（已在 v1.5.1 移除）

### v1.4.0
- **Cursor Pagination**：支援游標分頁，避免資料重複和遺漏
- **自動化分頁**：前端可根據 `has_more` 和 `next_cursor` 自動獲取所有資料

### v1.3.0
- **視覺化元數據**：API 回傳包含視覺化建議（圖表類型、顏色、插值方式）
- **智能數值格式化**：自動根據 device_class 和單位格式化數值精度
- **精簡屬性回傳**：僅首個狀態包含完整屬性，減少資料傳輸量

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
| `limit` | integer | ❌ | 自動 | 返回的最大記錄數（24小時內查詢不限制，超過24小時預設最多1000筆）⚠️ 使用 `cursor` 時無效 |
| `significant_changes_only` | boolean | ❌ | true | 是否只返回顯著變化的狀態 |
| `cursor` | string | ❌ | - | **[v1.4.0]** 分頁游標（Base64 編碼），用於獲取下一頁數據 |
| `page_size` | integer | ❌ | 100 | **[v1.4.0]** 每頁返回的記錄數（僅在使用 `cursor` 時有效，範圍：1-1000） |

#### 限制

- 時間範圍最長 30 天
- **24 小時內查詢（不使用 cursor）：** 回傳所有記錄，不限制筆數，確保時間軸完整
- **超過 24 小時查詢（不使用 cursor）：** 單次查詢最多返回 1000 筆記錄
- **使用 cursor 分頁：** 每頁最多返回 `page_size` 筆（預設 100，最大 1000）
- 僅能查詢有權限的實體

#### 分頁查詢說明（v1.4.0 新增）

當查詢大量歷史數據時，可使用 cursor-based pagination 來分批獲取數據：

1. **首次請求**：不提供 `cursor` 參數
2. **後續請求**：使用上一次回應中的 `next_cursor` 作為 `cursor` 參數
3. **結束條件**：當回應的 `has_more` 為 `false` 時，表示已經取得所有數據

**注意事項：**
- 使用 cursor 時，`limit` 參數將被忽略
- 使用 cursor 時，不會進行時間邊界填補（`_ensure_time_bounds`）
- cursor 包含加密的時間戳和狀態變更時間，不可手動構造
- cursor 有時效性，建議在合理時間內完成分頁查詢

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
  "entity_id": "sensor.micro_wake_word_pzem_004t_v3_current",
  "history": [
    {
      "state": 0.0,
      "attributes": {
        "device_class": "current",
        "friendly_name": "小燈電流",
        "state_class": "measurement",
        "unit_of_measurement": "mA"
      },
      "last_changed": "2026-01-09T05:25:48Z",
      "last_updated": "2026-01-09T05:25:48Z"
    },
    {
      "state": "unavailable",
      "last_changed": "2026-01-09T09:46:03.070703Z",
      "last_updated": "2026-01-09T09:46:03.070703Z"
    },
    {
      "state": 0.0,
      "last_changed": "2026-01-09T09:46:03.269271Z",
      "last_updated": "2026-01-09T09:46:03.269271Z"
    },
    {
      "state": 34.0,
      "last_changed": "2026-01-09T22:33:52.909742Z",
      "last_updated": "2026-01-09T22:33:52.909742Z"
    },
    {
      "state": 21.0,
      "last_changed": "2026-01-09T22:34:59.00267Z",
      "last_updated": "2026-01-09T22:34:59.00267Z"
    },
    {
      "state": 35.0,
      "last_changed": "2026-01-09T22:35:17.002829Z",
      "last_updated": "2026-01-09T22:35:17.002829Z"
    }
  ],
  "count": 6,
  "truncated": false,
  "start_time": "2026-01-09T05:25:48Z",
  "end_time": "2026-01-10T05:25:48Z",
  "metadata": {
    "domain": "sensor",
    "device_class": "current",
    "unit_of_measurement": "mA",
    "friendly_name": "小燈電流",
    "is_numeric": true,
    "decimal_places": 1,
    "visualization": {
      "type": "chart",
      "chart_type": "line",
      "color": "#FFA726",
      "show_points": true,
      "interpolation": "linear"
    }
  }
}
```

#### 響應欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `entity_id` | string | 實體 ID |
| `history` | array | 歷史狀態陣列 |
| `history[].state` | string/number | 狀態值（數值型會自動格式化精度） |
| `history[].attributes` | object | 屬性（僅首筆包含，後續省略以減少資料量） |
| `history[].last_changed` | string | 狀態變更時間（ISO 8601） |
| `history[].last_updated` | string | 最後更新時間（ISO 8601） |
| `count` | integer | 返回的記錄數 |
| `truncated` | boolean | 是否因超過 limit 而截斷（僅在非 cursor 模式） |
| `start_time` | string | 查詢開始時間 |
| `end_time` | string | 查詢結束時間 |
| `metadata` | object | **[v1.3.0]** 實體元數據與視覺化建議 |
| `device_class` | string | 符合 Bridge chart 規則的感測器設備類別，有值時回傳 |
| `unit_of_measurement` | string | 符合 Bridge chart 規則的感測器測量單位，有值時回傳 |
| `bridge_chart` | object | 符合 Bridge chart 規則的感測器簡化圖表資料 |
| `page_size` | integer | **[v1.4.0]** 每頁記錄數（僅在 cursor 模式） |
| `has_more` | boolean | **[v1.4.0]** 是否還有更多數據（僅在 cursor 模式） |
| `next_cursor` | string | **[v1.4.0]** 下一頁游標（僅在 `has_more=true` 時返回） |
| `total_count` | integer | **[v1.5.0]** 查詢範圍內的總記錄數（僅在第一頁返回） |

#### Bridge chart 判斷規則

`bridge_chart` 是否回傳由 `device_class` 和歷史狀態值決定，不根據 `entity_id`、`friendly_name` 或單位文字猜測。

回傳條件：

1. metadata 中有 `device_class`。
2. `device_class` 在 Bridge chart allowlist：`temperature`、`humidity`、`carbon_dioxide`、`co2`、`carbon_monoxide`、`aqi`、`pm25`、`pm10`、`illuminance`、`pressure`、`atmospheric_pressure`。
3. 歷史狀態值可轉成數字，且該筆資料有 `last_changed` 或 `last_updated` 時間戳。

不符合條件時省略 `bridge_chart`。符合條件但部分歷史點不是數字時，只略過那些點；若沒有任何可用點，則省略整個 `bridge_chart`。

#### 元數據（metadata）欄位說明

`metadata` 物件提供前端呈現時所需的完整資訊：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `domain` | string | 實體域（sensor, switch, light 等） |
| `device_class` | string | 設備類別（current, voltage, temperature 等） |
| `unit_of_measurement` | string | 測量單位（mA, V, °C 等） |
| `friendly_name` | string | 友善名稱 |
| `is_numeric` | boolean | 是否為數值型數據 |
| `decimal_places` | integer | 建議的小數位數 |
| `visualization` | object | 視覺化配置 |

#### 視覺化配置（visualization）

根據 `device_class` 或 `domain`，API 會提供最佳的視覺化建議：

**圖表類型（chart）** - 適用於連續數值數據：
```json
{
  "type": "chart",
  "chart_type": "line",       // line, area, spline
  "color": "#FFA726",          // 建議顏色（Hex）
  "show_points": true,         // 是否顯示數據點
  "interpolation": "linear"    // 插值方式：linear, monotone, natural, step-after
}
```

**時間軸（timeline）** - 適用於開關狀態：
```json
{
  "type": "timeline",
  "on_color": "#66BB6A",       // 開啟狀態顏色
  "off_color": "#BDBDBD"       // 關閉狀態顏色
}
```

**儀表板（gauge）** - 適用於範圍數值：
```json
{
  "type": "gauge",
  "min": 0,                    // 最小值
  "max": 1,                    // 最大值
  "color": "#7E57C2"           // 顏色
}
```

**柱狀圖（bar）** - 適用於累積數據：
```json
{
  "type": "bar",
  "chart_type": "bar",
  "color": "#AB47BC"
}
```

#### 視覺化配置對照表

| device_class | 建議類型 | 圖表類型 | 顏色 | 說明 |
|-------------|---------|---------|------|------|
| `current` | chart | line | #FFA726（橘） | 電流折線圖 |
| `voltage` | chart | line | #42A5F5（藍） | 電壓折線圖 |
| `power` | chart | area | #66BB6A（綠） | 功率面積圖 |
| `energy` | bar | bar | #AB47BC（紫） | 能量柱狀圖 |
| `temperature` | chart | spline | #EF5350（紅） | 溫度曲線圖 |
| `humidity` | chart | area | #26C6DA（青） | 濕度面積圖 |
| `battery` | chart | line | #9CCC65（淺綠） | 電池折線圖 |
| `illuminance` | chart | area | #FFEE58（黃） | 照度面積圖 |
| `pressure` | chart | line | #8D6E63（棕） | 氣壓折線圖 |
| `carbon_dioxide` / `co2` | chart | area | #78909C（灰藍） | CO2 面積圖 |
| `pm25` | chart | area | #FF7043（深橘） | PM2.5 面積圖 |
| `pm10` | chart | area | #BF360C（深紅橘） | PM10 面積圖 |
| `power_factor` | gauge | - | #7E57C2（深紫） | 功率因數儀表 |
| `frequency` | chart | line | #5C6BC0（靛藍） | 頻率折線圖 |

| domain | 建議類型 | on_color | off_color | 說明 |
|--------|---------|----------|-----------|------|
| `switch` | timeline | #66BB6A（綠） | #BDBDBD（灰） | 開關時間軸 |
| `light` | timeline | #FFEB3B（黃） | #757575（深灰） | 燈光時間軸 |
| `binary_sensor` | timeline | #EF5350（紅） | #E0E0E0（淺灰） | 二元感測器 |
| `lock` | timeline | #F44336（紅） | #4CAF50（綠） | 鎖狀態 |
| `cover` | chart | - | - | 窗簾位置 |

#### 數值精度配置

根據 `device_class` 和 `unit_of_measurement` 自動格式化：

| device_class | 單位 | 小數位數 | 範例 |
|-------------|------|---------|------|
| `current` | mA | 1 | 456.5 mA |
| `current` | A | 3 | 0.456 A |
| `voltage` | V | 2 | 220.12 V |
| `power` | W | 2 | 100.99 W |
| `power` | kW | 3 | 1.234 kW |
| `energy` | kWh | 3 | 1.234 kWh |
| `temperature` | °C/°F | 1 | 25.5 °C |
| `humidity` | % | 1 | 65.5 % |
| `battery` | % | 0 | 85 % |

#### Cursor Pagination 使用範例（v1.4.0）

**場景：** 查詢過去 7 天的溫度數據，每次獲取 50 筆記錄

**第一次請求：**
```http
GET /api/smartly/history/sensor.temperature?start_time=2026-01-03T00:00:00Z&end_time=2026-01-10T00:00:00Z&page_size=50
Host: localhost:8123
X-Client-Id: ha_your-client-id
X-Timestamp: 1768018354
X-Nonce: uuid-v4-string-1
X-Signature: computed-hmac-signature-1
```

**第一次響應：**
```json
{
  "entity_id": "sensor.temperature",
  "history": [
    {
      "state": 22.5,
      "attributes": {
        "device_class": "temperature",
        "unit_of_measurement": "°C"
      },
      "last_changed": "2026-01-03T00:00:00Z",
      "last_updated": "2026-01-03T00:00:00Z"
    },
    // ... 49 more records
  ],
  "count": 50,
  "page_size": 50,
  "has_more": true,
  "total_count": 387,
  "next_cursor": "eyJ0cyI6IjIwMjYtMDEtMDNUMDI6MzA6MDBaIiwibGMiOiIyMDI2LTAxLTAzVDAyOjMwOjAwWiJ9",
  "start_time": "2026-01-03T00:00:00Z",
  "end_time": "2026-01-10T00:00:00Z",
  "metadata": { ... },
  "device_class": "temperature",
  "unit_of_measurement": "°C",
  "bridge_chart": {
    "metric": "temperature",
    "unit": "°C",
    "points": [
      { "at": "2026-01-03T00:00:00Z", "value": 22.5 }
    ]
  }
}
```

**第二次請求（使用 cursor）：**
```http
GET /api/smartly/history/sensor.temperature?start_time=2026-01-03T00:00:00Z&end_time=2026-01-10T00:00:00Z&page_size=50&cursor=eyJ0cyI6IjIwMjYtMDEtMDNUMDI6MzA6MDBaIiwibGMiOiIyMDI2LTAxLTAzVDAyOjMwOjAwWiJ9
Host: localhost:8123
X-Client-Id: ha_your-client-id
X-Timestamp: 1768018360
X-Nonce: uuid-v4-string-2
X-Signature: computed-hmac-signature-2
```

**第二次響應：**
```json
{
  "entity_id": "sensor.temperature",
  "history": [
    {
      "state": 23.1,
      "attributes": { ... },
      "last_changed": "2026-01-03T02:30:01Z",
      "last_updated": "2026-01-03T02:30:01Z"
    },
    // ... 49 more records
  ],
  "count": 50,
  "page_size": 50,
  "has_more": true,
  "next_cursor": "eyJ0cyI6IjIwMjYtMDEtMDNUMDU6MDA6MDBaIiwibGMiOiIyMDI2LTAxLTAzVDA1OjAwOjAwWiJ9",
  "start_time": "2026-01-03T02:30:00Z",
  "end_time": "2026-01-10T00:00:00Z",
  "metadata": { ... }
}
```

**最後一次響應（has_more = false）：**
```json
{
  "entity_id": "sensor.temperature",
  "history": [
    {
      "state": 21.8,
      "attributes": { ... },
      "last_changed": "2026-01-09T22:30:00Z",
      "last_updated": "2026-01-09T22:30:00Z"
    },
    // ... 25 records (less than page_size)
  ],
  "count": 25,
  "page_size": 50,
  "has_more": false,
  "start_time": "2026-01-09T20:00:00Z",
  "end_time": "2026-01-10T00:00:00Z",
  "metadata": { ... }
}
```

**Python 範例（完整分頁查詢）：**
```python
import requests
from datetime import datetime, timedelta
from typing import List, Dict

def fetch_all_history(
    base_url: str,
    entity_id: str,
    start_time: datetime,
    end_time: datetime,
    auth_headers: Dict[str, str],
    page_size: int = 100
) -> List[Dict]:
    """使用 cursor pagination 獲取所有歷史數據"""
    all_history = []
    cursor = None
    total_count = None
    
    while True:
        # 構建請求參數
        params = {
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "page_size": page_size
        }
        if cursor:
            params["cursor"] = cursor
        
        # 發送請求
        response = requests.get(
            f"{base_url}/api/smartly/history/{entity_id}",
            params=params,
            headers=auth_headers
        )
        response.raise_for_status()
        
        data = response.json()
        all_history.extend(data["history"])
        
        # 第一頁會返回 total_count
        if total_count is None and "total_count" in data:
            total_count = data["total_count"]
            print(f"查詢範圍內共有 {total_count} 筆記錄")
        
        # 顯示進度
        if total_count:
            progress = len(all_history) / total_count * 100
            print(f"進度: {len(all_history)}/{total_count} ({progress:.1f}%)")
        
        # 檢查是否還有更多數據
        if not data.get("has_more", False):
            break
        
        cursor = data.get("next_cursor")
        if not cursor:
            break
    
    return all_history

# 使用範例
base_url = "http://localhost:8123"
entity_id = "sensor.temperature"
start_time = datetime.now() - timedelta(days=7)
end_time = datetime.now()

# 注意：實際使用時需要計算 HMAC 簽名
auth_headers = {
    "X-Client-Id": "your-client-id",
    "X-Timestamp": str(int(datetime.now().timestamp())),
    "X-Nonce": "unique-nonce",
    "X-Signature": "computed-hmac-signature"
}

history = fetch_all_history(base_url, entity_id, start_time, end_time, auth_headers)
print(f"Total records: {len(history)}")
```

#### 錯誤響應

```json
// 401 Unauthorized - 簽名驗證失敗
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "INVALID_SIGNATURE",
      "message": "invalid signature",
      "target": "history.auth",
      "retryable": false
    }
  ]
}

// 403 Forbidden - 無權限訪問該實體
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "ENTITY_NOT_ALLOWED",
      "message": "entity not allowed",
      "target": "history.entity_id",
      "retryable": false
    }
  ]
}

// 400 Bad Request - 時間範圍過長
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "TIME_RANGE_TOO_LARGE",
      "message": "time range too large",
      "target": "history.time_range",
      "retryable": false
    }
  ]
}

// 400 Bad Request - 無效的游標
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "INVALID_CURSOR",
      "message": "invalid cursor",
      "target": "history.cursor",
      "retryable": false
    }
  ]
}

// 500 Internal Server Error - 查詢失敗
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "HISTORY_QUERY_FAILED",
      "message": "history query failed",
      "target": "history",
      "retryable": false
    }
  ]
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
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "TOO_MANY_ENTITIES",
      "message": "too many entities",
      "target": "history.batch.entity_ids",
      "retryable": false
    }
  ]
}

// 400 Bad Request - entity_ids 不是列表
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "ENTITY_IDS_REQUIRED",
      "message": "entity ids required",
      "target": "history.batch.entity_ids",
      "retryable": false
    }
  ]
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
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "INVALID_PERIOD",
      "message": "invalid period",
      "target": "history.statistics.period",
      "retryable": false
    }
  ]
}

// 500 Internal Server Error - 統計查詢失敗
{
  "schema_version": "2026.06",
  "data": {
    "status": "rejected"
  },
  "warnings": [],
  "errors": [
    {
      "code": "STATISTICS_QUERY_FAILED",
      "message": "statistics query failed",
      "target": "history.statistics",
      "retryable": false
    }
  ]
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
result = client.get_history("sensor.temperature")
print(f"Retrieved {result['count']} records")

# 使用元數據渲染圖表
metadata = result.get('metadata', {})
viz_config = metadata.get('visualization', {})

if viz_config.get('type') == 'chart':
    print(f"建議使用 {viz_config['chart_type']} 圖表")
    print(f"顏色：{viz_config['color']}")
    print(f"插值方式：{viz_config['interpolation']}")

# 批量查詢
batch_result = client.get_batch_history([
    "sensor.temperature",
    "sensor.humidity"
])
```

---

## 🎨 前端實作建議

### 使用 Chart.js 渲染歷史數據

```javascript
// 獲取歷史數據
const response = await fetch('/api/smartly/history/sensor.temperature', {
    headers: {
        'X-Client-Id': clientId,
        'X-Timestamp': timestamp,
        'X-Nonce': nonce,
        'X-Signature': signature
    }
});

const data = await response.json();
const { history, metadata } = data;

// 根據 metadata 配置圖表
const vizConfig = metadata.visualization;

const chartData = {
    labels: history.map(h => new Date(h.last_changed)),
    datasets: [{
        label: metadata.friendly_name,
        data: history.map(h => h.state),
        borderColor: vizConfig.color,
        backgroundColor: vizConfig.chart_type === 'area' 
            ? vizConfig.color + '40'  // 添加透明度
            : vizConfig.color,
        fill: vizConfig.chart_type === 'area',
        pointRadius: vizConfig.show_points ? 3 : 0,
        tension: vizConfig.interpolation === 'natural' ? 0.4 :
                 vizConfig.interpolation === 'monotone' ? 0.3 : 0,
        stepped: vizConfig.interpolation === 'step-after' ? 'after' : false
    }]
};

const chartConfig = {
    type: vizConfig.chart_type === 'spline' ? 'line' : vizConfig.chart_type,
    data: chartData,
    options: {
        responsive: true,
        scales: {
            y: {
                title: {
                    display: true,
                    text: metadata.unit_of_measurement
                }
            }
        }
    }
};

new Chart(ctx, chartConfig);
```

### 使用 ECharts 渲染時間軸（開關狀態）

```javascript
const response = await fetch('/api/smartly/history/switch.living_room', {
    headers: { /* ... */ }
});

const data = await response.json();
const { history, metadata } = data;
const vizConfig = metadata.visualization;

// 將狀態轉換為時間段
const timeRanges = history.map((h, i) => {
    const nextTime = history[i + 1]?.last_changed || data.end_time;
    return {
        name: h.state === 'on' ? '開啟' : '關閉',
        value: [
            new Date(h.last_changed),
            new Date(nextTime),
            h.state === 'on' ? 1 : 0
        ],
        itemStyle: {
            color: h.state === 'on' ? vizConfig.on_color : vizConfig.off_color
        }
    };
});

const option = {
    tooltip: {
        formatter: function(params) {
            const duration = (params.value[1] - params.value[0]) / 1000;
            return `${params.name}<br/>持續時間：${duration.toFixed(0)} 秒`;
        }
    },
    xAxis: {
        type: 'time',
        min: new Date(data.start_time),
        max: new Date(data.end_time)
    },
    yAxis: {
        type: 'value',
        max: 1,
        splitLine: { show: false }
    },
    series: [{
        type: 'custom',
        renderItem: function(params, api) {
            const start = api.coord([api.value(0), 0]);
            const end = api.coord([api.value(1), 1]);
            const height = api.size([0, 1])[1];
            
            return {
                type: 'rect',
                shape: {
                    x: start[0],
                    y: start[1],
                    width: end[0] - start[0],
                    height: height
                },
                style: api.style()
            };
        },
        data: timeRanges
    }]
};

chart.setOption(option);
```

### React 組件範例

```jsx
import React, { useEffect, useState } from 'react';
import { Line, Bar } from 'react-chartjs-2';

function HistoryChart({ entityId, startTime, endTime }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchHistory() {
            const response = await fetch(
                `/api/smartly/history/${entityId}?start_time=${startTime}&end_time=${endTime}`,
                { headers: { /* authentication headers */ } }
            );
            const result = await response.json();
            setData(result);
            setLoading(false);
        }
        fetchHistory();
    }, [entityId, startTime, endTime]);

    if (loading) return <div>載入中...</div>;
    if (!data) return <div>無數據</div>;

    const { history, metadata } = data;
    const vizConfig = metadata.visualization;

    const chartData = {
        labels: history.map(h => new Date(h.last_changed)),
        datasets: [{
            label: metadata.friendly_name,
            data: history.map(h => h.state),
            borderColor: vizConfig.color,
            backgroundColor: vizConfig.chart_type === 'area' 
                ? `${vizConfig.color}40` 
                : vizConfig.color,
            fill: vizConfig.chart_type === 'area',
        }]
    };

    const ChartComponent = vizConfig.type === 'bar' ? Bar : Line;

    return (
        <div>
            <h3>{metadata.friendly_name}</h3>
            <ChartComponent data={chartData} />
            <p>共 {data.count} 筆記錄</p>
        </div>
    );
}

export default HistoryChart;
```

---

## 📊 最佳實作建議

### 1. 性能優化

- **使用 `significant_changes_only=true`**：減少不必要的數據點
- **合理設置 `limit`**：避免一次性獲取過多數據
- **批量查詢**：需要多個實體數據時使用 batch API
- **前端緩存**：對於不常變化的歷史數據進行緩存

### 2. 視覺化建議

- **自動應用 metadata 配置**：直接使用 API 提供的顏色和圖表類型
- **響應式設計**：根據螢幕大小調整數據點密度
- **時間軸適配**：開關類設備使用時間軸而非折線圖
- **數值格式化**：使用 `metadata.decimal_places` 顯示適當精度

### 3. 錯誤處理

```javascript
async function fetchHistoryWithRetry(entityId, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const response = await fetch(`/api/smartly/history/${entityId}`);
            if (response.status === 429) {
                // Rate limited - 等待後重試
                const retryAfter = response.headers.get('Retry-After') || 60;
                await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
                continue;
            }
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            if (i === retries - 1) throw error;
        }
    }
}
```

---

## 🔄 版本更新記錄

### v1.3.0 (2026-01-10)

**新增功能：**
- ✨ 新增 `metadata` 欄位，包含視覺化建議和精度配置
- ✨ 智能數值格式化，自動根據 device_class 和 unit 調整精度
- ✨ 優化屬性回傳，僅首筆包含完整 attributes 減少傳輸量

**改進：**
- 🎨 提供 15+ 種 device_class 的預設視覺化配置
- 🎨 支援 5 種 domain 的時間軸配置
- 📊 狀態值自動轉換為數值型態（適用於圖表渲染）

**範例：**
- 電流從 `"34.000001847744"` 格式化為 `34.0` (mA 單位保留 1 位小數)
- 自動建議使用橘色 (#FFA726) 折線圖呈現電流數據

### v1.2.0 (2026-01-08)
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

**問題：** 回應 `errors[0].code` 為 `INVALID_SIGNATURE`

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

**問題：** 回應 `errors[0].code` 為 `TIME_RANGE_TOO_LARGE`

**解決方案：**
- 確保時間範圍不超過 30 天
- 使用正確的 ISO 8601 格式：`2026-01-09T00:00:00Z`
- 確保 `end_time` 大於 `start_time`

### 3. 權限錯誤

**問題：** 回應 `errors[0].code` 為 `ENTITY_NOT_ALLOWED`

**解決方案：**
- 確認客戶端配置中 `allowed_entity_ids` 包含該實體
- 檢查 ACL 規則是否允許訪問
- 使用 `/api/smartly/sync/structure` 確認可訪問的實體列表

### 4. 無歷史數據

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
