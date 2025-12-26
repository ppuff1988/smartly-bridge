# Safety MCP 設定指南

## 📋 目錄

- [什麼是 Safety MCP？](#什麼是-safety-mcp)
- [功能特性](#功能特性)
- [安裝配置](#安裝配置)
- [使用方式](#使用方式)
- [故障排除](#故障排除)

## 什麼是 Safety MCP？

**Model Context Protocol (MCP)** 是一個讓 AI 助手與外部工具通訊的開放標準協議。**Safety MCP** 是 Safety CLI 提供的 MCP 伺服器，讓 GitHub Copilot 能夠在開發過程中即時檢查 Python 套件的安全漏洞。

### 為什麼需要 Safety MCP？

傳統的依賴掃描通常在 CI/CD 階段進行，這意味著：
- ❌ 問題發現太晚（代碼已提交）
- ❌ 修復成本更高
- ❌ 可能阻塞部署流程

使用 Safety MCP：
- ✅ **即時防護** - 在撰寫程式碼時就檢查安全性
- ✅ **主動建議** - Copilot 自動推薦安全版本
- ✅ **成本降低** - 在開發階段就避免問題

## 功能特性

### 1. 自動漏洞檢查
當您添加新的 Python 套件時，Safety MCP 會自動：
- 檢查該版本是否有已知漏洞
- 提供漏洞詳細資訊
- 建議修復方案

### 2. 版本建議
- 提供 `latest_secure_version` - 同一主要版本的最新安全版本
- 提供 `latest_version` - 絕對最新版本（可能跨主版本）
- 考慮相容性和安全性的平衡

### 3. 即時回饋
在 Copilot Chat 中直接獲得安全資訊，無需切換工具或查看文檔。

## 安裝配置

### 前置需求

- VS Code 或 VS Code Insiders
- GitHub Copilot 訂閱
- Safety API Key

### 步驟 1：獲取 Safety API Key

您的 API Key 已配置：
```
00a8b1d8-b01d-47e2-939b-da51dce589c7
```

⚠️ **安全提醒**：請勿將 API Key 提交到版本控制系統中。

### 步驟 2：配置 VS Code

配置檔案已自動建立在 `.vscode/settings.json`：

```json
{
  "chat.mcp.discovery.enabled": true,
  "mcp": {
    "inputs": [],
    "servers": {
      "safety-mcp": {
        "url": "https://mcp.safetycli.com/sse",
        "type": "http",
        "headers": {
          "Authorization": "Bearer 00a8b1d8-b01d-47e2-939b-da51dce589c7"
        }
      }
    }
  }
}
```

### 步驟 3：配置 Copilot 指令

Copilot 指令已建立在 `.github/copilot-instructions.md`，包含：
- Python 套件安全檢查規則
- 使用 `latest_secure_version` 的指引
- 程式碼品質和安全最佳實踐

### 步驟 4：重新載入 VS Code

完成配置後，重新載入 VS Code 視窗：
1. 按 `Cmd+Shift+P` (macOS) 或 `Ctrl+Shift+P` (Windows/Linux)
2. 輸入 "Reload Window"
3. 選擇 "Developer: Reload Window"

## 使用方式

### 在 Copilot Chat 中使用

**範例 1：檢查新套件**
```
@workspace 我想添加 requests 套件，請檢查最新的安全版本
```

Copilot 會使用 Safety MCP 查詢並回覆：
```
requests 的最新安全版本是 2.31.0
建議在 requirements.txt 中添加：
requests==2.31.0
```

**範例 2：檢查現有依賴**
```
@workspace 檢查 requirements.txt 中的所有套件是否有漏洞
```

**範例 3：更新不安全的套件**
```
@workspace flask 1.1.2 有漏洞嗎？應該更新到哪個版本？
```

### 在程式碼中使用

當您編寫程式碼時，Copilot 會自動考慮安全性：

```python
# 您輸入：
import flask

# Copilot 建議（在 requirements.txt 中）：
flask==3.0.0  # latest_secure_version
```

### 切換到 Agent 模式

要充分利用 Safety MCP，建議使用 Copilot 的 Agent 模式：

1. 開啟 Copilot Chat
2. 點擊右上角的設定圖示
3. 選擇 "Use Agent Mode"
4. 現在 Copilot 會自動使用 Safety MCP 進行安全檢查

## 故障排除

### MCP 連線失敗

**症狀**：Copilot 無法連接到 Safety MCP
**解決方案**：
1. 檢查 API Key 是否正確
2. 確認網路連線正常
3. 重新載入 VS Code 視窗

### API Key 無效

**症狀**：收到認證錯誤
**解決方案**：
1. 確認 API Key 完整複製（無空格或換行）
2. 在 Safety CLI 網站重新生成 API Key
3. 更新 `.vscode/settings.json` 中的 Key

### Copilot 未使用 Safety MCP

**症狀**：Copilot 沒有提供安全建議
**解決方案**：
1. 確認已啟用 Agent 模式
2. 在提示中明確提及安全檢查
3. 檢查 `.github/copilot-instructions.md` 是否正確配置

### 設定未生效

**症狀**：配置後仍無法使用
**解決方案**：
1. 檢查 `.vscode/settings.json` 語法是否正確（JSON 格式）
2. 重新啟動 VS Code（不只是重新載入）
3. 確認 GitHub Copilot 已登入並啟用

## 最佳實踐

### 1. 定期更新依賴
即使使用 Safety MCP，仍應定期執行完整掃描：
```bash
./run-ci-tests.sh --security
```

### 2. CI/CD 整合
Safety MCP 用於開發階段，但仍需在 CI/CD 中執行掃描：
- 已配置 `.github/workflows/safety-scan.yml`
- 每日自動掃描
- PR 中自動檢查

### 3. 團隊協作
- 確保所有開發人員都配置了 Safety MCP
- 在團隊文檔中記錄配置步驟
- 定期審查和更新 Copilot 指令

### 4. 版本固定
- 始終在 `requirements.txt` 中固定版本號
- 使用 `==` 而非 `>=` 或 `~=`
- 定期審查和更新固定版本

## 相關資源

- [Safety CLI 官方文檔](https://docs.safetycli.com/)
- [MCP 規範](https://modelcontextprotocol.io/)
- [GitHub Copilot 文檔](https://docs.github.com/copilot)
- [專案 Security 工作流程](.github/workflows/safety-scan.yml)

## 支援

如有問題，請聯繫：
- Safety CLI 支援：support@safetycli.com（通常 4 小時內回覆）
- 專案維護者：參見 [CONTRIBUTING.md](../CONTRIBUTING.md)

---

**最後更新**：2025-12-26
**MCP 版本**：當前 MCP 規範仍在演進中，Safety 會持續更新以支援最新規範。
