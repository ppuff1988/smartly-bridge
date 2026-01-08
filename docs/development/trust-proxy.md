# Trust Proxy 配置指南

> **技術文檔** | 更新日期：2026-01-08

本文檔說明 Smartly Bridge 的 Trust Proxy 功能實作與配置方式，解決 X-Forwarded-For 標頭可能被偽造繞過 IP 白名單的安全問題。

---

## ✅ 已完成的修改

### 1. **核心常數定義** ([`const.py`](custom_components/smartly_bridge/const.py))
- ✅ 新增 `CONF_TRUST_PROXY` 配置鍵
- ✅ 新增三種模式：`TRUST_PROXY_AUTO`、`TRUST_PROXY_ALWAYS`、`TRUST_PROXY_NEVER`
- ✅ 新增 `PRIVATE_IP_RANGES` 用於自動判斷
- ✅ 設定預設值 `DEFAULT_TRUST_PROXY = "auto"`

### 2. **認證邏輯** ([`auth.py`](custom_components/smartly_bridge/auth.py))
- ✅ 新增 `_is_private_ip()` 函數：檢測 IP 是否為私有/內網 IP
- ✅ 新增 `_should_trust_proxy()` 函數：智慧判斷是否應信任 X-Forwarded-For
- ✅ 重構 `get_client_ip()` 函數：支援 `trust_proxy_mode` 參數
- ✅ 更新 `verify_request()` 函數：傳遞 `trust_proxy_mode` 參數

### 3. **配置流程** ([`config_flow.py`](custom_components/smartly_bridge/config_flow.py))
- ✅ 在初始配置中加入 `trust_proxy` 預設值
- ✅ 在選項流程中新增 `trust_proxy` 選擇器（三個選項）
- ✅ UI 顯示下拉選單讓使用者選擇模式

### 4. **API Views** (所有 views)
- ✅ [`views/control.py`](custom_components/smartly_bridge/views/control.py)：更新 control API
- ✅ [`views/sync.py`](custom_components/smartly_bridge/views/sync.py)：更新 sync API（2 個 view）
- ✅ [`views/camera.py`](custom_components/smartly_bridge/views/camera.py)：更新 camera API（4 個 view）

### 5. **翻譯字串**
- ✅ [`translations/zh-Hant.json`](custom_components/smartly_bridge/translations/zh-Hant.json)：繁體中文翻譯
- ✅ [`translations/en.json`](custom_components/smartly_bridge/translations/en.json)：英文翻譯

---

## 🎯 功能說明

### 三種 Trust Proxy 模式

| 模式 | 值 | 說明 | 適用場景 |
|------|-----|------|---------|
| **自動檢測（推薦）** | `auto` | 自動判斷是否在 Proxy 後方 | 大部分場景（預設） |
| **總是信任** | `always` | 總是信任 X-Forwarded-For | 確定有 Nginx/Caddy 等 Proxy |
| **永不信任** | `never` | 永不信任 X-Forwarded-For | 直接對外（無 Proxy） |

### 自動判斷邏輯（mode=auto）

```python
def _should_trust_proxy(request, allowed_cidrs):
    """智慧判斷是否應該信任 X-Forwarded-For"""
    
    # 1. 取得直連 IP
    direct_ip = request.remote  # 例如：127.0.0.1 或 192.168.1.254
    
    # 2. 檢查直連 IP 是否為私有/內網 IP
    if not _is_private_ip(direct_ip):
        return False  # 公網 IP，不信任標頭
    
    # 3. 檢查 CIDR 白名單是否包含公網 IP
    if allowed_cidrs contains public IPs:
        return True  # 推測有 Proxy，信任標頭
    
    return False  # 預設不信任
```

---

## 🔒 安全性改進

### ❌ 修改前（有漏洞）

```python
def get_client_ip(request):
    # ⚠️ 無條件優先使用 X-Forwarded-For
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    return request.remote
```

**攻擊場景：**
```bash
# 攻擊者偽造標頭
curl -H "X-Forwarded-For: 192.168.1.100" https://ha.com/api/smartly/control
→ 程式誤以為來自白名單 IP
→ 🔥 繞過 IP 白名單驗證
```

### ✅ 修改後（安全）

