# 修正 Device Class Metadata 提取邏輯

## 問題描述

在查詢歷史記錄時，metadata 中的 `device_class` 始終為 `null`，即使該 sensor 實際上有 device_class 屬性。這導致前端無法正確顯示適當的單位和視覺化配置。

### 原始問題範例

```json
{
    "entity_id": "sensor.micro_wake_word_pzem004t_pzem_004t_v3_voltage",
    "history": [
        {
            "state": 113.9,
            "last_changed": "2026-01-12T04:57:50.621554+00:00",
            "last_updated": "2026-01-12T04:57:50.621554+00:00",
            "attributes": {}
        },
        {
            "state": 114.0,
            "last_changed": "2026-01-12T04:57:32.545598+00:00",
            "last_updated": "2026-01-12T04:57:32.545598+00:00"
        }
        // ... 其他記錄也沒有 attributes
    ],
    "metadata": {
        "domain": "sensor",
        "device_class": null,  // ❌ 應該是 "voltage"
        "unit_of_measurement": "",  // ❌ 應該是 "V"
        "friendly_name": "sensor.micro_wake_word_pzem004t_pzem_004t_v3_voltage",
        "is_numeric": true,
        "visualization": {
            "type": "chart",
            "chart_type": "line",
            "color": "#607D8B",
            "show_points": true,
            "interpolation": "linear"
        },
        "decimal_places": 2
    }
}
```

## 根本原因

歷史記錄查詢時，為了效能考量，Home Assistant 不會為每個 state 都保存完整的 attributes：

1. **第一筆記錄**：通常包含 `attributes` 欄位，但可能是空的 `{}`
2. **後續記錄**：為了節省空間，通常省略 `attributes` 欄位（除非有變更）
3. **Cursor pagination**：分頁查詢時，每頁的第一筆都可能沒有完整 attributes

原有的 `_get_entity_metadata` 函數只從傳入的 `first_state` 取得 device_class，如果該 state 的 attributes 是空的，就會得到 `null`。

## 解決方案

實作三層 fallback 機制來獲取 device_class：

### 1. 從第一個 state 的 attributes 獲取
```python
attributes = first_state.get("attributes", {})
device_class = attributes.get("device_class")
```

### 2. 從歷史記錄中搜尋第一個有 device_class 的 state
```python
if device_class is None and all_states:
    for state in all_states:
        state_attrs = state.get("attributes", {})
        if state_attrs.get("device_class"):
            device_class = state_attrs.get("device_class")
            if not unit:
                unit = state_attrs.get("unit_of_measurement", "")
            break
```

### 3. 從 Home Assistant 的當前狀態獲取（最可靠）
```python
if device_class is None and hass is not None:
    current_state = hass.states.get(entity_id)
    if current_state and current_state.attributes:
        device_class = current_state.attributes.get("device_class")
        if not unit:
            unit = current_state.attributes.get("unit_of_measurement", "")
        if "friendly_name" not in attributes:
            attributes["friendly_name"] = current_state.attributes.get("friendly_name")
```

## 程式碼變更

### 修改函數簽名

```python
def _get_entity_metadata(
    entity_id: str,
    first_state: dict[str, Any],
    all_states: list[dict[str, Any]] | None = None,  # 新增
    hass: HomeAssistant | None = None,  # 新增
) -> dict[str, Any]:
```

### 更新調用位置

所有調用 `_get_entity_metadata` 的地方都需要傳入：
- `all_states`: 完整的 states 列表（格式化過的）
- `hass`: View 的 `self.hass` 實例

```python
# 在 _format_history_response 中
formatted_states = [_format_state(s, include_attributes=True) for s in entity_states]
metadata = _get_entity_metadata(
    entity_id,
    _format_state(entity_states[0]),
    all_states=formatted_states,
    hass=self.hass  # 新增
)
```

## 測試覆蓋

新增 8 個測試案例來驗證功能：

1. ✅ `test_device_class_from_first_state` - 從第一個 state 獲取
2. ✅ `test_device_class_from_later_state_when_first_empty` - 從後續 state 獲取
3. ✅ `test_device_class_none_when_not_found` - 找不到時返回 None
4. ✅ `test_unit_fallback_from_later_state` - unit_of_measurement fallback
5. ✅ `test_no_all_states_provided` - 沒有提供 all_states 時的行為
6. ✅ `test_numeric_sensor_with_device_class` - 數值型 sensor 的視覺化
7. ✅ `test_fallback_to_current_state` - 從當前狀態獲取（核心功能）
8. ✅ `test_no_current_state_available` - 實體已刪除時的處理

## 效能考量

### 為什麼不每次都查詢當前狀態？

1. **優先使用歷史數據**：如果歷史記錄中有 device_class，直接使用，避免額外查詢
2. **Fallback 機制**：只有在歷史記錄中找不到時，才訪問 `hass.states`
3. **格式化快取**：`formatted_states` 只在需要時建立一次

### 時間複雜度

- **最佳情況**：O(1) - 第一個 state 就有 device_class
- **平均情況**：O(n) - 需要遍歷 n 個 states（通常 n ≤ 10）
- **最差情況**：O(n) + O(1) - 遍歷歷史 + 查詢當前狀態

## 向後相容性

✅ **完全相容**：
- 新增的參數都是可選的（default = None）
- 不影響現有的調用方式
- 所有現有測試都通過

## 相關檔案

- `/workspace/custom_components/smartly_bridge/views/history.py` - 核心邏輯
- `/workspace/tests/test_metadata_device_class.py` - 新增的測試
- `/workspace/tests/test_history_views.py` - 現有測試（全部通過）

## 建議的後續優化

1. **快取 device_class**：可考慮在 View 層級快取 entity_id → device_class 的映射
2. **Batch 查詢**：批次查詢時，可以一次性獲取所有實體的當前狀態
3. **監控日誌**：新增 debug 日誌記錄 fallback 到哪一層，幫助優化

## 總結

這個修正確保了即使歷史記錄中的 attributes 不完整，也能從 Home Assistant 的當前狀態正確獲取 `device_class`、`unit_of_measurement` 和 `friendly_name`，提供完整且正確的 metadata 給前端使用。
