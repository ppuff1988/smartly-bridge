# GitHub Copilot 指令 - Safety MCP 集成

## 安全依賴管理規則

### Python 套件安全檢查

- **添加新套件時必須檢查**：每次您要匯入 Python 套件或添加套件到 `requirements.txt`、`requirements-dev.txt` 或 `pyproject.toml` 時，必須使用 `safety-mcp` 工具檢查該版本是否安全且為最新版本。

- **使用最新安全版本**：確保始終使用 `safety-mcp` 回傳的 `latest_secure_version` 作為任何套件的版本。

- **檢查現有套件**：如果程式碼庫中已存在某個套件，且使用者要求檢查其漏洞，請使用 `safety-mcp` 評估：
  - 同一主要版本中是否有安全版本
  - 提供這些選項的資訊
  - 告知使用者該套件的最新安全版本

### 範例工作流程

```python
# ❌ 錯誤：未經檢查就添加套件
import requests  # 哪個版本？是否安全？

# ✅ 正確：使用 safety-mcp 檢查後添加
# 1. 檢查 requests 套件的安全版本
# 2. 在 requirements.txt 中使用: requests==2.31.0  # latest_secure_version
import requests
```

## 程式碼品質要求

### Home Assistant 整合開發

- 遵循 Home Assistant 開發指南
- 使用 `async_setup_entry` 和 `async_unload_entry`
- 正確處理配置流程和選項流程
- 實作適當的錯誤處理和日誌記錄

### Python 編碼標準

- 使用 Black 進行程式碼格式化（最大行長度：100）
- 使用 isort 進行導入排序
- 遵循 PEP 8 風格指南
- 添加類型提示（Type Hints）
- 撰寫文檔字串（Docstrings）

### 測試覆蓋率

- 為新功能撰寫單元測試
- 保持測試覆蓋率 > 80%
- 使用 pytest 作為測試框架
- 模擬外部依賴

## 安全最佳實踐

1. **永不硬編碼敏感資訊** - 使用 `secrets.yaml` 或環境變數
2. **驗證所有輸入** - 特別是來自 API 或使用者輸入
3. **使用參數化查詢** - 避免 SQL 注入
4. **保持依賴更新** - 定期執行 `safety check`
5. **最小權限原則** - 僅請求必要的權限

## 程式碼審查檢查清單

- [ ] 所有依賴都通過 Safety MCP 檢查
- [ ] 程式碼已格式化（Black + isort）
- [ ] 無 Flake8 警告
- [ ] 類型檢查通過（MyPy）
- [ ] 測試覆蓋率充足
- [ ] 文檔已更新
- [ ] 變更記錄已更新（CHANGELOG.md）
