---
applyTo: 'custom_components/**/*.py'
description: 'Home Assistant 整合開發指南，涵蓋最佳實作與常見模式'
---

# Home Assistant 整合開發指南

## 你的任務

作為 GitHub Copilot，協助開發者遵循 Home Assistant 整合開發最佳實作，確保程式碼品質、安全性和相容性。

## 整合架構

### 標準目錄結構

```
custom_components/smartly_bridge/
├── __init__.py          # 整合入口點
├── config_flow.py       # 配置流程
├── const.py             # 常數定義
├── manifest.json        # 整合描述檔
├── strings.json         # 翻譯字串
├── translations/        # 多語言翻譯
│   ├── en.json
│   └── zh-Hant.json
└── views/               # HTTP 視圖
    ├── __init__.py
    ├── base.py
    ├── camera.py
    ├── control.py
    └── sync.py
```

## 核心模式

### 1. 整合生命週期

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """設定整合 entry。"""
    # 1. 初始化資料結構
    hass.data.setdefault(DOMAIN, {})

    # 2. 建立服務/管理器
    manager = SomeManager(hass, entry)
    await manager.start()

    # 3. 儲存參考
    hass.data[DOMAIN][entry.entry_id] = {
        "manager": manager,
    }

    # 4. 註冊更新監聽器
    entry.async_on_unload(
        entry.add_update_listener(async_reload_entry)
    )

    # 5. 註冊清理
    entry.async_on_unload(manager.stop)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸載整合 entry。"""
    # 清理資源
    if data := hass.data[DOMAIN].pop(entry.entry_id, None):
        manager = data.get("manager")
        if manager:
            await manager.stop()

    return True
```

### 2. Config Flow

```python
class SmartlyBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """配置流程處理。"""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """處理使用者輸入步驟。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            # 驗證輸入
            if not self._validate_input(user_input):
                errors["base"] = "invalid_input"
            else:
                # 建立 entry
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA_USER,
            errors=errors,
        )
```

### 3. 資源管理

```python
class ResourceManager:
    """管理需要清理的資源。"""

    def __init__(self, hass: HomeAssistant) -> None:
        """初始化管理器。"""
        self.hass = hass
        self._session: aiohttp.ClientSession | None = None
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """啟動管理器。"""
        self._session = aiohttp.ClientSession()
        # 啟動背景任務
        self._tasks.append(
            asyncio.create_task(self._background_worker())
        )

    async def stop(self) -> None:
        """停止管理器並清理資源。"""
        # 取消所有任務
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        # 關閉 session
        if self._session:
            await self._session.close()
            self._session = None
```

## 安全性最佳實作

### 1. 敏感資訊處理

```python
# ✅ 使用 secrets.yaml 或環境變數
CONF_API_KEY = "api_key"  # 在 config_flow 中處理

# ❌ 永不硬編碼
API_KEY = "sk-12345"  # 絕對不要這樣做

# 日誌中隱藏敏感資訊
_LOGGER.debug("連線到 API: %s", mask_sensitive(api_url))
```

### 2. 輸入驗證

```python
def validate_entity_id(entity_id: str) -> bool:
    """驗證 entity_id 格式。"""
    if not entity_id:
        return False
    if not isinstance(entity_id, str):
        return False
    # 格式: domain.name
    parts = entity_id.split(".", 1)
    if len(parts) != 2:
        return False
    return all(part.replace("_", "").isalnum() for part in parts)


def validate_cidr(cidr: str) -> bool:
    """驗證 CIDR 格式。"""
    try:
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False
```

### 3. HMAC 驗證

```python
import hmac
import hashlib

def verify_hmac_signature(
    payload: bytes,
    signature: str,
    secret: str,
    algorithm: str = "sha256",
) -> bool:
    """驗證 HMAC 簽章。"""
    expected = hmac.new(
        secret.encode(),
        payload,
        getattr(hashlib, algorithm),
    ).hexdigest()

    # 使用 compare_digest 防止時序攻擊
    return hmac.compare_digest(expected, signature)
```

## 非同步最佳實作

### 1. 避免阻塞

```python
# ✅ 使用 executor 執行阻塞操作
result = await hass.async_add_executor_job(
    blocking_io_operation,
    arg1,
    arg2,
)

