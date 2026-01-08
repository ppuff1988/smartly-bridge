---
applyTo: 'tests/*.py,test_*.py'
description: 'Python 測試撰寫最佳實作指南，使用 pytest 框架，專注於提升測試覆蓋率'
---

# Python 測試最佳實作指南

## 你的任務

作為 GitHub Copilot，協助開發者撰寫高品質的測試程式碼，以**漸進式**提升測試覆蓋率。目標是從目前的覆蓋率逐步提升，優先覆蓋關鍵業務邏輯和錯誤處理路徑。

## 測試框架與工具

本專案使用：

- **pytest**：測試框架
- **pytest-asyncio**：異步測試支援
- **pytest-cov**：覆蓋率報告
- **unittest.mock**：Mock 和 Patch

## 測試撰寫原則

### 1. AAA 模式（Arrange-Act-Assert）

```python
async def test_get_snapshot_returns_cached_when_valid():
    """測試取得快照時優先返回有效快取。"""
    # Arrange（準備）
    manager = CameraManager(mock_hass)
    cached_snapshot = CameraSnapshot(
        entity_id="camera.test",
        image_data=b"cached_data",
        content_type="image/jpeg",
        timestamp=time.time(),
        etag="abc123",
    )
    manager._snapshot_cache["camera.test"] = cached_snapshot

    # Act（執行）
    result = await manager.get_snapshot("camera.test")

    # Assert（驗證）
    assert result == cached_snapshot
    assert result.image_data == b"cached_data"
```

### 2. 測試命名規範

```python
# 格式：test_<被測功能>_<情境>_<預期結果>

def test_snapshot_is_expired_when_past_ttl():
    """快照超過 TTL 時應該被判定為過期。"""
    ...

def test_get_snapshot_returns_none_when_camera_not_found():
    """相機不存在時應返回 None。"""
    ...

async def test_fetch_image_raises_timeout_when_server_slow():
    """伺服器回應過慢時應拋出 TimeoutError。"""
    ...
```

### 3. 單一斷言原則

每個測試專注於驗證一個行為：

```python
# ✅ 良好：每個測試驗證一件事
def test_snapshot_etag_is_generated_from_content():
    snapshot = create_snapshot(image_data=b"test")
    assert snapshot.etag == hashlib.md5(b"test").hexdigest()

def test_snapshot_timestamp_is_current_time():
    before = time.time()
    snapshot = create_snapshot()
    after = time.time()
    assert before <= snapshot.timestamp <= after

# ❌ 避免：一個測試驗證太多事情
def test_snapshot_properties():
    snapshot = create_snapshot(image_data=b"test")
    assert snapshot.etag == hashlib.md5(b"test").hexdigest()
    assert snapshot.timestamp > 0
    assert snapshot.content_type == "image/jpeg"
    assert snapshot.entity_id.startswith("camera.")
```

### 4. 測試分類標記

```python
import pytest

@pytest.mark.unit
def test_simple_calculation():
    """單元測試：快速、無外部依賴。"""
    ...

@pytest.mark.integration
async def test_camera_connection():
    """整合測試：涉及多個元件互動。"""
    ...

@pytest.mark.slow
async def test_large_data_processing():
    """慢速測試：執行時間較長。"""
    ...
```

執行特定類型測試：
```bash
pytest -m unit           # 只執行單元測試
pytest -m "not slow"     # 排除慢速測試
```

## 測試覆蓋率策略

### 優先順序（由高到低）

1. **業務邏輯**：核心功能的正確性
2. **錯誤處理**：異常情況的處理
3. **邊界條件**：空值、極端值、邊界值
4. **正常路徑**：一般使用情境

### 覆蓋邊界條件

