# 開發文檔

> **技術深度文檔** | 適合開發者和貢獻者閱讀

本目錄包含 Smartly Bridge 的深度技術文檔和實作細節。

## 📚 文檔列表

### [trust-proxy.md](trust-proxy.md)
**Trust Proxy 配置指南**

說明 Trust Proxy 三段式配置功能的實作與使用方式：
- 自動檢測模式（推薦）
- 總是信任模式
- 永不信任模式
- 安全性改進與攻擊場景分析
- 配置與測試指南

**適用場景：**
- 了解 Trust Proxy 工作原理
- 配置反向代理環境
- 排查 IP 白名單問題

### [mjpeg-chunked-encoding-fix.md](mjpeg-chunked-encoding-fix.md)
**MJPEG 串流 Chunked Encoding 修正**

說明 MJPEG 串流與 HTTP Chunked Encoding 的衝突問題及解決方案：
- 問題診斷與技術原因分析
- MJPEG 與 Chunked Encoding 格式說明
- 解決方案實作細節
- 驗證測試方法
- 未來優化方向

**適用場景：**
- 理解 MJPEG 串流實作
- 排查串流傳輸問題
- HTTP 協議相容性問題

## 🔗 相關文檔

- **[CI/CD 指南](../CI_CD_GUIDE.md)** - 持續整合與部署配置
- **[API 文檔](../README.md)** - API 使用說明
- **[貢獻指南](../../CONTRIBUTING.md)** - 如何參與開發

## 📝 文檔規範

開發文檔應包含：
1. **背景說明** - 為什麼需要這個功能
2. **技術細節** - 具體實作方式
3. **使用指南** - 如何配置和使用
4. **安全考量** - 相關安全注意事項
5. **範例程式碼** - 實際使用範例

## 🤝 貢獻

如果您有新的技術文檔要補充：
1. 在此目錄創建新的 `.md` 文件
2. 使用清晰的檔案名稱（使用 kebab-case）
3. 更新本 README 的文檔列表
4. 提交 Pull Request