# ❌ 避免在事件循環中阻塞
result = blocking_io_operation(arg1, arg2)  # 會阻塞
```

### 2. 超時處理

```python
async def fetch_with_timeout(url: str, timeout: float = 10.0) -> bytes | None:
    """帶超時的請求。"""
    try:
        async with asyncio.timeout(timeout):
            async with session.get(url) as response:
                return await response.read()
    except asyncio.TimeoutError:
        _LOGGER.warning("請求逾時: %s", url)
        return None
```

### 3. 並行處理

```python
async def process_all_devices(devices: list[str]) -> list[dict]:
    """並行處理所有裝置。"""
    tasks = [process_device(device) for device in devices]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 過濾成功結果
    return [r for r in results if not isinstance(r, Exception)]
```

## 日誌最佳實作

```python
import logging

_LOGGER = logging.getLogger(__name__)

# 使用適當的日誌等級
_LOGGER.debug("詳細診斷資訊: %s", details)
_LOGGER.info("整合已成功設定")
_LOGGER.warning("連線重試: 第 %d 次", retry_count)
_LOGGER.error("無法連線到裝置: %s", device_id)
_LOGGER.exception("未預期的錯誤")  # 自動包含堆疊追蹤

# 稽核日誌
def log_integration_event(
    logger: logging.Logger,
    event_type: str,
    details: str,
) -> None:
    """記錄整合事件。"""
    logger.info("[%s] %s", event_type, details)
```

## 常數管理（const.py）

```python
"""整合常數定義。"""

DOMAIN = "smartly_bridge"

# 配置鍵
CONF_INSTANCE_ID = "instance_id"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_WEBHOOK_URL = "webhook_url"
CONF_ALLOWED_CIDRS = "allowed_cidrs"

# 預設值
DEFAULT_TIMEOUT = 30
DEFAULT_CACHE_TTL = 300

# 限制
RATE_LIMIT = 100
RATE_WINDOW = 60
MAX_RETRY_COUNT = 3

# 相機相關
CAMERA_CACHE_TTL = 30
CAMERA_SNAPSHOT_TIMEOUT = 10
CAMERA_STREAM_TIMEOUT = 30
CAMERA_STREAM_CHUNK_SIZE = 8192
```

## 翻譯

### strings.json

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Configure Smartly Bridge",
        "data": {
          "instance_id": "Instance ID",
          "client_id": "Client ID"
        }
      }
    },
    "error": {
      "invalid_auth": "Invalid authentication",
      "cannot_connect": "Cannot connect to server"
    }
  }
}
```

### 繁體中文翻譯 (translations/zh-Hant.json)

```json
{
  "config": {
    "step": {
      "user": {
        "title": "設定 Smartly Bridge",
        "data": {
          "instance_id": "實例 ID",
          "client_id": "用戶端 ID"
        }
      }
    },
    "error": {
      "invalid_auth": "認證無效",
      "cannot_connect": "無法連線至伺服器"
    }
  }
}
```

## 測試模式

### Mock Home Assistant

```python
@pytest.fixture
def mock_hass():
    """建立 Mock Home Assistant 實例。"""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.async_add_executor_job = AsyncMock(
        side_effect=lambda func, *args: func(*args)
    )
    return hass
```

### Mock Config Entry

```python
@pytest.fixture
def mock_config_entry():
    """建立 Mock ConfigEntry。"""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        CONF_INSTANCE_ID: "test_instance",
        CONF_CLIENT_ID: "test_client",
        CONF_CLIENT_SECRET: "test_secret",
    }
    entry.entry_id = "test_entry_id"
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    entry.async_on_unload = MagicMock()
    return entry
```

## Copilot 協助項目

請協助我：

1. **遵循 HA 模式**：確保程式碼符合 Home Assistant 開發規範
2. **資源管理**：正確處理生命週期和清理
3. **安全審查**：檢查敏感資訊處理和輸入驗證
4. **非同步最佳化**：避免阻塞和正確處理超時
5. **翻譯支援**：維護多語言翻譯檔案

---

<!-- End of Home Assistant Integration Instructions -->
