# 安全審計報告

> **Smartly Bridge 整合安全性審查** | 更新日期：2026-01-08

**審查範圍**: custom_components/smartly_bridge 整合  
**審查者**: GitHub Copilot

---

## 執行摘要

本次安全性審查針對 Smartly Bridge Home Assistant 整合進行全面檢查，評估身份驗證、授權、輸入驗證、密碼管理、依賴項安全等關鍵安全面向。

### 整體安全等級：**良好** ✅

主要發現：
- ✅ 實作完善的 HMAC 身份驗證機制
- ✅ 使用 `hmac.compare_digest` 防止時序攻擊
- ✅ 實作 nonce 重放攻擊防護
- ✅ 實作速率限制機制
- ✅ 無硬編碼敏感資訊
- ⚠️ 部分區域需要加強安全檢查

---

## 1. 身份驗證與授權 ✅

### 1.1 HMAC 簽章驗證 ✅

**檔案**: [auth.py](custom_components/smartly_bridge/auth.py#L139-L174)

**優點**:
- ✅ 使用 HMAC-SHA256 進行訊息簽章
- ✅ 使用 `hmac.compare_digest()` 防止時序攻擊
- ✅ 包含時間戳、nonce、請求路徑、HTTP 方法、請求體雜湊
- ✅ 簽章格式完整：`METHOD\nPATH\nTIMESTAMP\nNONCE\nBODY_HASH`

```python
def verify_signature(
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    provided_signature: str,
) -> bool:
    """Verify HMAC-SHA256 signature using constant-time comparison."""
    expected = compute_signature(secret, method, path, timestamp, nonce, body)
    return hmac.compare_digest(expected, provided_signature)  # ✅ 防止時序攻擊
```

### 1.2 重放攻擊防護 ✅

**檔案**: [auth.py](custom_components/smartly_bridge/auth.py#L39-L90)

**實作機制**:
1. **Nonce Cache**: 使用記憶體快取追蹤已使用的 nonce
2. **TTL 機制**: nonce 在 5 分鐘後自動過期
3. **定期清理**: 每 60 秒清理過期的 nonce
4. **時間戳驗證**: 要求時間戳在 30 秒容差範圍內

```python
async def check_and_add(self, nonce: str) -> bool:
    """Check if nonce exists, add if not. Returns True if nonce is new."""
    async with self._lock:
        now = time.time()
        if nonce in self._cache:
            return False  # Nonce already used (replay attack) ✅
        self._cache[nonce] = now
        return True
```

**風險評估**: ✅ 低風險
- 重啟服務時 nonce cache 會重置，但因為有時間戳驗證，舊的 nonce 無法重用

### 1.3 IP 白名單檢查 ✅

**檔案**: [auth.py](custom_components/smartly_bridge/auth.py#L181-L207)

**優點**:
- ✅ 支援 CIDR 範圍配置
- ✅ 正確處理 IPv4 和 IPv6
- ✅ 支援 X-Forwarded-For 標頭（反向代理場景）

**注意事項**:
```python
def get_client_ip(request: web.Request) -> str:
    """Get client IP from request, considering X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()  # ⚠️ 取第一個 IP
```

**建議**: 
- ⚠️ X-Forwarded-For 標頭可能被偽造，建議文件中說明必須在受信任的反向代理後使用
- ✅ 已在配置中提供空白則不限制的選項

### 1.4 速率限制 ✅

**檔案**: [auth.py](custom_components/smartly_bridge/auth.py#L93-L130)

**實作**:
- 滑動視窗演算法
- 預設：60 請求 / 60 秒
- 按 client_id 進行限制
- 429 狀態碼和 Retry-After 標頭

```python
async def check(self, client_id: str) -> bool:
    """Check if request is allowed. Returns True if allowed."""
    async with self._lock:
        now = time.time()
        window_start = now - self._window
        
        # Remove old requests outside the window
        self._requests[client_id] = [t for t in self._requests[client_id] if t > window_start]
        
        # Check if under limit
        if len(self._requests[client_id]) >= self._max_requests:
            return False  # ✅ Rate limited
```

---

## 2. 存取控制 (ACL) ✅

**檔案**: [acl.py](custom_components/smartly_bridge/acl.py)

### 2.1 實體白名單 ✅

**機制**:
- 使用 Home Assistant 實體標籤（Label）系統
- 僅允許標記為 `smartly` 的實體被控制
- 預設拒絕（Deny by Default）原則

```python
def is_entity_allowed(
    hass: HomeAssistant,
    entity_id: str,
    entity_registry: EntityRegistry,
) -> bool:
    """Check if entity is allowed for platform control."""
    entry = entity_registry.async_get(entity_id)
    if entry is None:
        return False
    
    # Check for smartly_control label
    if entry.labels and PLATFORM_CONTROL_LABEL in entry.labels:
        return True  # ✅ 明確允許
    
    return False  # ✅ 預設拒絕
```

### 2.2 服務白名單 ✅

**檔案**: [const.py](custom_components/smartly_bridge/const.py#L35-L47)

```python
ALLOWED_SERVICES: dict[str, list[str]] = {
    "switch": ["turn_on", "turn_off", "toggle"],
    "light": ["turn_on", "turn_off", "toggle"],
    "cover": ["open_cover", "close_cover", "stop_cover", "set_cover_position"],
    "climate": ["set_temperature", "set_hvac_mode", "set_fan_mode"],
    "fan": ["turn_on", "turn_off", "set_percentage", "set_preset_mode"],
    "lock": ["lock", "unlock"],
    "scene": ["turn_on"],
    "script": ["turn_on", "turn_off"],
    "automation": ["trigger", "turn_on", "turn_off"],
    "camera": ["enable_motion_detection", "disable_motion_detection", "record", "snapshot"],
}
```

**優點**:
- ✅ 白名單機制，預設拒絕未列出的服務
- ✅ 按 domain 分類，易於維護
- ✅ 僅包含必要的控制服務

### 2.3 區域過濾 ✅

**檔案**: [acl.py](custom_components/smartly_bridge/acl.py#L95-L124)

支援按區域（Area）、樓層（Floor）過濾實體，提供更細緻的存取控制。

---

## 3. 輸入驗證 ✅

### 3.1 JSON 輸入驗證 ✅

**檔案**: [views/control.py](custom_components/smartly_bridge/views/control.py#L100-L107)

```python
try:
    body = await self.request.json()
except json.JSONDecodeError:
    return web.json_response(
        {"error": "invalid_json"},
        status=400,
    )  # ✅ 捕捉無效 JSON
```

### 3.2 必要欄位檢查 ✅

```python
entity_id = body.get("entity_id")
action = body.get("action")

if not entity_id or not action:
    return web.json_response(
        {"error": "missing_required_fields"},
        status=400,
    )  # ✅ 檢查必要欄位
```

### 3.3 CIDR 格式驗證 ✅

**檔案**: [config_flow.py](custom_components/smartly_bridge/config_flow.py#L93-L106)

```python
def _validate_cidrs(self, cidrs_str: str) -> bool:
    """Validate CIDR format."""
    import ipaddress
    
    if not cidrs_str.strip():
        return True
    
    cidrs = [c.strip() for c in cidrs_str.split(",") if c.strip()]
    for cidr in cidrs:
        try:
            ipaddress.ip_network(cidr, strict=False)  # ✅ 使用 ipaddress 驗證
        except ValueError:
            return False
    
    return True
```

### 3.4 URL 格式驗證 ✅

```python
webhook_url = user_input.get(CONF_WEBHOOK_URL, "")
if webhook_url and not webhook_url.startswith(("http://", "https://")):
    errors[CONF_WEBHOOK_URL] = "invalid_url"  # ✅ 檢查 URL 格式
```

---

## 4. 敏感資訊管理 ✅

### 4.1 無硬編碼敏感資訊 ✅

**掃描結果**: 
- ✅ 無硬編碼密碼或 API 金鑰
- ✅ 所有敏感資訊存儲在 ConfigEntry.data 中
- ✅ Home Assistant 會加密 ConfigEntry 資料

### 4.2 安全的密碼生成 ✅

**檔案**: [config_flow.py](custom_components/smartly_bridge/config_flow.py#L24-L32)

```python
import secrets

def generate_client_id() -> str:
    """Generate a unique client ID."""
    return f"ha_{secrets.token_urlsafe(16)}"  # ✅ 使用 secrets 模組

def generate_client_secret() -> str:
    """Generate a secure client secret."""
    return secrets.token_urlsafe(32)  # ✅ 使用密碼學安全的隨機數
```

**優點**:
- ✅ 使用 Python `secrets` 模組（CSPRNG）
- ✅ 產生長度足夠的金鑰（32 bytes URL-safe base64）
- ✅ 每次配置時自動產生新金鑰

### 4.3 相機認證處理 ⚠️

**檔案**: [camera.py](custom_components/smartly_bridge/camera.py#L270-L271)

```python
if config.username and config.password:
    auth = aiohttp.BasicAuth(config.username, config.password)  # ⚠️ Basic Auth
```

**風險評估**: 
- ⚠️ 使用 HTTP Basic Authentication（明文傳輸使用者名稱和密碼的 Base64 編碼）
- ⚠️ 依賴 HTTPS 確保傳輸安全

**建議**:
1. 在文件中明確說明必須使用 HTTPS 的相機 URL
2. 如果相機不支援 HTTPS，應警告使用者風險
3. 考慮支援 Digest Authentication 或 Token-based 認證

---

## 5. 注入攻擊防護 ✅

### 5.1 無 SQL 注入風險 ✅

**掃描結果**: 
- ✅ 專案未使用資料庫
- ✅ 所有資料存儲使用 Home Assistant 的 ConfigEntry 和 Registry

### 5.2 無命令注入風險 ✅

**掃描結果**:
- ✅ 未使用 `os.system()`、`subprocess`、`shell=True`
- ✅ 未使用 `eval()`、`exec()`、`compile()`
- ✅ 所有服務呼叫使用 Home Assistant API

```python
await self.hass.services.async_call(
    domain,
    action,
    service_call_data,
    blocking=True,
)  # ✅ 使用 Home Assistant 內建 API
```

### 5.3 無反序列化漏洞 ✅

**掃描結果**:
- ✅ 未使用 `pickle`、`marshal`、`shelve`
- ✅ 未使用 `yaml.load()` 或 `yaml.unsafe_load()`
- ✅ 僅使用 `json.loads()` 處理輸入

---

## 6. 錯誤處理與日誌 ✅

### 6.1 安全的錯誤訊息 ✅

**範例**: [views/control.py](custom_components/smartly_bridge/views/control.py#L195-L209)

```python
except Exception as err:
    _LOGGER.error("Service call failed: %s", err)  # ✅ 詳細錯誤記錄在日誌
    log_control(
        _LOGGER,
        client_id=auth_result.client_id or "unknown",
        entity_id=entity_id,
        service=action,
        result=f"error: {type(err).__name__}",  # ✅ 僅返回錯誤類型
        actor=actor,
    )
    return web.json_response(
        {"error": "service_call_failed"},  # ✅ 通用錯誤訊息，不洩露細節
        status=500,
    )
```

**優點**:
- ✅ API 返回通用錯誤訊息
- ✅ 詳細錯誤記錄在日誌中
- ✅ 不洩露內部實作細節

### 6.2 審計日誌 ✅

**檔案**: [audit.py](custom_components/smartly_bridge/audit.py)

提供完整的審計日誌功能：
- `log_control()`: 記錄控制操作
- `log_deny()`: 記錄拒絕存取
- `log_push_success()` / `log_push_fail()`: 記錄推送狀態

**範例**:
```python
log_deny(
    _LOGGER,
    client_id=auth_result.client_id or "unknown",
    entity_id=entity_id,
    service=action,
    reason="entity_not_allowed",
    actor=actor,
)
```

---

## 7. HTTPS 與傳輸安全 ⚠️

### 7.1 對外通訊使用 HTTPS ⚠️

**檔案**: [push.py](custom_components/smartly_bridge/push.py)

**目前狀態**:
```python
webhook_url = self.config_entry.data.get(CONF_WEBHOOK_URL, "")
# ⚠️ 未強制要求 HTTPS
```

**建議**:
1. 在配置流程中驗證 webhook URL 必須使用 HTTPS
2. 如果使用 HTTP，顯示安全警告
3. 在文件中明確說明 HTTPS 的重要性

**建議修改**:
```python
def _validate_webhook_url(self, url: str) -> bool:
    """Validate webhook URL must use HTTPS in production."""
    if not url:
        return True  # Optional field
    
    if not url.startswith("https://"):
        # Allow http:// only for localhost/testing
        if not any(domain in url for domain in ["localhost", "127.0.0.1", "[::1]"]):
            return False
    
    return True
```

### 7.2 SSL 憑證驗證 ✅

**檔案**: [camera.py](custom_components/smartly_bridge/camera.py#L55)

```python
@dataclass
class CameraConfig:
    """Configuration for an IP camera."""
    verify_ssl: bool = True  # ✅ 預設驗證 SSL
```

**優點**:
- ✅ 預設啟用 SSL 憑證驗證
- ✅ 允許在測試環境中關閉（但需明確配置）

---

## 8. 依賴項安全 ⚠️

### 8.1 已知依賴項

**主要依賴項**:
- `homeassistant>=2024.1.0,<2025.0.0`
- `aiohttp` (由 Home Assistant 管理)
- `pytest`, `black`, `isort`, `flake8`, `mypy` (開發依賴)

### 8.2 安全建議

1. **定期更新依賴項** ⚠️
   - 建議使用 `safety` 工具掃描已知漏洞
   - 建議使用 Dependabot 自動偵測漏洞

2. **Python 版本升級** ⚠️
   ```toml
   # requirements-dev.txt
   # Note: Upgrading to Python 3.13 + HA 2025.2+ will resolve security vulnerabilities
   homeassistant>=2024.1.0,<2025.0.0
   ```
   - 已知需要升級到較新版本解決安全漏洞
   - 建議規劃升級路徑

3. **新增安全掃描工具**
   ```bash
   pip install safety bandit
   safety check
   bandit -r custom_components/
   ```

---

## 9. 特定風險與建議

### 9.1 高優先級 ⚠️

#### 1. X-Forwarded-For 偽造風險 ⚠️

**位置**: [auth.py](custom_components/smartly_bridge/auth.py#L210-L225)

**風險**: 
如果直接暴露在公網而非受信任的反向代理後，攻擊者可以偽造 X-Forwarded-For 標頭繞過 IP 白名單。

**建議**:
```python
def get_client_ip(request: web.Request, trust_proxy: bool = False) -> str:
    """Get client IP from request.
    
    Args:
        request: aiohttp request
        trust_proxy: If True, trust X-Forwarded-For header.
                    Should only be True when behind trusted reverse proxy.
    """
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    
    # Direct connection
    if request.transport:
        peername = request.transport.get_extra_info("peername")
        if peername:
            return peername[0]
    
    return ""
```

並在配置中新增 `trust_proxy` 選項。

#### 2. Webhook URL 強制 HTTPS ⚠️

**建議**: 在 `config_flow.py` 中新增驗證：

```python
def _validate_webhook_url(self, url: str) -> tuple[bool, str]:
    """Validate webhook URL security.
    
    Returns:
        (is_valid, error_key)
    """
    if not url or not url.strip():
        return True, ""
    
    url = url.strip()
    
    # Must be HTTP(S)
    if not url.startswith(("http://", "https://")):
        return False, "invalid_url_scheme"
    
    # HTTPS required except for local testing
    if url.startswith("http://"):
        # Allow localhost for testing
        parsed = urlparse(url)
        if parsed.hostname not in ["localhost", "127.0.0.1", "::1"]:
            return False, "https_required"
    
    return True, ""
```

### 9.2 中優先級 ⚠️

#### 3. 相機認證改進 ⚠️

**建議**:
1. 在文件中明確說明相機 URL 必須使用 HTTPS
2. 新增配置驗證警告
3. 考慮支援更安全的認證方式（Token、Digest Auth）

```python
def _validate_camera_config(self, config: CameraConfig) -> None:
    """Validate camera configuration security."""
    if config.username and config.password:
        if config.snapshot_url and not config.snapshot_url.startswith("https://"):
            _LOGGER.warning(
                "Camera %s uses Basic Auth over HTTP. "
                "Credentials will be transmitted in plaintext! "
                "Consider using HTTPS.",
                config.entity_id
            )
```

#### 4. Rate Limiter 持久化 ⚠️

**目前問題**: Rate limiter 使用記憶體存儲，重啟後重置。

**建議**: 考慮使用 Redis 或檔案持久化，防止惡意客戶端透過重啟繞過限制。

#### 5. Nonce Cache 持久化 ⚠️

**目前問題**: Nonce cache 使用記憶體存儲，重啟後重置。

**風險評估**: 
- 風險相對較低，因為有時間戳驗證（30 秒容差）
- 理論上攻擊者需要在重啟後的 30 秒內重放請求

**建議**: 
- 如果非常擔心，可以考慮持久化 nonce
- 或者在啟動時加入額外的時間戳檢查邏輯

### 9.3 低優先級 ℹ️

#### 6. 新增 Security Headers

**建議**: 在 HTTP 回應中新增安全標頭：

```python
def add_security_headers(response: web.Response) -> web.Response:
    """Add security headers to response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

#### 7. CORS 配置審查

確認是否需要 CORS，如果不需要，確保未啟用。

#### 8. 增加安全測試

**建議新增測試**:
- 重放攻擊測試
- 時序攻擊測試
- 速率限制測試
- IP 白名單繞過測試
- 無效簽章測試

---

## 10. 合規性檢查

### 10.1 OWASP Top 10 (2021) 對照

| 風險 | 狀態 | 說明 |
|------|------|------|
| A01: Broken Access Control | ✅ 良好 | 實作完善的 ACL 和白名單機制 |
| A02: Cryptographic Failures | ✅ 良好 | 使用 HMAC-SHA256 和 secrets 模組 |
| A03: Injection | ✅ 良好 | 無 SQL/命令/程式碼注入風險 |
| A04: Insecure Design | ✅ 良好 | 安全設計，預設拒絕原則 |
| A05: Security Misconfiguration | ⚠️ 注意 | 建議強制 HTTPS |
| A06: Vulnerable Components | ⚠️ 注意 | 需定期更新依賴項 |
| A07: Authentication Failures | ✅ 良好 | HMAC 認證、nonce、速率限制 |
| A08: Software and Data Integrity | ✅ 良好 | 簽章驗證、無反序列化漏洞 |
| A09: Logging & Monitoring | ✅ 良好 | 完整的審計日誌 |
| A10: SSRF | ✅ 良好 | Webhook URL 由管理員配置 |

### 10.2 CWE 常見弱點檢查

| CWE ID | 弱點名稱 | 狀態 |
|--------|---------|------|
| CWE-89 | SQL Injection | ✅ N/A（不使用資料庫）|
| CWE-78 | OS Command Injection | ✅ 無風險 |
| CWE-79 | Cross-site Scripting (XSS) | ✅ API 不返回 HTML |
| CWE-306 | Missing Authentication | ✅ 所有端點需認證 |
| CWE-307 | Improper Authentication | ✅ 良好 |
| CWE-327 | Broken Crypto | ✅ 使用標準演算法 |
| CWE-352 | CSRF | ✅ 使用 HMAC 簽章 |
| CWE-502 | Deserialization | ✅ 僅使用 JSON |
| CWE-798 | Hard-coded Credentials | ✅ 無硬編碼 |

---

## 11. 建議改進措施

### 立即執行（高優先級）⚠️

1. **新增 Webhook URL HTTPS 驗證**
   ```python
   # In config_flow.py
   if webhook_url.startswith("http://") and not is_localhost(webhook_url):
       errors[CONF_WEBHOOK_URL] = "https_required"
   ```

2. **新增 X-Forwarded-For 信任設定**
   ```python
   # In const.py
   CONF_TRUST_PROXY = "trust_proxy"
   
   # In auth.py
   def get_client_ip(request, trust_proxy=False):
       if trust_proxy:
           # Only then trust X-Forwarded-For
   ```

3. **相機 URL 安全警告**
   ```python
   # In camera.py
   if config.username and not config.snapshot_url.startswith("https://"):
       _LOGGER.warning("Credentials over HTTP - security risk!")
   ```

### 短期執行（1-2 週）⚠️

4. **整合依賴項掃描**
   ```yaml
   # .github/workflows/security.yml
   - name: Run Safety Check
     run: |
       pip install safety
       safety check --json
   ```

5. **新增安全測試**
   - 重放攻擊測試
   - 時序攻擊測試（雖然難以自動化測試）
   - 速率限制測試

6. **新增 Security Headers**
   ```python
   response.headers.update({
       "X-Content-Type-Options": "nosniff",
       "X-Frame-Options": "DENY",
   })
   ```

### 中期執行（1-2 個月）ℹ️

7. **考慮 Rate Limiter 持久化**
   - 使用 Redis 或檔案存儲
   - 防止重啟繞過限制

8. **升級 Python 和 Home Assistant 版本**
   - 解決已知安全漏洞
   - 規劃遷移路徑

9. **新增安全文件**
   - 部署安全指南
   - 安全最佳實踐
   - 安全配置檢查清單

### 長期執行（3-6 個月）ℹ️

10. **考慮外部安全審計**
    - 請專業安全團隊審查
    - 滲透測試

11. **實作更進階的認證機制**
    - OAuth 2.0 支援
    - 相機的 Digest Authentication

12. **安全監控與告警**
    - 異常請求偵測
    - 失敗登入告警
    - 速率限制觸發告警

---

## 12. 結論

### 12.1 整體評價

Smartly Bridge 整合在安全性方面表現**良好** ✅，展現了以下優點：

**主要優勢**:
1. ✅ 完善的 HMAC 身份驗證機制，使用常數時間比較防止時序攻擊
2. ✅ 實作重放攻擊防護（nonce + 時間戳）
3. ✅ 實作速率限制防止 DoS
4. ✅ 完整的 ACL 系統（實體白名單 + 服務白名單）
5. ✅ 無硬編碼敏感資訊，使用密碼學安全的隨機數生成器
6. ✅ 無常見注入漏洞（SQL、命令、程式碼注入）
7. ✅ 完整的審計日誌
8. ✅ 良好的錯誤處理，不洩露內部細節

**待改進區域**:
1. ⚠️ Webhook URL 應強制使用 HTTPS（非 localhost）
2. ⚠️ X-Forwarded-For 處理需要信任設定選項
3. ⚠️ 相機 Basic Auth over HTTP 的安全警告
4. ⚠️ 依賴項需要定期掃描和更新
5. ⚠️ Rate Limiter 和 Nonce Cache 持久化（可選）

### 12.2 風險等級總結

- **高風險**: 0 個 ✅
- **中風險**: 2 個 ⚠️（Webhook HTTPS、X-Forwarded-For 信任）
- **低風險**: 3 個 ⚠️（相機認證、依賴項更新、持久化）

### 12.3 最終建議

1. **優先處理中風險項目**（預計 1-2 天工作量）
   - 新增 Webhook URL HTTPS 驗證
   - 新增 X-Forwarded-For 信任設定

2. **建立安全維護流程**
   - 整合 Safety 或 Dependabot
   - 定期審查和更新依賴項
   - 每季度進行安全審查

3. **持續改進**
   - 新增安全測試
   - 擴充安全文件
   - 考慮外部審計

**整體而言，這是一個安全設計良好的整合，只需進行少量改進即可達到生產級別的安全標準。** ✅

---

## 13. 附錄

### 13.1 安全檢查清單

供部署前使用：

- [ ] client_secret 已安全生成（至少 32 bytes）
- [ ] client_secret 未出現在版本控制中
- [ ] Webhook URL 使用 HTTPS（非測試環境）
- [ ] IP 白名單已正確配置
- [ ] 僅必要的實體標記為 `smartly`
- [ ] Home Assistant 使用 HTTPS（如果從公網存取）
- [ ] 反向代理正確設定（如使用）
- [ ] 日誌級別適當（不在 DEBUG）
- [ ] 已審查所有配置選項
- [ ] 已測試認證失敗場景
- [ ] 已測試速率限制
- [ ] 定期審查存取日誌

### 13.2 參考資源

- [OWASP Top 10 (2021)](https://owasp.org/Top10/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Home Assistant Security Guidelines](https://developers.home-assistant.io/docs/creating_integration_manifest/#security)

### 13.3 聯絡資訊

如發現安全問題，請參閱 [SECURITY.md](../SECURITY.md) 中的回報流程。

---

## 相關文檔

- **[SECURITY.md](../SECURITY.md)** - 安全政策與漏洞回報流程
- **[Trust Proxy 配置](development/trust-proxy.md)** - 反向代理安全配置
- **[API 安全指南](control/security.md)** - API 使用安全最佳實踐
- **[貢獻指南](../CONTRIBUTING.md)** - 如何安全地貢獻代碼

---

**報告結束** - 祝您安全部署！🔒
