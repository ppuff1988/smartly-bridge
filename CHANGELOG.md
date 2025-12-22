# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
