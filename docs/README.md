# Smartly Bridge API 文件

本目錄包含 Smartly Bridge 的完整 API 文件，採用 OpenAPI 3.1.0 規範。

## 📁 文件說明

### `openapi.yaml`
完整的 OpenAPI 3.1.0 規範文件，可用於：
- 生成客戶端 SDK
- API 測試工具（Postman、Insomnia）
- 自動化測試
- 程式碼生成

### `api-docs.html`
使用 [Scalar](https://github.com/scalar/scalar) 渲染的互動式 API 文件介面。

**特色：**
- 🎨 現代化、美觀的介面
- 🔍 即時搜尋功能
- 📝 互動式 API 測試
- 🌙 支援深色模式
- 🌐 支援繁體中文顯示
- 📱 響應式設計，支援行動裝置

### `sync-api.md`
詳細的 Sync API 說明文件，包含：
- `/api/smartly/sync/structure` - 取得結構層級
- `/api/smartly/sync/states` - 取得實體狀態
- Icon 資訊的使用方式和建議
- 安全性說明和範例程式碼

### `history-api.md` ⭐ NEW
詳細的 History API 說明文件，包含：
- `/api/smartly/history/{entity_id}` - 單一實體歷史查詢
- `/api/smartly/history/batch` - 批量實體歷史查詢
- `/api/smartly/history/statistics` - 統計數據查詢
- HMAC 簽名計算詳細說明
- Python 客戶端完整範例
- Postman Pre-request Script
- 常見問題與故障排除

### `camera-api.md`
詳細的 Camera API 說明文件，包含快照、串流和 HLS 支援。

### `control-examples.md`
詳細的裝置控制範例文件。

## 🚀 使用方式

### 方法一：本地伺服器（推薦）

1. 在 `docs/` 目錄啟動簡單的 HTTP 伺服器：

```bash
# Python 3
cd /workspace/docs
python3 -m http.server 8000

# 或使用 Python 2
python -m SimpleHTTPServer 8000
```

2. 在瀏覽器開啟：
   - Scalar 文件：http://localhost:8000/api-docs.html
   - 原始 OpenAPI YAML：http://localhost:8000/openapi.yaml

### 方法二：直接開啟（可能有 CORS 限制）

在某些瀏覽器中，可以直接開啟 `api-docs.html` 文件：

```bash
# macOS
open docs/api-docs.html

# Linux
xdg-open docs/api-docs.html

# Windows
start docs/api-docs.html
```

> ⚠️ **注意**：直接開啟可能因 CORS 政策無法載入 `openapi.yaml`，建議使用方法一。

### 方法三：使用 VS Code Live Server

1. 安裝 VS Code 擴充套件：[Live Server](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer)
2. 在 VS Code 中右鍵點擊 `api-docs.html`
3. 選擇「Open with Live Server」

### 方法四：使用 Docker（如果在容器中開發）

```bash
# 在工作區根目錄
docker run -d -p 8080:80 -v $(pwd)/docs:/usr/share/nginx/html:ro nginx:alpine
```

然後開啟 http://localhost:8080/api-docs.html

## 🎨 自訂 Scalar 主題

編輯 `api-docs.html` 中的 `configuration` 物件來自訂顯示：

```javascript
var configuration = {
  theme: 'purple',  // 可選: 'default', 'alternate', 'moon', 'purple', 'solarized'
  darkMode: false,  // 預設深色模式
  layout: 'modern', // 可選: 'modern', 'classic'
  // ... 更多選項
};
```

### 可用主題
- `default` - 預設淺色主題
- `alternate` - 替代淺色主題
- `moon` - 月光主題
- `purple` - 紫色主題（當前使用）
- `solarized` - Solarized 主題

## 🛠️ OpenAPI 工具整合

### 生成客戶端 SDK

```bash
# 使用 openapi-generator
npx @openapitools/openapi-generator-cli generate \
  -i docs/openapi.yaml \
  -g python \
  -o ./client-sdk

# 使用 swagger-codegen
docker run --rm -v ${PWD}:/local swaggerapi/swagger-codegen-cli generate \
  -i /local/docs/openapi.yaml \
  -l python \
  -o /local/client-sdk
```

### 驗證 OpenAPI 規範

```bash
# 使用 Spectral 驗證
npm install -g @stoplight/spectral-cli
spectral lint docs/openapi.yaml

# 使用 openapi-spec-validator
pip install openapi-spec-validator
openapi-spec-validator docs/openapi.yaml
```

### 匯入到 Postman

**方式一：匯入 OpenAPI 文件**

1. 開啟 Postman
2. Import → File → 選擇 `openapi.yaml`
3. Postman 會自動建立完整的 API 集合

**方式二：匯入 Postman Collection（推薦）**

1. 開啟 Postman
2. Import → File → 選擇 `postman-collection.json`
3. 已包含預設範例和說明

**設定環境變數：**
```
base_url: http://localhost:8123
client_id: ha_abc123def456
client_secret: your_client_secret_here
```

**請求 Body 格式說明：**

所有 POST 請求都必須使用 JSON 格式。以 `/api/smartly/control` 為例：

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

- `command_id` (必填): 命令追蹤 ID
- `device_id` (必填): Sync API 回傳的邏輯設備 ID
- `capability` (必填): canonical capability，例如 `brightness`
- `command` (必填): capability 支援的 command，例如 `set_brightness`
- `params` (選填): command 參數，依 capability contract 而定
- `source` (選填): 操作者資訊，用於審計日誌

**必要的 HTTP Headers：**
```
Content-Type: application/json
X-Client-Id: ha_abc123def456
X-Timestamp: 1735228800
X-Nonce: 550e8400-e29b-41d4-a716-446655440000
X-Signature: [HMAC-SHA256 簽章]
```

### 匯入到 Insomnia

1. 開啟 Insomnia
2. Create → Import from File → 選擇 `openapi.yaml`
3. 選擇匯入為 Request Collection

## 📋 API 概覽

### 核心端點

| 端點 | 方法 | 說明 | 文檔 |
|-----|------|------|------|
| `/api/smartly/control` | POST | 控制裝置 | [control-examples.md](control-examples.md) |
| `/api/smartly/sync/structure` | GET | 取得結構層級 | [sync-api.md](sync-api.md) |
| `/api/smartly/sync/states` | GET | 取得所有實體狀態 | [sync-api.md](sync-api.md) |
| `/api/smartly/history/{entity_id}` | GET | 單一實體歷史查詢 | [history-api.md](history-api.md) |
| `/api/smartly/history/batch` | POST | 批量實體歷史查詢 | [history-api.md](history-api.md) |
| `/api/smartly/history/statistics` | POST | 統計數據查詢 | [history-api.md](history-api.md) |
| `/api/smartly/camera/{entity_id}/snapshot` | GET | 攝影機快照 | [camera-api.md](camera-api.md) |
| `/api/smartly/camera/{entity_id}/stream` | GET | MJPEG 串流 | [camera-api.md](camera-api.md) |

### Webhooks

| Webhook | 說明 |
|---------|------|
| `stateChanged` | 狀態變更通知（批次傳送，500ms 間隔）|
| `heartbeat` | 心跳通知（60 秒間隔）|

### 安全性

所有請求必須使用 HMAC-SHA256 簽章驗證，需包含以下標頭：
- `X-Client-Id`: 客戶端識別碼
- `X-Timestamp`: Unix 時間戳記
- `X-Nonce`: UUID v4（5 分鐘內不可重複使用）
- `X-Signature`: HMAC-SHA256 簽章

## 🔗 相關連結

- [OpenAPI 3.1 規範](https://spec.openapis.org/oas/v3.1.0)
- [Scalar 文件](https://github.com/scalar/scalar)
- [Home Assistant 開發者文件](https://developers.home-assistant.io/)
- [Smartly Bridge GitHub](https://github.com/ppuff1988/smartly-bridge)

## 📝 更新文件

當 API 有變更時，請更新 `openapi.yaml` 並確保：

1. ✅ 版本號已更新
2. ✅ 新端點已記錄
3. ✅ 範例已更新
4. ✅ 錯誤回應已記錄
5. ✅ 通過 OpenAPI 驗證

```bash
# 驗證變更
spectral lint docs/openapi.yaml

# 測試 Scalar 渲染
python3 -m http.server 8000
# 然後開啟 http://localhost:8000/api-docs.html
```

## 🐛 疑難排解

### CORS 錯誤
如果看到 CORS 錯誤，請使用本地 HTTP 伺服器而非直接開啟 HTML 檔案。

### 樣式未載入
確保網路連線正常，Scalar 從 CDN 載入。如需離線使用，請參考 [Scalar 自託管文件](https://github.com/scalar/scalar#self-hosting)。

### OpenAPI YAML 未載入
確保 `openapi.yaml` 和 `api-docs.html` 在同一目錄下。

## 📄 授權

本專案採用 MIT 授權 - 詳見 [LICENSE](../LICENSE) 檔案。
