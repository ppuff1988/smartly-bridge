# 安全指南

> **返回**：[控制 API 指南](./README.md)

本文檔說明 Smartly Bridge API 的安全最佳實踐，包含認證機制、IP 白名單、速率限制、ACL 與審計日誌。

---

## 目錄

1. [HMAC 簽名安全](#1-hmac-簽名安全)
2. [時間戳與 Nonce](#2-時間戳與-nonce)
3. [IP 白名單](#3-ip-白名單)
4. [速率限制](#4-速率限制)
5. [HTTPS 使用建議](#5-https-使用建議)
6. [實體標籤控制](#6-實體標籤控制)
7. [審計日誌](#7-審計日誌)
8. [ACL（存取控制清單）](#8-acl存取控制清單)
9. [安全檢查清單](#9-安全檢查清單)

---

## 1. HMAC 簽名安全

### 密鑰管理

| ✅ 應該做 | ❌ 不應該做 |
|----------|-----------|
| 使用強隨機密鑰（至少 32 字元） | 使用弱密碼或常見字串 |
| 定期輪換密鑰 | 長期使用同一組密鑰 |
| 使用環境變數或密鑰管理服務存儲 | 將密鑰硬編碼在程式碼中 |
| 限制密鑰的存取權限 | 透過 GET 參數或 URL 傳遞密鑰 |

### 簽名計算注意事項

| ✅ 應該做 | ❌ 不應該做 |
|----------|-----------|
| 確保 Body JSON 與發送的內容完全一致 | 在簽名計算和發送時使用不同的 JSON 格式 |
| 使用 UTF-8 編碼 | 使用其他編碼 |
| 簽名使用小寫十六進位字串 | 使用大寫或其他格式 |
| 每次請求使用新的 Nonce | 重複使用 Nonce |

---

## 2. 時間戳與 Nonce

### 時間戳驗證

- 伺服器允許時間戳在 **±30 秒**內
- 確保客戶端時間同步（使用 NTP）
- 時間偏移過大會導致所有請求失敗

```bash
# 同步系統時間（Linux/macOS）
sudo ntpdate pool.ntp.org

# 或使用 systemd-timesyncd
sudo timedatectl set-ntp true

# Windows
w32tm /resync
```

### Nonce 防重放

- 每個 Nonce 在 **5 分鐘內只能使用一次**
- 使用 UUID v4 格式
- 伺服器會記錄並檢查 Nonce

```python
import uuid

# 每次請求都生成新的 Nonce
nonce = str(uuid.uuid4())
```

---

## 3. IP 白名單

配置 `allowed_cidr` 限制允許的來源 IP：

```yaml
# configuration.yaml
smartly_bridge:
  clients:
    - client_id: ha_abc123
      client_secret: your_secret
      allowed_cidr:
        - "192.168.1.0/24"    # 本地網路
        - "10.0.0.100/32"     # 特定 IP
```

### CIDR 範例

| CIDR | 說明 |
|------|------|
| `192.168.1.0/24` | 192.168.1.0 ~ 192.168.1.255 |
| `10.0.0.100/32` | 僅 10.0.0.100 |
| `0.0.0.0/0` | 所有 IPv4（不建議） |

---

## 4. 速率限制

### 預設配置

- **每分鐘 60 次請求**（可自訂）
- 超過限制將收到 `429 Too Many Requests`

### 自訂配置

```yaml
# configuration.yaml
smartly_bridge:
  rate_limit:
    requests_per_minute: 120  # 預設 60
```

### 指數退避重試

```python
import time

def call_api_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)
            else:
                raise
```

---

## 5. HTTPS 使用建議

| ✅ 應該做 | ❌ 不應該做 |
|----------|-----------|
| 生產環境必須使用 HTTPS | 在公網上使用 HTTP |
| 使用有效的 SSL/TLS 憑證 | 使用過期或自簽憑證 |
| 啟用 HSTS | 允許 HTTP 降級 |

### 配置範例

```yaml
# configuration.yaml
http:
  ssl_certificate: /path/to/fullchain.pem
  ssl_key: /path/to/privkey.pem
```

---

## 6. 實體標籤控制

只有標記為 `smartly` 的實體才能被控制。

### 在 Home Assistant 介面設定

1. 設定 → 實體
2. 選擇要開放的實體
3. 點選「標籤」
4. 新增或選擇 `smartly` 標籤

### 透過 YAML 設定

```yaml
# configuration.yaml
label:
  smartly:
    name: Smartly 可控制
    icon: mdi:api
```

---

## 7. 審計日誌

所有 API 請求都會記錄在審計日誌中。

### 啟用審計日誌

```yaml
# configuration.yaml
smartly_bridge:
  audit:
    enabled: true
    level: info  # debug, info, warning, error
```

### 查看日誌

```bash
# 檢視 Home Assistant 日誌
tail -f /config/home-assistant.log | grep smartly
```

### 日誌內容範例

```
2025-12-27 10:30:45 INFO smartly_bridge.audit: 
  client_id=ha_abc123 
  action=turn_on 
  entity_id=light.bedroom 
  actor_user_id=u_123 
  actor_role=tenant 
  source_ip=192.168.1.100 
  result=success
```

---

## 8. ACL（存取控制清單）

設定細緻化的權限控制：

```yaml
# configuration.yaml
smartly_bridge:
  acl:
    # 允許所有角色控制燈光
    - entity_id: "light.*"
      allowed_actions: ["turn_on", "turn_off"]
      allowed_roles: ["admin", "tenant"]
    
    # 僅管理員可控制空調
    - entity_id: "climate.*"
      allowed_actions: ["set_temperature"]
      allowed_roles: ["admin"]
      
    # 禁止所有解鎖操作
    - entity_id: "lock.*"
      allowed_actions: ["unlock"]
      denied: true
```

### ACL 規則說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `entity_id` | string | 實體 ID 模式（支援 `*` 萬用字元） |
| `allowed_actions` | array | 允許的動作列表 |
| `allowed_roles` | array | 允許的角色列表 |
| `denied` | boolean | 是否拒絕（優先於允許規則） |

---

## 9. 安全檢查清單

部署前確認：

- [ ] 已設定強隨機的 `client_secret`
- [ ] 已配置 IP 白名單或防火牆規則
- [ ] 生產環境使用 HTTPS
- [ ] 已啟用審計日誌
- [ ] 已設定實體標籤控制
- [ ] 已配置適當的 ACL 規則
- [ ] 已測試速率限制機制
- [ ] 已同步伺服器時間（NTP）
- [ ] 已定期檢查日誌異常活動
- [ ] 已制定密鑰輪換計畫

---

## 📚 相關文檔

- **[API 基礎與認證](./api-basics.md)** - 端點資訊與簽名計算
- **[故障排除](./troubleshooting.md)** - 常見問題與解決方案
- **[SECURITY.md](../../SECURITY.md)** - 專案安全政策

---

**返回**：[控制 API 指南](./README.md)
