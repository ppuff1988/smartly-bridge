# 設備類型控制

> **返回**：[控制 API 指南](./README.md)

本文檔說明 9 種核心設備類型的控制方式、支援的動作與參數。

---

## 目錄

1. [Switch（開關）](#1-switch開關)
2. [Light（燈光）](#2-light燈光)
3. [Cover（窗簾/捲簾/車庫門）](#3-cover窗簾捲簾車庫門)
4. [Climate（空調/恆溫器/暖氣）](#4-climate空調恆溫器暖氣)
5. [Fan（風扇）](#5-fan風扇)
6. [Lock（門鎖）](#6-lock門鎖)
7. [Scene（場景）](#7-scene場景)
8. [Script（腳本）](#8-script腳本)
9. [Automation（自動化）](#9-automation自動化)

---

## 1. Switch（開關）

**適用設備**：智慧插座、電源開關、繼電器模組等

**領域（Domain）**：`switch`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `turn_on` | 開啟 |
| `turn_off` | 關閉 |
| `toggle` | 切換狀態 |

### 範例

#### 開啟開關
```json
{
  "entity_id": "switch.living_room_light",
  "action": "turn_on",
  "service_data": {}
}
```

#### 關閉開關
```json
{
  "entity_id": "switch.living_room_light",
  "action": "turn_off",
  "service_data": {}
}
```

#### 切換開關
```json
{
  "entity_id": "switch.living_room_light",
  "action": "toggle",
  "service_data": {}
}
```

---

## 2. Light（燈光）

**適用設備**：智慧燈泡、LED 燈條、調光器、RGB 燈等

**領域（Domain）**：`light`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `turn_on` | 開啟（可帶參數） |
| `turn_off` | 關閉 |
| `toggle` | 切換狀態 |

### 參數說明

| 參數 | 類型 | 範圍 | 說明 |
|------|------|------|------|
| `brightness` | integer | 0-255 | 亮度值，0 為最暗，255 為最亮 |
| `rgb_color` | array | [0-255, 0-255, 0-255] | RGB 顏色，例如 [255, 0, 0] 為紅色 |
| `color_temp` | integer | 153-500 | 色溫（mireds），153 為冷白光，500 為暖黃光 |
| `kelvin` | integer | 2000-6500 | 色溫（Kelvin） |
| `hs_color` | array | [0-360, 0-100] | HSV 色彩空間的色相和飽和度 |
| `xy_color` | array | [0-1, 0-1] | CIE 1931 色彩空間座標 |
| `transition` | integer | 0+ | 漸變時間（秒） |

### 範例

#### 開啟燈光（基本）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {}
}
```

#### 開啟燈光（設定亮度）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 255
  }
}
```

#### 開啟燈光（設定 RGB 顏色）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 200,
    "rgb_color": [255, 0, 0]
  }
}
```

#### 開啟燈光（設定色溫）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 180,
    "color_temp": 370
  }
}
```

#### 開啟燈光（漸變效果）
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_on",
  "service_data": {
    "brightness": 255,
    "transition": 2
  }
}
```

#### 關閉燈光
```json
{
  "entity_id": "light.bedroom",
  "action": "turn_off",
  "service_data": {}
}
```

---

## 3. Cover（窗簾/捲簾/車庫門）

**適用設備**：電動窗簾、捲簾、百葉窗、車庫門、天窗等

**領域（Domain）**：`cover`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `open_cover` | 打開 |
| `close_cover` | 關閉 |
| `stop_cover` | 停止移動 |
| `set_cover_position` | 設定位置 |

### 參數說明

| 參數 | 類型 | 範圍 | 說明 |
|------|------|------|------|
| `position` | integer | 0-100 | 位置百分比，0=完全關閉，100=完全打開 |
| `tilt_position` | integer | 0-100 | 傾斜角度百分比（適用於百葉窗） |

### 範例

#### 打開窗簾
```json
{
  "entity_id": "cover.living_room_curtain",
  "action": "open_cover",
  "service_data": {}
}
```

#### 關閉窗簾
```json
{
  "entity_id": "cover.living_room_curtain",
  "action": "close_cover",
  "service_data": {}
}
```

#### 停止移動
```json
{
  "entity_id": "cover.living_room_curtain",
  "action": "stop_cover",
  "service_data": {}
}
```

#### 設定位置
```json
{
  "entity_id": "cover.living_room_curtain",
  "action": "set_cover_position",
  "service_data": {
    "position": 50
  }
}
```

---

## 4. Climate（空調/恆溫器/暖氣）

**適用設備**：空調、恆溫器、暖氣系統、熱泵、地暖控制器等

**領域（Domain）**：`climate`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `set_temperature` | 設定溫度 |
| `set_hvac_mode` | 設定 HVAC 模式 |
| `set_fan_mode` | 設定風扇模式 |

### 參數說明

| 參數 | 類型 | 說明 | 可能的值 |
|------|------|------|----------|
| `temperature` | float | 目標溫度 | 依設備而定，例如 16-30 |
| `target_temp_high` | float | 目標最高溫度（冷暖模式） | 依設備而定 |
| `target_temp_low` | float | 目標最低溫度（冷暖模式） | 依設備而定 |
| `hvac_mode` | string | HVAC 模式 | `off`, `heat`, `cool`, `heat_cool`, `auto`, `dry`, `fan_only` |
| `fan_mode` | string | 風扇模式 | `auto`, `low`, `medium`, `high`, `middle`, `focus`, `diffuse` |
| `preset_mode` | string | 預設模式 | `eco`, `away`, `boost`, `comfort`, `home`, `sleep` |
| `swing_mode` | string | 擺風模式 | `off`, `vertical`, `horizontal`, `both` |

### 範例

#### 設定溫度
```json
{
  "entity_id": "climate.living_room_ac",
  "action": "set_temperature",
  "service_data": {
    "temperature": 24
  }
}
```

#### 設定溫度範圍（冷暖兩用）
```json
{
  "entity_id": "climate.living_room_ac",
  "action": "set_temperature",
  "service_data": {
    "target_temp_high": 26,
    "target_temp_low": 22
  }
}
```

#### 設定 HVAC 模式
```json
{
  "entity_id": "climate.living_room_ac",
  "action": "set_hvac_mode",
  "service_data": {
    "hvac_mode": "cool"
  }
}
```

#### 設定風扇模式
```json
{
  "entity_id": "climate.living_room_ac",
  "action": "set_fan_mode",
  "service_data": {
    "fan_mode": "auto"
  }
}
```

---

## 5. Fan（風扇）

**適用設備**：電風扇、吊扇、換氣扇、循環扇等

**領域（Domain）**：`fan`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `turn_on` | 開啟 |
| `turn_off` | 關閉 |
| `set_percentage` | 設定風速百分比 |
| `set_preset_mode` | 設定預設模式 |

### 參數說明

| 參數 | 類型 | 範圍/值 | 說明 |
|------|------|---------|------|
| `percentage` | integer | 0-100 | 風速百分比，0 為關閉，100 為最大風速 |
| `preset_mode` | string | 依設備 | 預設模式，例如 `sleep`, `normal`, `turbo`, `natural` |
| `direction` | string | `forward`, `reverse` | 風扇旋轉方向 |
| `oscillating` | boolean | true/false | 是否擺頭 |

### 範例

#### 開啟風扇
```json
{
  "entity_id": "fan.bedroom_fan",
  "action": "turn_on",
  "service_data": {}
}
```

#### 關閉風扇
```json
{
  "entity_id": "fan.bedroom_fan",
  "action": "turn_off",
  "service_data": {}
}
```

#### 設定風速
```json
{
  "entity_id": "fan.bedroom_fan",
  "action": "set_percentage",
  "service_data": {
    "percentage": 75
  }
}
```

#### 設定預設模式
```json
{
  "entity_id": "fan.bedroom_fan",
  "action": "set_preset_mode",
  "service_data": {
    "preset_mode": "sleep"
  }
}
```

---

## 6. Lock（門鎖）

**適用設備**：智慧門鎖、電子鎖、磁力鎖等

**領域（Domain）**：`lock`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `lock` | 上鎖 |
| `unlock` | 解鎖 |

### 參數說明

| 參數 | 類型 | 說明 |
|------|------|------|
| `code` | string | 解鎖密碼（可選） |

### 範例

#### 上鎖
```json
{
  "entity_id": "lock.front_door",
  "action": "lock",
  "service_data": {}
}
```

#### 解鎖
```json
{
  "entity_id": "lock.front_door",
  "action": "unlock",
  "service_data": {}
}
```

#### 解鎖（使用密碼）
```json
{
  "entity_id": "lock.front_door",
  "action": "unlock",
  "service_data": {
    "code": "1234"
  }
}
```

---

## 7. Scene（場景）

**適用場景**：預設的多設備聯動狀態組合（如「電影模式」、「離家模式」等）

**領域（Domain）**：`scene`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `turn_on` | 啟動場景 |

### 參數說明

| 參數 | 類型 | 說明 |
|------|------|------|
| `transition` | integer | 場景切換的漸變時間（秒） |

### 範例

#### 啟動場景
```json
{
  "entity_id": "scene.movie_night",
  "action": "turn_on",
  "service_data": {}
}
```

#### 啟動場景（設定漸變）
```json
{
  "entity_id": "scene.romantic_dinner",
  "action": "turn_on",
  "service_data": {
    "transition": 3
  }
}
```

---

## 8. Script（腳本）

**適用場景**：自定義的動作序列、複雜的自動化邏輯等

**領域（Domain）**：`script`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `turn_on` | 執行腳本 |
| `turn_off` | 停止腳本 |

### 範例

#### 執行腳本
```json
{
  "entity_id": "script.morning_routine",
  "action": "turn_on",
  "service_data": {}
}
```

#### 執行腳本（傳遞變數）
```json
{
  "entity_id": "script.notify_user",
  "action": "turn_on",
  "service_data": {
    "variables": {
      "message": "Hello from API",
      "title": "Notification"
    }
  }
}
```

#### 停止腳本
```json
{
  "entity_id": "script.morning_routine",
  "action": "turn_off",
  "service_data": {}
}
```

---

## 9. Automation（自動化）

**適用場景**：事件驅動的自動化規則管理

**領域（Domain）**：`automation`

### 支援的動作

| 動作 | 說明 |
|------|------|
| `trigger` | 觸發自動化 |
| `turn_on` | 啟用自動化 |
| `turn_off` | 停用自動化 |

### 參數說明

| 參數 | 類型 | 說明 |
|------|------|------|
| `skip_condition` | boolean | 是否跳過條件檢查，直接執行動作 |

### 範例

#### 觸發自動化
```json
{
  "entity_id": "automation.motion_light",
  "action": "trigger",
  "service_data": {}
}
```

#### 觸發自動化（跳過條件）
```json
{
  "entity_id": "automation.motion_light",
  "action": "trigger",
  "service_data": {
    "skip_condition": true
  }
}
```

#### 啟用自動化
```json
{
  "entity_id": "automation.motion_light",
  "action": "turn_on",
  "service_data": {}
}
```

#### 停用自動化
```json
{
  "entity_id": "automation.motion_light",
  "action": "turn_off",
  "service_data": {}
}
```

---

## 📚 相關文檔

- **[API 基礎與認證](./api-basics.md)** - 端點資訊與簽名計算
- **[程式碼範例](./code-examples.md)** - 完整的實作範例
- **[回應格式](./responses.md)** - 成功與錯誤回應說明

---

**返回**：[控制 API 指南](./README.md)
