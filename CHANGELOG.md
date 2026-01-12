# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.10.7](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.6...v1.10.7) (2026-01-12)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正反序排序時游標分頁失效問題 ([#52](https://github.com/ppuff1988/smartly-bridge/issues/52)) ([7d2328c](https://github.com/ppuff1988/smartly-bridge/commit/7d2328cbcb794aada0d29ba4b9022635e592deb7))

## [1.10.6](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.5...v1.10.6) (2026-01-12)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正歷史資料排序順序為從新到舊 ([#51](https://github.com/ppuff1988/smartly-bridge/issues/51)) ([e77ee8b](https://github.com/ppuff1988/smartly-bridge/commit/e77ee8b13b80a01298b68065806904f7cd6d94ed))

## [1.10.5](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.4...v1.10.5) (2026-01-12)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正數值格式化與 cursor 分頁問題 ([#50](https://github.com/ppuff1988/smartly-bridge/issues/50)) ([8c2bcc4](https://github.com/ppuff1988/smartly-bridge/commit/8c2bcc406349d2950f14393b12a501eb87029820))

## [1.10.4](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.3...v1.10.4) (2026-01-11)

### 🐛 錯誤修正 (Bug Fixes)

* **sync:** 修正 sensor state 未套用小數點格式化問題 ([#49](https://github.com/ppuff1988/smartly-bridge/issues/49)) ([4e29dcd](https://github.com/ppuff1988/smartly-bridge/commit/4e29dcd96fc1fa8b556075c9b889d849da6515ff))

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🐛 錯誤修正 (Bug Fixes)

* **sync:** 修正 sensor state 未套用小數點格式化問題
  - 新增 `format_sensor_state` 函數統一處理 sensor state 數值格式化
  - sync API 和 webhook 推送現在都會根據 device_class 和 unit 正確格式化 sensor 數值
  - 例如：電壓顯示 2 位小數 (115.7V)、電流毫安培顯示 1 位小數 (35.0mA)、溫度顯示 1 位小數 (25.6°C)

## [1.10.3](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.2...v1.10.3) (2026-01-11)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正 cursor pagination 連續分頁邏輯錯誤 ([#48](https://github.com/ppuff1988/smartly-bridge/issues/48)) ([f1f584c](https://github.com/ppuff1988/smartly-bridge/commit/f1f584c6d5382f50c070ec7129e526be4dd9f095))

## [1.10.2](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.1...v1.10.2) (2026-01-11)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 新增 cursor-based pagination 支援 ([#47](https://github.com/ppuff1988/smartly-bridge/issues/47)) ([1709633](https://github.com/ppuff1988/smartly-bridge/commit/17096334881e4e0d00d317542d3987e1e1bd54e3))
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.10.1](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.0...v1.10.1) (2026-01-10)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正 24 小時歷史數據時間軸顯示問題 ([#46](https://github.com/ppuff1988/smartly-bridge/issues/46)) ([a33c40d](https://github.com/ppuff1988/smartly-bridge/commit/a33c40db1dcdb910962ba258620240127a117f3c))

## [1.10.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.9.1...v1.10.0) (2026-01-10)

### ✨ 新增功能 (Features)

* **history:** History API 視覺化增強 (v1.3.0) ([#45](https://github.com/ppuff1988/smartly-bridge/issues/45)) ([a687597](https://github.com/ppuff1988/smartly-bridge/commit/a687597d938a84f1e200ad671ec15f40b5ead3f7))

## [1.9.1](https://github.com/ppuff1988/smartly-bridge/compare/v1.9.0...v1.9.1) (2026-01-10)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正資料庫存取未使用 executor 的警告 ([#44](https://github.com/ppuff1988/smartly-bridge/issues/44)) ([a3007bb](https://github.com/ppuff1988/smartly-bridge/commit/a3007bbb239c103ab1556905437748f8174e9a6a))

## [1.9.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.8.1...v1.9.0) (2026-01-10)

### ✨ 新增功能 (Features)

* **history:** 新增 History API 完整功能 ([#43](https://github.com/ppuff1988/smartly-bridge/issues/43)) ([a065abb](https://github.com/ppuff1988/smartly-bridge/commit/a065abb114e14755ebac2f50795bfc0f3e636554)), closes [#41](https://github.com/ppuff1988/smartly-bridge/issues/41)

## [1.8.1](https://github.com/ppuff1988/smartly-bridge/compare/v1.8.0...v1.8.1) (2026-01-10)

### ♻️ 程式碼重構 (Refactoring)

* **const:** 改善預設 domain 圖標選擇 ([#39](https://github.com/ppuff1988/smartly-bridge/issues/39)) ([714370f](https://github.com/ppuff1988/smartly-bridge/commit/714370fdc7ab40117f4fd1c2091ff4046403a901))

## [1.8.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.7.1...v1.8.0) (2026-01-10)

### ✨ 新增功能 (Features)

* **sync:** 新增基於 domain 的默認圖標支援 ([#38](https://github.com/ppuff1988/smartly-bridge/issues/38)) ([0b3ef69](https://github.com/ppuff1988/smartly-bridge/commit/0b3ef6981cce241978eb0776e6ae3755c5cbe36b))

## [1.7.1](https://github.com/ppuff1988/smartly-bridge/compare/v1.7.0...v1.7.1) (2026-01-10)

### 🐛 錯誤修正 (Bug Fixes)

* **sync:** 修正實體圖標獲取邏輯，優先使用狀態屬性中的圖標 ([#37](https://github.com/ppuff1988/smartly-bridge/issues/37)) ([8f6aa0d](https://github.com/ppuff1988/smartly-bridge/commit/8f6aa0d62b225603d62a28e69635c4c691d1f5cf))

## [1.7.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.6.0...v1.7.0) (2026-01-10)

### ✨ 新增功能 (Features)

* **sync:** 新增實體圖示欄位到同步 API ([#36](https://github.com/ppuff1988/smartly-bridge/issues/36)) ([b8ead21](https://github.com/ppuff1988/smartly-bridge/commit/b8ead213fb1e72c052f1b93316b11f279fc64e44)), closes [#issue](https://github.com/ppuff1988/smartly-bridge/issues/issue)

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ✨ 新增功能 (Features)

- **sync:** Sync API 新增 icon 資訊回傳 (#SYNC-ICON-001)
  - `/api/smartly/sync/structure` 端點的 entities 列表新增 `icon` 欄位
  - `/api/smartly/sync/states` 端點的 states 列表新增 `icon` 欄位
  - 支援 MDI (Material Design Icons) 格式圖示
  - Icon 欄位自動 fallback：優先使用使用者自訂圖示，若無則自動使用原始預設圖示
  - 新增詳細的 Sync API 文件 (docs/sync-api.md)

### 📝 文件更新 (Documentation)

- 新增 [Sync API 說明文件](docs/sync-api.md)，包含完整的 API 參考和使用範例
- 說明 `icon` 和 `original_icon` 欄位的使用方式和建議

## [1.6.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.5.1...v1.6.0) (2026-01-08)

### ✨ 新增功能 (Features)

* **camera:** 新增 IP Camera 支援與 MJPEG 串流修正 ([#35](https://github.com/ppuff1988/smartly-bridge/issues/35)) ([43b628f](https://github.com/ppuff1988/smartly-bridge/commit/43b628fd30ffac1e3bbc6ab9f072ab73416e776a)), closes [#MJPEG-001](https://github.com/ppuff1988/smartly-bridge/issues/MJPEG-001)

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ✨ 新增功能 (Features)

- **camera:** 新增 IP Camera 支援，包含快取截圖和串流代理功能
  - 新增 `CameraManager` 管理器，提供快取機制的截圖功能
  - 支援 MJPEG 串流代理
  - 支援 ETag 條件請求 (304 Not Modified)
  - 可配置快取 TTL、串流逾時等參數
  - 新增 Camera API 端點：
    - `GET /api/smartly/camera/{entity_id}/snapshot` - 取得攝影機截圖
    - `GET /api/smartly/camera/{entity_id}/stream` - 取得攝影機串流
    - `GET /api/smartly/camera/list` - 列出所有可用攝影機
    - `POST /api/smartly/camera/config` - 管理攝影機設定

### 🐛 錯誤修正 (Bug Fixes)

- **camera:** 修正 MJPEG 串流雙層 HTTP 響應和 chunked encoding 問題 (#MJPEG-001)
  - **關鍵修正**：正確使用 `stream_response.content.iter_chunked()` 獲取純 MJPEG 數據
  - 修正雙層 HTTP 響應問題（body 中包含 `HTTP/1.1 200 OK` 導致解析失敗）
  - 禁用 MJPEG 串流的 `Transfer-Encoding: chunked`
  - 使用 `Connection: close` 和 `enable_compression(False)` 強制禁用 chunked encoding
  - 修正 Go HTTP 客戶端解析失敗問題（`invalid byte in chunk length`）
  - 確保 `multipart/x-mixed-replace` 格式正確傳輸
  - 新增詳細的調試日誌追蹤串流狀態
  - 解決串流數據無法正常傳輸的問題（bytes_written: 0）

### ♻️ 程式碼重構 (Refactoring)

- **utils:** 將數值格式化工具函式重構到 `utils.py` 模組
  - 將 `NUMERIC_PRECISION_CONFIG` 和 `UNIT_SPECIFIC_PRECISION_CONFIG` 移至 `const.py`
  - 建立 `utils.py` 存放 `format_numeric_attributes` 和 `get_decimal_places` 函式
  - 改善程式碼組織性和可維護性

### 🔒 安全性修正 (Security)

- **ci:** 改用 pip-audit 取代 Safety，解決 typer 相容性問題
- **ci:** 調整安全掃描為資訊性質，不因已知依賴限制而阻塞 CI

### 📝 說明

**安全漏洞狀況：**
- 目前開發環境使用 Python 3.12 + Home Assistant 2024.x
- pip-audit 檢測到 20 個已知漏洞（主要來自 aiohttp, urllib3 等）
- 這些是開發依賴，不影響生產環境的 Integration 本身

**解決方案：**
- 短期：安全掃描改為資訊性質，持續監控但不阻塞 CI
- 長期：升級到 Python 3.13 + Home Assistant 2025.2+
  - 可解決大部分安全漏洞
  - 需要 CI 環境支援 Python 3.13
## [1.5.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.4.1...v1.5.0) (2026-01-06)

### ✨ 新增功能 (Features)

* **http,push:** 新增數值格式化功能並整合重複邏輯 ([#32](https://github.com/ppuff1988/smartly-bridge/issues/32)) ([41ea6d3](https://github.com/ppuff1988/smartly-bridge/commit/41ea6d330a71dd63a0f760c232484c4a55f087f0))

## [1.4.1](https://github.com/ppuff1988/smartly-bridge/compare/v1.4.0...v1.4.1) (2026-01-06)

### 🐛 錯誤修正 (Bug Fixes)

* **ci:** 修正 release 流程中 manifest.json 版本不同步問題 ([#31](https://github.com/ppuff1988/smartly-bridge/issues/31)) ([a2521a7](https://github.com/ppuff1988/smartly-bridge/commit/a2521a7750105084b3d058243e640d5e1fe0d99d))

## [1.4.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.3.3...v1.4.0) (2026-01-06)

### ✨ 新增功能 (Features)

* **http:** 新增數值屬性格式化功能並修正狀態同步延遲 ([#30](https://github.com/ppuff1988/smartly-bridge/issues/30)) ([3237b90](https://github.com/ppuff1988/smartly-bridge/commit/3237b90fc9be9774164f498c3726f6a5f6d907c7))

## [1.3.3](https://github.com/ppuff1988/smartly-bridge/compare/v1.3.2...v1.3.3) (2025-12-27)

### 🐛 錯誤修正 (Bug Fixes)

* **http:** 修正服務調用時無效參數錯誤並拆分文檔 ([#26](https://github.com/ppuff1988/smartly-bridge/issues/26)) ([ce9dd9d](https://github.com/ppuff1988/smartly-bridge/commit/ce9dd9d32d0448d5aaae214d3a0493827535cce6))

## [1.3.2](https://github.com/ppuff1988/smartly-bridge/compare/v1.3.1...v1.3.2) (2025-12-26)

### 🐛 錯誤修正 (Bug Fixes)

* **ci:** 修正 auto-delete-branch workflow 權限問題 ([#24](https://github.com/ppuff1988/smartly-bridge/issues/24)) ([9a4d60a](https://github.com/ppuff1988/smartly-bridge/commit/9a4d60a6a4227d3e8a9a0181f32e288de73dc466))
* **ci:** 修正 workflow 權限與自動化問題 ([#25](https://github.com/ppuff1988/smartly-bridge/issues/25)) ([c10980e](https://github.com/ppuff1988/smartly-bridge/commit/c10980e95a60e889eca7951ecd35fd6a367e487f))

## [1.3.1](https://github.com/ppuff1988/smartly-bridge/compare/v1.3.0...v1.3.1) (2025-12-26)

### 🐛 錯誤修正 (Bug Fixes)

* 優化事件格式和 heartbeat 發送機制 ([#21](https://github.com/ppuff1988/smartly-bridge/issues/21)) ([bff33e2](https://github.com/ppuff1988/smartly-bridge/commit/bff33e26dc47126d4f2789a7a0ccf27c07530486))

## [1.3.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.2.0...v1.3.0) (2025-12-26)

### ✨ 新增功能 (Features)

* 整合 Safety MCP 自動化漏洞掃描 ([#20](https://github.com/ppuff1988/smartly-bridge/issues/20)) ([9c1d376](https://github.com/ppuff1988/smartly-bridge/commit/9c1d376a3943dcc03a7c658cbd2f978932d6666b))

## [1.2.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.1.3...v1.2.0) (2025-12-25)

### ✨ 新增功能 (Features)

* **api:** add states sync API and heartbeat mechanism ([#19](https://github.com/ppuff1988/smartly-bridge/issues/19)) ([82f3524](https://github.com/ppuff1988/smartly-bridge/commit/82f35246165a03cc925c4eb120026a2656ee38af))

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.3](https://github.com/ppuff1988/smartly-bridge/compare/v1.1.2...v1.1.3) (2025-12-22)

### 🐛 錯誤修正 (Bug Fixes)

* 修正 sync 端點未正確呼叫 get_allowed_entities ([#17](https://github.com/ppuff1988/smartly-bridge/issues/17)) ([ffbed61](https://github.com/ppuff1988/smartly-bridge/commit/ffbed61a6279b6e0a7defbb96faf6cf07a06f327))

## [1.1.2](https://github.com/ppuff1988/smartly-bridge/compare/v1.1.1...v1.1.2) (2025-12-22)

### 🐛 錯誤修正 (Bug Fixes)

* 移除錯誤的 Add-on badge 並更新 HACS 安裝指引 ([#15](https://github.com/ppuff1988/smartly-bridge/issues/15)) ([3771bcc](https://github.com/ppuff1988/smartly-bridge/commit/3771bccbde1db7791b7d48c41d519baa5a283b16))

## [1.1.1](https://github.com/ppuff1988/smartly-bridge/compare/v1.1.0...v1.1.1) (2025-12-22)

### 🐛 錯誤修正 (Bug Fixes)

* 更新 GitHub 使用者名稱從 yourusername 改為 ppuff1988 ([#14](https://github.com/ppuff1988/smartly-bridge/issues/14)) ([7a69b70](https://github.com/ppuff1988/smartly-bridge/commit/7a69b7008b81b27f8c00f16294d1cd758654e72b))

## [1.1.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.0.0...v1.1.0) (2025-12-22)

### ✨ 新增功能 (Features)

* **acl:** 實作實體標籤存取控制與結構優化 ([efa133b](https://github.com/ppuff1988/smartly-bridge/commit/efa133b6820a238b29a7b85139103d2642ac1f23))
* **ci:** 啟用完全自動化 Semantic Release 並停用手動發布 ([1d22c69](https://github.com/ppuff1988/smartly-bridge/commit/1d22c69e0a6102b2c32bb9423c239302c50907f8))

### 🐛 錯誤修正 (Bug Fixes)

* **acl:** 降低 get_structure 函數複雜度並修正 Flake8 錯誤 ([df8f7ac](https://github.com/ppuff1988/smartly-bridge/commit/df8f7acbce43dfba3ff526c4dffcca4e7a6ebb2c))

### ♻️ 程式碼重構 (Refactoring)

* 改善程式碼品質和 CI/CD 流程 ([7f15eae](https://github.com/ppuff1988/smartly-bridge/commit/7f15eaeb2cf584a98128059f323a7eab50da7874))

## 1.0.0 (2025-12-22)

### ✨ 新增功能 (Features)

* 初始化 Smartly Bridge Home Assistant 整合專案 ([a4e5c92](https://github.com/ppuff1988/smartly-bridge/commit/a4e5c92d433dbd7cacf0f24d3119622909151007))
* 實體標籤存取控制與自動化發布流程 ([#11](https://github.com/ppuff1988/smartly-bridge/issues/11)) ([b5bc9a5](https://github.com/ppuff1988/smartly-bridge/commit/b5bc9a5055c6e425fc6e5511c1f0878cca51d160))

## [Unreleased]

### Added
- 實體標籤（Entity Labels）存取控制機制，支援基於 Home Assistant 標籤過濾可存取的實體
- 完全自動化的 Semantic Release 流程，根據 Conventional Commits 自動發布版本
- 自動版本號決定機制（feat → minor, fix → patch, BREAKING → major）
- 自動生成繁體中文 CHANGELOG 功能
- 自動更新 manifest.json 版本的 Python 腳本 (`scripts/update_manifest_version.py`)
- `docs/RELEASE.md` 完整的自動化 Release 流程說明文件
- `.github/workflows/auto-release.yml` 自動發布 workflow
- `.releaserc.json` Semantic Release 配置檔
- `run-ci-tests.sh` 和 `reset.sh` 測試輔助腳本
- Git commit 規範中的 CHANGELOG 更新指南

### Changed
- 優化 `get_structure` 函數，正確處理沒有 floor 或 area 的實體
- 改善實體註冊表讀取與標籤檢查邏輯
- 更新 ACL 警告訊息，明確區分實體標籤與 NFC 標籤
- 停用手動 release.yml workflow，避免與自動化流程衝突
- 強化 `.gitignore` 配置以保護敏感資訊
- 改善 CI/CD workflows 和程式碼品質檢查配置
- 更新 SECURITY.md 安全指南內容

### Security
- 新增安全檢查文檔和最佳實踐指南

## [1.0.0] - 2025-12-17

### Added
- Initial release of Smartly Bridge integration
- OAuth-like authentication with HMAC-SHA256
- RESTful API endpoints for device control and sync
- Push notification system for state changes
- Access control list (ACL) for entities and services
- Audit logging for all control actions
- Rate limiting and CIDR-based IP filtering
- Support for Home Assistant structure (floors, areas, devices)
- Internationalization support (en, zh-Hant)

### Security
- HMAC-SHA256 request signing
- Nonce-based replay attack prevention
- Configurable CIDR IP whitelist
- Rate limiting per client
