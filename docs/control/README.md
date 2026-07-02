# Home Assistant 設備控制 API 完整指南

> **版本**：v1.0.0  
> **最後更新**：2025-12-27  
> **適用於**：Smartly Bridge Home Assistant Integration

本文檔提供完整的 Home Assistant 設備控制 API 規範、範例與最佳實踐，涵蓋 9 種核心設備類型。

---

## 📖 文檔導覽

本指南已拆分為以下章節，請依需求點選：

| 文檔 | 說明 |
|------|------|
| **[API 基礎與認證](./api-basics.md)** | 端點資訊、HTTP 標頭、請求結構、HMAC-SHA256 簽名計算 |
| **[設備類型控制](./device-types.md)** | 9 種設備類型的動作與參數說明（Switch、Light、Cover、Climate、Fan、Lock、Scene、Script、Automation） |
| **[程式碼範例](./code-examples.md)** | 完整的 cURL、Python、JavaScript/TypeScript 實作範例 |
| **[回應格式](./responses.md)** | 成功回應、錯誤回應與 HTTP 狀態碼說明 |
| **[安全指南](./security.md)** | HMAC 簽名安全、IP 白名單、速率限制、ACL、審計日誌 |
| **[故障排除](./troubleshooting.md)** | 常見問題、除錯步驟與解決方案 |

---

## 🚀 快速開始

### 1. 基本請求格式

```
POST /api/smartly/control
Content-Type: application/json
```

### 2. 請求 Body 結構

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

### 3. 必要的 HTTP 標頭

| 標頭 | 說明 |
|------|------|
| `X-Client-Id` | 客戶端識別碼 |
| `X-Timestamp` | Unix 時間戳（秒） |
| `X-Nonce` | UUID v4，每次請求唯一 |
| `X-Signature` | HMAC-SHA256 簽名 |

詳細說明請參閱 **[API 基礎與認證](./api-basics.md)**。

---

## 🎯 支援的設備類型

| 設備類型 | Domain | 主要動作 |
|---------|--------|---------|
| [Switch（開關）](./device-types.md#1-switch開關) | `switch` | `turn_on`, `turn_off`, `toggle` |
| [Light（燈光）](./device-types.md#2-light燈光) | `light` | `turn_on`, `turn_off`, `toggle` |
| [Cover（窗簾）](./device-types.md#3-cover窗簾捲簾車庫門) | `cover` | `open_cover`, `close_cover`, `set_cover_position` |
| [Climate（空調）](./device-types.md#4-climate空調恆溫器暖氣) | `climate` | `set_temperature`, `set_hvac_mode`, `set_fan_mode` |
| [Fan（風扇）](./device-types.md#5-fan風扇) | `fan` | `turn_on`, `turn_off`, `set_percentage` |
| [Lock（門鎖）](./device-types.md#6-lock門鎖) | `lock` | `lock`, `unlock` |
| [Scene（場景）](./device-types.md#7-scene場景) | `scene` | `turn_on` |
| [Script（腳本）](./device-types.md#8-script腳本) | `script` | `turn_on`, `turn_off` |
| [Automation（自動化）](./device-types.md#9-automation自動化) | `automation` | `trigger`, `turn_on`, `turn_off` |

詳細參數說明請參閱 **[設備類型控制](./device-types.md)**。

---

## 📚 相關文檔

- **[OpenAPI 規格](../openapi.yaml)** - 完整的 API 規格定義
- **[專案 README](../../README.md)** - 專案概覽與快速開始
- **[SECURITY.md](../../SECURITY.md)** - 安全最佳實踐與漏洞回報
- **[CONTRIBUTING.md](../../CONTRIBUTING.md)** - 貢獻指南
- **[Home Assistant 開發文檔](https://developers.home-assistant.io/)** - 官方開發資源

---

## 📝 更新記錄

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| **v1.0.0** | 2025-12-27 | • 完整重寫文檔結構<br>• 拆分為多個子文檔<br>• 新增完整的 Python/JS/TypeScript 範例<br>• 擴充故障排除章節<br>• 新增安全最佳實踐 |
| **v0.1.0** | 2025-12-26 | • 初始版本 |

---

## 🤝 貢獻

歡迎提交 Issue 或 Pull Request 來改進這份文檔！

---

**製作**：Smartly Bridge Team  
**最後更新**：2025-12-27
