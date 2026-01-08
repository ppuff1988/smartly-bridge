# 手動測試腳本

> ⚠️ **注意**：這些腳本僅用於開發和測試目的，包含敏感資訊範例。

## 📂 腳本說明

### `test_smartly_api.py`
測試 Smartly Bridge API 的基本功能，包括 HMAC 認證和設備控制。

**使用方式：**
```bash
# 1. 修改腳本中的配置
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
BASE_URL = "http://localhost:8123"

# 2. 執行測試
python scripts/manual_tests/test_smartly_api.py
```

**測試項目：**
- HMAC-SHA256 簽名生成
- Sync API 結構同步
- Control API 設備控制

### `test_trust_proxy.py`
驗證 Trust Proxy 功能的配置和邏輯。

**使用方式：**
```bash
python scripts/manual_tests/test_trust_proxy.py
```

**測試項目：**
- 私有 IP 檢測
- Trust Proxy 模式判斷邏輯
- 配置常數驗證

## ⚠️ 安全提醒

1. **永不提交敏感資訊**
   - 使用前請修改 `CLIENT_ID` 和 `CLIENT_SECRET`
   - 這些腳本包含在 `.gitignore` 中

2. **僅用於開發環境**
   - 不要在生產環境執行
   - 測試完成後刪除或重置憑證

3. **自動化測試優先**
   - 優先使用 `tests/` 目錄中的自動化測試
   - 這些手動腳本僅用於快速驗證和除錯

## 📚 相關文檔

- [測試指南](../../.github/instructions/python-testing.instructions.md)
- [開發環境設定](../../CONTRIBUTING.md)
- [API 文檔](../../docs/README.md)