```python
def get_client_ip(request, trust_proxy_mode="auto", allowed_cidrs=""):
    # 1. 根據模式決定是否信任 X-Forwarded-For
    if trust_proxy_mode == "always":
        trust_proxy = True
    elif trust_proxy_mode == "never":
        trust_proxy = False
    else:  # "auto"
        trust_proxy = _should_trust_proxy(request, allowed_cidrs)
    
    # 2. 只有在明確信任時才使用標頭
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    
    # 3. 預設使用直連 IP（最安全）
    return request.remote
```

**防禦效果：**
```bash
# 場景 A：直連（無 Proxy）
request.remote = "5.6.7.8"（攻擊者）
X-Forwarded-For = "192.168.1.100"（偽造）
trust_proxy_mode = "auto"

→ _should_trust_proxy() 返回 False（直連 IP 不是私有 IP）
→ 使用 request.remote = "5.6.7.8"
→ ❌ 不在白名單，攻擊失敗 ✅

# 場景 B：有 Nginx Proxy
request.remote = "127.0.0.1"（Nginx）
X-Forwarded-For = "1.2.3.4"（真實客戶端）
allowed_cidrs = "1.2.3.0/24"
trust_proxy_mode = "auto"

→ _should_trust_proxy() 返回 True（直連 IP 是 localhost，白名單有公網 IP）
→ 使用 X-Forwarded-For = "1.2.3.4"
→ ✅ 通過白名單驗證 ✅
```

---

## 📊 部署場景對照表

| 場景 | 直連 IP | X-Forwarded-For | CIDR 白名單 | auto 模式行為 | 建議模式 |
|------|---------|-----------------|------------|--------------|---------|
| **直連（無 Proxy）** | 1.2.3.4 | 偽造 | 1.2.3.0/24 | 使用直連 IP | ✅ auto |
| **有 Nginx** | 127.0.0.1 | 1.2.3.4 | 1.2.3.0/24 | 使用 X-F-F | ✅ auto 或 always |
| **內網測試** | 192.168.1.100 | - | 192.168.1.0/24 | 使用直連 IP | ✅ auto |
| **Cloudflare** | CF IP | 真實 IP | 公網 IP | 使用 X-F-F | always |

---

## 🧪 測試驗證

### 執行測試
```bash
cd /workspace
python test_trust_proxy.py
```

### 測試結果
```
✅ 常數定義檢查
  CONF_TRUST_PROXY = trust_proxy
  TRUST_PROXY_AUTO = auto
  DEFAULT_TRUST_PROXY = auto

✅ 私有 IP 檢測測試
  ✅ 127.0.0.1       -> True  (localhost)
  ✅ 192.168.1.1     -> True  (私有網路)
  ✅ 10.0.0.1        -> True  (私有網路)
  ✅ 8.8.8.8         -> False (公網 IP)

✅ 所有檢查通過！
```

---

## 🎨 UI 截圖說明

使用者在 Home Assistant UI 設定時會看到：

### 選項設定頁面
```
┌─────────────────────────────────────────┐
│ Smartly Bridge 選項                     │
├─────────────────────────────────────────┤
│ Platform Webhook URL:                   │
│ [https://platform.example.com/webhook]  │
│                                         │
│ Allowed IP Ranges (CIDR):               │
│ [1.2.3.0/24, 10.0.0.0/8]               │
│                                         │
│ Push Batch Interval (seconds):         │
│ [0.5]                                   │
│                                         │
│ Proxy Trust Mode:                       │
│ ┌───────────────────────────────────┐   │
│ │ Auto-detect (Recommended)       ▼│   │
│ ├───────────────────────────────────┤   │
│ │ Auto-detect (Recommended)        │   │
│ │ Always trust (Behind proxy)      │   │
│ │ Never trust (Direct connection)  │   │
│ └───────────────────────────────────┘   │
│                                         │
│ ℹ️ 自動檢測：自動判斷是否在 Proxy 後方  │
│                                         │
│         [取消]           [儲存]          │
└─────────────────────────────────────────┘
```

---

## 📝 使用指南

### 場景 1：Home Assistant 直接對外（無 Proxy）

**配置：**
- Proxy Trust Mode：`Auto-detect (Recommended)` 或 `Never trust`
- Allowed CIDRs：`1.2.3.4/32`（您的公網 IP）

