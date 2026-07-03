# 設備類型控制

> **返回**：[控制 API 指南](./README.md)

本文檔說明 `/api/smartly/control` 使用的 API vNext `SmartlyCommand` 格式。Platform 應以 `device_id`、`capability`、`command` 和 `params` 控制邏輯設備，不直接送 Home Assistant service call body。

---

## 通用 Body

```json
{
  "command_id": "cmd_20260627_0001",
  "device_id": "ldev_bedroom_light",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "value": 78
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

| 欄位 | 說明 |
|------|------|
| `command_id` | 命令追蹤 ID，用於冪等與審計 |
| `device_id` | Sync API 回傳的邏輯設備 ID |
| `capability` | 要控制的 canonical capability |
| `command` | capability 支援的 canonical command |
| `params` | command 參數，依 capability 而定 |
| `source` | 操作者資訊，用於審計日誌 |

---

## Power

適用於開關、燈、風扇、腳本、自動化等可開關設備。

| Command | Params | 說明 |
|---------|--------|------|
| `turn_on` | `{}` | 開啟 |
| `turn_off` | `{}` | 關閉 |
| `toggle` | `{}` | 切換狀態 |

```json
{
  "command_id": "cmd_power_0001",
  "device_id": "ldev_living_switch",
  "capability": "power",
  "command": "turn_on",
  "params": {},
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Brightness

適用於燈光與支援亮度控制的設備。

| Command | Params | 說明 |
|---------|--------|------|
| `set_brightness` | `{"value": 0-100}` | 設定亮度百分比 |
| `increase_brightness` | `{"step": 1-100}` | 增加亮度 |
| `decrease_brightness` | `{"step": 1-100}` | 降低亮度 |

```json
{
  "command_id": "cmd_brightness_0001",
  "device_id": "ldev_bedroom_light",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "value": 78
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Color

適用於支援 RGB、色溫、效果或色彩模式的燈光。

| Capability | Command | Params |
|------------|---------|--------|
| `rgb_color` | `set_rgb_color` | `{"r": 255, "g": 180, "b": 100}` |
| `color_temperature` | `set_color_temperature` | `{"value": 3000}` |
| `effect` | `set_effect` | `{"effect": "rainbow"}` |

```json
{
  "command_id": "cmd_color_0001",
  "device_id": "ldev_bedroom_light",
  "capability": "rgb_color",
  "command": "set_rgb_color",
  "params": {
    "r": 255,
    "g": 180,
    "b": 100
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Position

適用於窗簾、捲簾、車庫門與百葉窗。

| Capability | Command | Params |
|------------|---------|--------|
| `position` | `open` | `{}` |
| `position` | `close` | `{}` |
| `position` | `stop` | `{}` |
| `position` | `set_position` | `{"value": 0-100}` |
| `tilt_position` | `set_tilt` | `{"value": 0-100}` |

```json
{
  "command_id": "cmd_position_0001",
  "device_id": "ldev_living_cover",
  "capability": "position",
  "command": "set_position",
  "params": {
    "value": 50
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Climate

適用於空調、恆溫器、暖氣與熱泵。

| Capability | Command | Params |
|------------|---------|--------|
| `target_temperature` | `set_temperature` | `{"value": 24}` |
| `target_temperature_range` | `set_range` | `{"low": 22, "high": 26}` |
| `mode_select` | `set_mode` | `{"mode": "cool"}` |
| `fan_speed` | `set_fan_speed` | `{"mode": "auto"}` |
| `preset_mode` | `set_preset` | `{"preset": "eco"}` |
| `swing_mode` | `set_swing` | `{"mode": "vertical"}` |

```json
{
  "command_id": "cmd_climate_0001",
  "device_id": "ldev_living_ac",
  "capability": "target_temperature",
  "command": "set_temperature",
  "params": {
    "value": 24
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Fan

適用於電風扇、吊扇、換氣扇與循環扇。

| Capability | Command | Params |
|------------|---------|--------|
| `fan_speed` | `set_percentage` | `{"value": 75}` |
| `fan_speed` | `set_preset` | `{"preset": "sleep"}` |
| `fan_direction` | `set_direction` | `{"direction": "forward"}` |
| `fan_oscillation` | `set_oscillating` | `{"enabled": true}` |

```json
{
  "command_id": "cmd_fan_0001",
  "device_id": "ldev_bedroom_fan",
  "capability": "fan_speed",
  "command": "set_percentage",
  "params": {
    "value": 75
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Lock

適用於智慧門鎖、電子鎖與磁力鎖。

| Command | Params | 說明 |
|---------|--------|------|
| `lock` | `{}` | 上鎖 |
| `unlock` | `{"code": "1234"}` | 解鎖，密碼依設備需求提供 |

```json
{
  "command_id": "cmd_lock_0001",
  "device_id": "ldev_front_door",
  "capability": "lock",
  "command": "unlock",
  "params": {
    "code": "1234"
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Scene And Script

場景與腳本使用 `run` capability。

| Command | Params | 說明 |
|---------|--------|------|
| `run` | `{}` | 啟動場景或執行腳本 |
| `stop` | `{}` | 停止可停止的腳本 |

```json
{
  "command_id": "cmd_scene_0001",
  "device_id": "ldev_movie_night",
  "capability": "run",
  "command": "run",
  "params": {},
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Button

Home Assistant `button` entity 在 Platform contract 中分成 command-only `button_press` 與 event-only `button_event`。

| Capability | Command | Params |
|------------|---------|--------|
| `button_press` | `press` | `{}` |

```json
{
  "command_id": "cmd_button_0001",
  "device_id": "ldev_desk_scene",
  "capability": "button_press",
  "command": "press",
  "params": {},
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## Setting Controls

Presence sensor 等 sibling setting entity 會升格為 canonical setting capability。

| Capability | Command | Params |
|------------|---------|--------|
| `numeric_setting` | `set_value` | `{"key": "detection_delay", "value": 10}` |
| `option_setting` | `select_option` | `{"key": "sensitivity", "option": "high"}` |

```json
{
  "command_id": "cmd_setting_0001",
  "device_id": "ldev_presence_sensor",
  "capability": "numeric_setting",
  "command": "set_value",
  "params": {
    "key": "detection_delay",
    "value": 10
  },
  "source": {
    "user_id": "u_123",
    "role": "tenant"
  }
}
```

---

## 📚 相關文檔

- **[API 基礎與認證](./api-basics.md)** - 端點資訊與簽名計算
- **[程式碼範例](./code-examples.md)** - 完整的實作範例
- **[回應格式](./responses.md)** - 成功與錯誤回應說明

---

**返回**：[控制 API 指南](./README.md)
