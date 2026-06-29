# Smartly Capability Contracts

> 版本：v0.1  
> 日期：2026-06-29  
> 狀態：Draft  
> 上層文件：[Smartly Bridge 架構規劃](../smartly_bridge_architecture_plan.md)  
> 相關規格：[Device Abstraction](device-abstraction.md)

## 1. 目的

Capability contract 是 Platform、Bridge Core、Adapter、Automation 與測試之間的穩定合約。

所有 capability 都必須定義：

- Canonical name
- State schema
- Command schema
- Event schema
- Constraints
- Unit 與數值範圍
- Presentation hint
- 錯誤行為
- 版本與相容策略

Platform 不應直接讀取 Home Assistant attribute、Zigbee2MQTT expose、Matter cluster 或品牌私有 payload。這些差異應在 adapter 內被正規化成 capability contract。

## 2. Contract Envelope

每個 capability contract 應使用相同 envelope：

```json
{
  "type": "brightness",
  "version": "2026.06",
  "readable": true,
  "writable": true,
  "event_only": false,
  "state_schema": {},
  "command_schemas": {},
  "event_schemas": {},
  "constraints": {},
  "presentation": {},
  "source_refs": []
}
```

規則：

- `type` 必須是 canonical capability name。
- `version` 使用 `YYYY.MM` 或 semver；breaking change 必須新增版本，不可覆寫既有語意。
- `state_schema` 是 Platform 可以儲存、顯示與訂閱的資料。
- `command_schemas` 是 Platform 或 Automation 可以下發的指令。
- `event_schemas` 是 event-only 或 mixed capability 可以發出的事件。
- `constraints` 只能縮小合法範圍，不得改變 capability 本身語意。
- `presentation` 是 UI hint，不是業務邏輯。
- `source_refs` 只用於診斷與追蹤，不得成為 Platform 決策依據。

## 3. 命名與版本規則

Capability name 應使用穩定、抽象、跨品牌的語意。

| 類型 | 可接受 | 不可接受 |
|---|---|---|
| 通用能力 | `brightness` | `tapo_brightness` |
| 標準感測 | `open_close` | `sonoff_contact_state` |
| 事件 | `button_event` | `aqara_d1_action` |
| 診斷 | `signal_quality` | `zigbee_lqi_only` |

新增 capability 前必須確認：

1. 是否能用既有 capability + constraints 表達。
2. 是否只是 presentation 差異。
3. 是否只是 adapter source alias。
4. 是否會讓 automation 可以跨品牌重用。
5. 是否能以 optional field 擴充而不破壞既有 consumer。

## 4. 通用 State 規則

所有 state 必須包含：

```json
{
  "value": "normalized_value",
  "updated_at": "2026-06-29T00:00:00Z",
  "quality": "good",
  "source": {
    "adapter_id": "home_assistant",
    "source_entity_id": "light.living_room"
  }
}
```

`quality` 可用值：

| Quality | 說明 |
|---|---|
| `good` | 來源資料可信且即時 |
| `stale` | 裝置離線或資料逾時 |
| `estimated` | 經推估、轉換或 fallback |
| `unknown` | 來源沒有足夠資訊 |
| `error` | 來源回報錯誤 |

數值單位必須在 adapter normalize 階段統一。Platform 不應再進行品牌或協定層級的單位轉換。

## 5. 核心 Capability

### 5.1 `power`

用途：表示裝置主要開關狀態。

State：

```json
{
  "value": true
}
```

Commands：

| Command | Params | 說明 |
|---|---|---|
| `turn_on` | `{}` | 開啟 |
| `turn_off` | `{}` | 關閉 |
| `toggle` | `{}` | 切換狀態，若來源不支援 toggle，由 Bridge Core 讀 state 後轉成 on/off |

### 5.2 `brightness`

用途：表示亮度或類似 0-100 的強度控制。

State：

```json
{
  "value": 75,
  "unit": "percent"
}
```

Constraints：

```json
{
  "min": 0,
  "max": 100,
  "step": 1
}
```

Commands：

| Command | Params | 說明 |
|---|---|---|
| `set_brightness` | `{ "value": 0-100 }` | 設定亮度百分比 |
| `increase_brightness` | `{ "delta": 1-100 }` | 遞增 |
| `decrease_brightness` | `{ "delta": 1-100 }` | 遞減 |

Adapter 必須處理來源 range，例如 Home Assistant `0-255`、Zigbee `0-254` 或 vendor `1-1000`。

### 5.3 `color_temperature`

State：

```json
{
  "value": 4000,
  "unit": "kelvin"
}
```

Constraints 應由 adapter 根據來源能力提供：

```json
{
  "min": 2000,
  "max": 6500,
  "step": 50
}
```

若來源只支援 mired，adapter 必須轉為 kelvin 並保留 raw diagnostic。

### 5.4 `rgb_color`

State：

```json
{
  "value": {
    "r": 255,
    "g": 120,
    "b": 40
  }
}
```

Commands：

| Command | Params |
|---|---|
| `set_rgb_color` | `{ "r": 0-255, "g": 0-255, "b": 0-255 }` |

若來源使用 HSV、XY 或 HS，adapter 應轉成 canonical RGB，並可額外輸出 `hsv_color` 作為 secondary capability。

### 5.5 `button_event`

用途：無狀態按鍵、場景控制器或遙控器事件。

State：通常無 state，`event_only` 應為 `true`。

Events：

```json
{
  "event": "single_press",
  "button": "left",
  "sequence": 1,
  "occurred_at": "2026-06-29T00:00:00Z"
}
```

Canonical event：

| Event | 說明 |
|---|---|
| `single_press` | 單擊 |
| `double_press` | 雙擊 |
| `long_press` | 長按 |
| `long_release` | 長按放開 |
| `rotate_left` | 旋鈕左轉 |
| `rotate_right` | 旋鈕右轉 |

品牌值如 `single_left`、`left_single`、`1_single` 必須在 adapter 中映射。

### 5.6 `signal_quality`

State：

```json
{
  "value": 82,
  "unit": "percent",
  "raw_metric": {
    "kind": "lqi",
    "value": 210
  }
}
```

規則：

- Platform 永遠使用 `value` 判斷顯示。
- `raw_metric` 只做診斷。
- RSSI、LQI、Wi-Fi RSSI percentage 必須映射到 `0-100`。

## 6. Capability Extension Policy

新增 capability 時必須提供：

- Contract 文件
- Adapter fixture
- Normalization test
- Presentation fallback
- Unknown / unsupported 行為
- Migration note

若只是來源欄位不同，應新增 adapter mapping，不應新增 capability。

若只是 UI 不同，應新增 presentation hint，不應新增 capability。

若需要 vendor-specific 進階功能，應先放在 `diagnostic` 或 `extension` namespace，等至少兩個來源可共用時再升格成 canonical capability。

## 7. 錯誤行為

Capability command 錯誤必須回傳標準錯誤碼：

| Code | 使用時機 |
|---|---|
| `CAPABILITY_NOT_FOUND` | logical device 不存在該能力 |
| `COMMAND_NOT_SUPPORTED` | capability 存在但不支援該 command |
| `INVALID_PARAMS` | params 不符合 schema 或 constraints |
| `DEVICE_OFFLINE` | 裝置離線 |
| `ADAPTER_UNAVAILABLE` | adapter 不可用 |
| `SOURCE_REJECTED` | 來源系統拒絕控制 |
| `TIMEOUT` | 控制逾時 |

錯誤 response 必須帶 `command_id`、`device_id`、`capability`、`adapter_id` 與可追蹤的 `correlation_id`。