**運作：**
- 直連 IP = 1.2.3.4
- auto 模式檢測：直連 IP 不是私有 IP → 不信任標頭
- 使用真實 IP 進行白名單驗證 ✅

### 場景 2：Home Assistant 在 Nginx 後方

**Nginx 配置：**
```nginx
location /api/smartly/ {
    proxy_pass http://localhost:8123;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header Host $host;
}
```

**Home Assistant 配置：**
- Proxy Trust Mode：`Auto-detect (Recommended)` 或 `Always trust`
- Allowed CIDRs：`1.2.3.0/24`（外部網路）

**運作：**
- 直連 IP = 127.0.0.1（Nginx）
- X-Forwarded-For = 1.2.3.4（真實客戶端）
- auto 模式檢測：直連 IP 是 localhost，白名單有公網 IP → 信任標頭
- 使用 X-Forwarded-For 進行白名單驗證 ✅

### 場景 3：Cloudflare CDN

**配置：**
- Proxy Trust Mode：`Always trust`（明確告知有 CDN）
- Allowed CIDRs：您的使用者來源 IP 範圍

**說明：**
- Cloudflare 會設定正確的 X-Forwarded-For
- 使用 `always` 模式確保正確解析真實 IP

---

## 🔧 故障排除

### 問題 1：白名單驗證失敗

**症狀：**
```json
{"error": "ip_not_allowed"}
```

**檢查步驟：**
1. 查看日誌確認使用的 IP
   ```python
   _LOGGER.debug("Client IP: %s, Trust Proxy: %s", client_ip, trust_proxy)
   ```

2. 確認 trust_proxy 模式是否正確
   - 有 Proxy 但用 `never`：會使用 Proxy IP（錯誤）
   - 無 Proxy 但用 `always`：可能被偽造（危險）

3. 調整模式或白名單
   - 建議先用 `auto` 模式
   - 如果不正確，根據實際環境手動選擇

### 問題 2：自動檢測不正確

**解決方案：**
- 手動覆寫為 `always` 或 `never`
- 檢查是否配置了正確的 CIDR 白名單

### 問題 3：遷移舊配置

**自動處理：**
- 舊的 config entries 會自動加入 `trust_proxy: "auto"` 預設值
- 不需要手動遷移

---

## 📚 技術文件連結

## 相關文檔

- **[安全審計報告](../security-audit.md)** - 完整安全性審查報告
- **[安全政策](../../SECURITY.md)** - 專案安全政策與漏洞回報
- **[API 安全指南](../control/security.md)** - API 安全最佳實踐
- **[貢獻指南](../../CONTRIBUTING.md)** - 如何參與貢獻
- **[CI/CD 指南](../ci-cd-guide.md)** - 持續整合與部署配置

---

## ✅ 實作完成檢查清單

- [x] 新增常數定義（const.py）
- [x] 實作私有 IP 檢測邏輯
- [x] 實作智慧判斷邏輯
- [x] 重構 get_client_ip() 函數
- [x] 更新 verify_request() 函數
- [x] 更新配置流程（config_flow.py）
- [x] 更新所有 API views（7 個端點）
- [x] 新增繁體中文翻譯
- [x] 新增英文翻譯
- [x] 編譯檢查（無語法錯誤）
- [x] 功能測試腳本
- [x] 文件撰寫

---

## 🎉 結論

**trust_proxy 三段式配置**功能已完整實作，具備以下特點：

1. ✅ **自動化**：預設 `auto` 模式智慧判斷，零配置
2. ✅ **靈活性**：提供三種模式適應不同部署場景
3. ✅ **安全性**：有效防止 X-Forwarded-For 偽造攻擊
4. ✅ **易用性**：UI 清晰說明，降低配置門檻
5. ✅ **向後相容**：舊配置自動遷移，不影響既有用戶

**下一步建議：**
- 執行完整單元測試（`pytest tests/test_auth.py`）
- 在實際環境中測試各種場景
- 更新使用者文件（README.md）
- 發布新版本（遵循語意化版本）

---

**實作完成日期：** 2026-01-08  
**實作者：** GitHub Copilot  
**版本：** 1.1.0（建議）
