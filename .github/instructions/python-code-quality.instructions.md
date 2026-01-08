---
applyTo: '*.py'
description: 'Python 程式碼品質與可讀性指南，專注於漸進式改善與低風險重構'
---

# Python 程式碼品質指南

## 你的任務

作為 GitHub Copilot，協助開發者以**低風險、漸進式**的方式提升程式碼可讀性與品質。優先保持現有行為不變，僅改善內部實作。

## 核心原則

### 1. 安全重構優先

- **不改變外部行為**：任何重構都必須保持 API 相容性
- **小步前進**：每次只做一件事，便於 review 和 rollback
- **先有測試**：重構前確認該程式碼已有足夠測試覆蓋

### 2. 可讀性標準

#### 函數與方法

- **單一職責**：一個函數只做一件事
- **長度限制**：理想 10-20 行，最多不超過 40 行
- **參數數量**：不超過 5 個參數，過多時考慮使用 dataclass 或 TypedDict
- **巢狀深度**：不超過 3 層，使用提早返回（early return）減少巢狀

#### 命名規範

```python
# ✅ 良好命名
def calculate_snapshot_expiry_time(ttl_seconds: float) -> float:
    ...

async def fetch_camera_image(entity_id: str) -> bytes:
    ...

# ❌ 不良命名
def calc(t):  # 過於簡短
    ...

def do_stuff():  # 不具描述性
    ...
```

#### Docstring 標準（Google 風格）

```python
async def get_snapshot(
    self,
    entity_id: str,
    force_refresh: bool = False,
) -> CameraSnapshot | None:
    """取得相機快照，優先使用快取。

    Args:
        entity_id: 相機實體 ID，格式為 camera.<name>
        force_refresh: 是否強制重新取得快照，忽略快取

    Returns:
        快照物件，若相機不存在或取得失敗則返回 None

    Raises:
        CameraConnectionError: 連線相機時發生錯誤
    """
```

### 3. 類型提示要求

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# ✅ 完整類型提示
async def process_data(
    hass: HomeAssistant,
    data: dict[str, Any],
    timeout: float = 30.0,
) -> list[str]:
    ...

# ✅ 使用 | 而非 Union（Python 3.10+）
def get_value(key: str) -> str | None:
    ...
```

### 4. 錯誤處理

```python
# ✅ 具體的異常處理
try:
    response = await session.get(url)
except aiohttp.ClientError as err:
    _LOGGER.warning("連線失敗: %s", err)
    return None
except asyncio.TimeoutError:
    _LOGGER.warning("請求逾時: %s", url)
    return None

# ❌ 避免裸 except
try:
    ...
except:  # 不要這樣做
    pass
```

### 5. 常數管理

```python
# ✅ 提取魔術數字為常數（放在 const.py）
from .const import CACHE_TTL, MAX_RETRY_COUNT, DEFAULT_TIMEOUT

# ❌ 避免魔術數字
if retry_count > 3:  # 3 是什麼意思？
    ...
```

## 漸進式改善策略

### 階段 1：文件化（最低風險）

- 添加 docstring
- 添加類型提示
- 添加行內註解解釋複雜邏輯

### 階段 2：命名改善（低風險）

- 重新命名變數使其更具描述性
- 提取魔術數字為常數

### 階段 3：結構改善（中等風險）

- 使用 Extract Method 拆分大函數
- 減少巢狀深度
- 簡化條件判斷

### 階段 4：架構改善（較高風險，需充分測試）

- 引入設計模式
- 重構類別結構

## Logging 最佳實作

```python
import logging

_LOGGER = logging.getLogger(__name__)

# ✅ 使用正確的日誌等級
_LOGGER.debug("開始處理快照: entity_id=%s", entity_id)
_LOGGER.info("相機管理器已啟動")
_LOGGER.warning("快取已過期，重新取得: %s", entity_id)
_LOGGER.error("無法連線到相機: %s, 錯誤: %s", entity_id, err)

# ✅ 使用 % 格式化而非 f-string（延遲評估）
_LOGGER.debug("處理資料: %s", data)  # ✅
_LOGGER.debug(f"處理資料: {data}")   # ❌ 總是會執行格式化
```

## 程式碼格式化

本專案使用以下工具：

- **Black**：程式碼格式化（行長度 100）
- **isort**：import 排序
- **Flake8**：程式碼檢查
- **MyPy**：類型檢查

執行格式化：
```bash
black --line-length 100 .
isort .
flake8
mypy .
```

## Copilot 協助項目

請協助我：

1. **添加文件**：為缺少 docstring 的函數添加 Google 風格文件
2. **類型提示**：補充遺漏的類型提示
3. **安全重構**：在不改變行為的前提下改善可讀性
4. **命名改善**：建議更具描述性的命名
5. **簡化邏輯**：使用提早返回減少巢狀

---

<!-- End of Python Code Quality Instructions -->
