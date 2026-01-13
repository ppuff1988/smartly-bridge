# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.11.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.12...v1.11.0) (2026-01-13)

### ✨ 新增功能 (Features)

* **webrtc:** 完善 WebRTC P2P 串流功能 ([#62](https://github.com/ppuff1988/smartly-bridge/issues/62)) ([68903ec](https://github.com/ppuff1988/smartly-bridge/commit/68903ec545ce72324a83fc6f79c4ab1d5932ca49))

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ✨ 新功能 (Features)

* **webrtc:** 新增 WebRTC P2P 連線支援，節省 Platform 流量
  - 新增 \`webrtc.py\` 模組處理 Token 管理和 Session 生命週期
  - Token 機制：Platform 透過 HMAC 認證請求短期 Token（5 分鐘有效）
  - Token 為單次使用，消費後即失效，防止重放攻擊
  - 新增 4 個 WebRTC API 端點：
    - \`POST /api/smartly/camera/{entity_id}/webrtc\` - 請求 Token（HMAC 保護）
    - \`POST /api/smartly/camera/{entity_id}/webrtc/offer\` - SDP Offer/Answer 交換
    - \`POST /api/smartly/camera/{entity_id}/webrtc/ice\` - ICE Candidate 交換
    - \`POST /api/smartly/camera/{entity_id}/webrtc/hangup\` - 關閉 Session
  - Camera 列表 API 現在回傳 \`webrtc\` 端點資訊
  - 新增 37 個 WebRTC 相關測試案例

### Fixed
- 修正歷史查詢 API metadata 中 device_class 為 null 的問題，實作三層 fallback 機制：
  1. 從歷史記錄的第一個 state 獲取
  2. 從歷史記錄中搜尋第一個有 device_class 的 state
  3. 從 Home Assistant 的當前狀態獲取（最可靠）
  - 確保即使歷史記錄中的 attributes 不完整，也能提供正確的 metadata
  - 同時改善 unit_of_measurement 和 friendly_name 的獲取邏輯

## [1.10.12](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.11...v1.10.12) (2026-01-12)

### 🐛 錯誤修正 (Bug Fixes)

* **ci:** 修正分支保護規則的必需檢查名稱 ([#59](https://github.com/ppuff1988/smartly-bridge/issues/59)) ([95ddaf0](https://github.com/ppuff1988/smartly-bridge/commit/95ddaf0d32ec4aecdfa3d54f06a876014e02ac93))

## [1.10.11](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.10...v1.10.11) (2026-01-12)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正 cursor 分頁無限循環與 total_count 計算錯誤 ([#57](https://github.com/ppuff1988/smartly-bridge/issues/57)) ([0c780be](https://github.com/ppuff1988/smartly-bridge/commit/0c780be9826b45a22b271933332cdb1dc83046b2))

## [1.10.10](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.9...v1.10.10) (2026-01-12)

### 🐛 錯誤修正 (Bug Fixes)

* **ci:** 新增 release workflow 並行控制，避免 tag 衝突問題 ([a893f17](https://github.com/ppuff1988/smartly-bridge/commit/a893f1785154f2fa8eae993afe6511879afa1a70))
* **ci:** 新增 tags 強制同步步驟避免重複 tag 錯誤 ([859f1f1](https://github.com/ppuff1988/smartly-bridge/commit/859f1f1d8c2579c8dc018460fa3ade19a823a101))
* **docs:** 修正 CHANGELOG 重複條目問題 ([ea4f5fe](https://github.com/ppuff1988/smartly-bridge/commit/ea4f5fe3034fdb5ed08564ffdfea780f79d9774a))
* **history:** 修正歷史查詢 metadata device_class 為 null 問題 ([#56](https://github.com/ppuff1988/smartly-bridge/issues/56)) ([617fc11](https://github.com/ppuff1988/smartly-bridge/commit/617fc1191514d46ede04d5c161a4ac6ea5709d77))

## [1.10.9](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.8...v1.10.9) (2026-01-12)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正 cursor pagination 後續請求 metadata device_class 為 null ([#54](https://github.com/ppuff1988/smartly-bridge/issues/54)) ([3ae4bf1](https://github.com/ppuff1988/smartly-bridge/commit/3ae4bf1dfd2f9f96b96eda55f124313b6bfb6f19)), closes [#53](https://github.com/ppuff1988/smartly-bridge/issues/53)

## [1.10.8](https://github.com/ppuff1988/smartly-bridge/compare/v1.10.7...v1.10.8) (2026-01-12)

### 🐛 錯誤修正 (Bug Fixes)

* **history:** 修正 cursor pagination 大量查詢失敗問題 ([#53](https://github.com/ppuff1988/smartly-bridge/issues/53)) ([14b70b5](https://github.com/ppuff1988/smartly-bridge/commit/14b70b57ae209d1e06535e9942dc152c402d9119))

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

## [1.6.0](https://github.com/ppuff1988/smartly-bridge/compare/v1.5.1...v1.6.0) (2026-01-08)

### ✨ 新增功能 (Features)

* **camera:** 新增 IP Camera 支援與 MJPEG 串流修正 ([#35](https://github.com/ppuff1988/smartly-bridge/issues/35)) ([43b628f](https://github.com/ppuff1988/smartly-bridge/commit/43b628fd30ffac1e3bbc6ab9f072ab73416e776a)), closes [#MJPEG-001](https://github.com/ppuff1988/smartly-bridge/issues/MJPEG-001)

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