```python
class TestCameraManager:
    """CameraManager 測試類別。"""

    # 正常情況
    async def test_get_snapshot_success(self):
        """成功取得快照。"""
        ...

    # 邊界條件：空值
    async def test_get_snapshot_with_empty_entity_id(self):
        """空的 entity_id 應返回 None。"""
        result = await manager.get_snapshot("")
        assert result is None

    # 邊界條件：不存在
    async def test_get_snapshot_camera_not_registered(self):
        """未註冊的相機應返回 None。"""
        result = await manager.get_snapshot("camera.nonexistent")
        assert result is None

    # 錯誤處理：網路錯誤
    async def test_get_snapshot_handles_connection_error(self):
        """連線錯誤時應記錄警告並返回 None。"""
        with patch.object(manager, "_fetch_image", side_effect=aiohttp.ClientError):
            result = await manager.get_snapshot("camera.test")
        assert result is None

    # 錯誤處理：逾時
    async def test_get_snapshot_handles_timeout(self):
        """請求逾時時應記錄警告並返回 None。"""
        with patch.object(manager, "_fetch_image", side_effect=asyncio.TimeoutError):
            result = await manager.get_snapshot("camera.test")
        assert result is None
```

## Mock 與 Patch 最佳實作

### 使用 Fixture

```python
@pytest.fixture
def mock_hass():
    """建立 Mock Home Assistant 實例。"""
    hass = MagicMock()
    hass.data = {}
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass

@pytest.fixture
def camera_manager(mock_hass):
    """建立已初始化的 CameraManager。"""
    return CameraManager(mock_hass)
```

### 使用 patch

```python
from unittest.mock import patch, AsyncMock

async def test_fetch_image_calls_correct_url(camera_manager):
    """確認取得圖片時使用正確的 URL。"""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.read = AsyncMock(return_value=b"image_data")

    with patch.object(
        camera_manager._session,
        "get",
        return_value=mock_response,
    ) as mock_get:
        await camera_manager._fetch_image("http://camera.local/snapshot")

    mock_get.assert_called_once_with(
        "http://camera.local/snapshot",
        timeout=ANY,
    )
```

### 使用 pytest.mark.parametrize

```python
@pytest.mark.parametrize(
    "ttl,expected_expired",
    [
        (0, True),      # 立即過期
        (30, False),    # 未過期
        (-1, True),     # 負數 TTL
        (3600, False),  # 長 TTL
    ],
)
def test_snapshot_expiration_with_various_ttl(ttl, expected_expired):
    """測試不同 TTL 設定下的過期判定。"""
    snapshot = CameraSnapshot(
        entity_id="camera.test",
        image_data=b"test",
        content_type="image/jpeg",
        timestamp=time.time() - 60,  # 1 分鐘前
        etag="abc",
    )
    assert snapshot.is_expired(ttl=ttl) == expected_expired
```

## 異步測試

```python
import pytest

# pytest.ini 已設定 asyncio_mode = "auto"
# 不需要手動添加 @pytest.mark.asyncio

async def test_async_operation():
    """異步測試範例。"""
    result = await some_async_function()
    assert result is not None

async def test_concurrent_operations():
    """測試並行操作。"""
    results = await asyncio.gather(
        operation_1(),
        operation_2(),
        operation_3(),
    )
    assert len(results) == 3
```

## 測試輔助函數

建立測試工具函數減少重複：

```python
# tests/helpers.py
def create_snapshot(
    entity_id: str = "camera.test",
    image_data: bytes = b"test_data",
    content_type: str = "image/jpeg",
    timestamp: float | None = None,
    etag: str = "default_etag",
) -> CameraSnapshot:
    """建立測試用快照。"""
    return CameraSnapshot(
        entity_id=entity_id,
        image_data=image_data,
        content_type=content_type,
        timestamp=timestamp or time.time(),
        etag=etag,
    )
```

## 執行測試

```bash
# 執行所有測試
pytest

# 執行特定檔案
pytest tests/test_camera.py

# 顯示覆蓋率
pytest --cov=custom_components/smartly_bridge --cov-report=html

# 只執行失敗的測試
pytest --lf

# 詳細輸出
pytest -v --tb=short
```

## 覆蓋率目標

| 模組 | 目前覆蓋率 | 目標覆蓋率 |
|------|-----------|-----------|
| 整體 | 76% | 85% |
| 核心邏輯 | - | 90% |
| 錯誤處理 | - | 80% |

## Copilot 協助項目

請協助我：

1. **分析覆蓋率缺口**：找出未被測試的程式碼路徑
2. **撰寫單元測試**：為特定函數撰寫完整測試
3. **覆蓋邊界條件**：補充邊界值和錯誤處理測試
4. **重構測試**：使用 parametrize 減少重複
5. **建立 Fixture**：建立可重用的測試 fixture

---

<!-- End of Python Testing Instructions -->
