# Smartly 裝置抽象層規格

> 版本：v0.1  
> 日期：2026-06-29  
> 狀態：Draft  
> 範圍：未來 Smartly Bridge 與 Smartly Platform 的裝置抽象層  
> 原則：優先為長期擴充性設計。目前實作細節是遷移時的輸入，不是本規格的限制。

> 上層文件：[Smartly Bridge 架構規劃](../smartly_bridge_architecture_plan.md)

## 1. 目的

Smartly Bridge 應演進成以 capability 為核心的裝置抽象層。

系統不應被單一協定、目前某個 Home Assistant integration、某台 ESP32 裝置，或某種 Zigbee2MQTT exposes 格式牽制。所有來源系統都應被標準化成穩定的 Smartly 模型：

```text
Source Device / Source Entity / Source Event
        ↓
Protocol Adapter
        ↓
Normalization Pipeline
        ↓
Smartly Logical Device
        ↓
Capability Contract
        ↓
Platform Presentation and Automation
```

核心目標是：Smartly Platform 可以 render card、建立 automation、下發 command、顯示裝置狀態，但不需要知道裝置來源是 Home Assistant、ESPHome、MQTT、Zigbee2MQTT、Matter、Tuya、Tapo、Aqara，或未來任何 adapter。

## 2. 非目標

本規格不定義目前程式碼的實作行為。

本規格不要求立即相容既有 API response shape。

本規格不為單一現有裝置定義一次性的特殊行為。

本規格不要求 Platform 理解 vendor-specific payload。

本規格不把 Home Assistant domain、Zigbee2MQTT exposes 或 MQTT topic 作為 Platform-facing contract。

## 3. 核心詞彙

| 詞彙 | 說明 |
|---|---|
| Source | 提供裝置資料的上游系統，例如 Home Assistant、ESPHome、MQTT、Zigbee2MQTT、Matter 或 vendor cloud |
| Source Device | 來源系統中的實體硬體裝置，或來源系統回報的裝置 |
| Source Entity | 來源層級中可控制或可觀測的單位，例如 `light.xxx`、`fan.xxx`、MQTT topic、Matter endpoint 或 Zigbee expose |
| Adapter | 理解某個 source、protocol、brand 或 model family 的 plugin |
| Logical Device | Smartly 標準化後的使用者面向裝置，可由一個或多個 source entities 組成 |
| Capability | 標準化後的能力或訊號，例如 power、brightness、fan speed、button event、battery 或 signal quality |
| Primary Type | logical device 的主要使用者面向用途 |
| Secondary Capability | logical device 中有用但不是主要用途的功能 |
| Entity Role | source entity 在 logical device 中扮演的角色 |
| Presentation | 由標準化裝置與 capability 資料產生的 UI hint |
| Raw Data | 為診斷與 adapter 改進而保留的來源 payload |

## 4. 設計原則

Smartly Platform 必須依賴 Smartly contract，而不是 source contract。

Bridge Core 必須依賴 adapter interface，而不是 vendor-specific logic。

Adapter 必須保留 raw source data，同時輸出標準化的 Smartly object。

Capability 名稱必須 canonical 且 versioned。

Logical device grouping 必須在 normalization 後明確產生。

Platform card rendering 必須根據 `primary_type`、`capabilities` 與 `presentation`，而不是根據 brand、model 或 protocol。

Manual override 必須存在，但 automatic classification 是預設路徑。

Unknown device 必須以安全的 read-only diagnostic device 形式保持可見。

## 5. 標準資料模型

### 5.1 SmartlyLogicalDevice

```json
{
  "id": "ldev_001",
  "bridge_id": "bridge_001",
  "name": "Example Logical Device",
  "primary_type": "selected_primary_type",
  "device_class": "selected_device_class",
  "manufacturer": "Example",
  "model": "Example Model",
  "status": "online",
  "area_id": "area_living",
  "capabilities": [],
  "source_entities": [],
  "presentation": {},
  "raw_refs": [],
  "diagnostics": {
    "label_trace": {
      "source": "home_assistant",
      "entities": []
    }
  },
  "schema_version": "2026.06"
}
```

規則：

- `id` 是穩定的 Smartly logical device ID。
- `primary_type` 描述主要的使用者面向分類。
- `device_class` 是 Platform UI classification。
- `capabilities` 是支援行為的唯一依據。
- `source_entities` 記錄上游 entity 如何映射到 logical device。
- `raw_refs` 指向已儲存的診斷 raw payload；正常 sync response 不應包含完整 raw payload。
- `diagnostics` 是 owner/support-only metadata；customer-facing render/control 不得依賴它。
- `diagnostics.label_trace` 可解釋 Home Assistant label-derived exposure、hidden、class override、grouping 與 presentation hint decisions，但不得包含 HA token、password、client secret、IP address、完整 registry payload、完整 state attributes 或 raw diagnostic payload body。
- `diagnostics.label_trace.entities[]` 必須以 source entity 為粒度，讓 grouped logical device 可以解釋每個 member 的 label decision。

### 5.2 SmartlyCapability

```json
{
  "id": "cap_001",
  "type": "fan_speed",
  "role": "primary",
  "readable": true,
  "writable": true,
  "event_only": false,
  "state": {},
  "commands": [],
  "events": [],
  "constraints": {},
  "presentation": {},
  "instances": [],
  "source_refs": []
}
```

規則：

- `type` 必須使用 canonical capability name。
- `role` 必須是 `primary`、`secondary`、`health`、`diagnostic`、`event_source` 或 `setting` 其中之一。
- `readable`、`writable` 與 `event_only` 必須明確宣告。
- State schema 與 command schema 必須由 capability contract 定義。
- 一個 logical device 可以有多個來自不同 source entity 的 capabilities。
- 同一 logical device 有多個同型 setting 時，`instances` 必須逐項保留 stable `key`、顯示名稱、state、commands 與 constraints；不得只保留第一項 metadata。
- `instances` 不得包含 source entity ID。來源路由只留在 Bridge 內部 `source_refs`，Platform customer response 必須排除 `source_refs`。

### 5.3 SourceEntityRef

```json
{
  "source": "source_name",
  "source_device_id": "source_device_001",
  "source_entity_id": "source.primary_entity",
  "domain": "source_domain",
  "role": "primary_control",
  "capability_types": ["power"]
}
```

Entity roles：

| Role | 說明 |
|---|---|
| `primary_control` | logical device 的主要 controllable entity |
| `secondary_control` | 附加 controllable function |
| `sensor` | read-only state 或 measurement |
| `health` | Battery、signal、connectivity、diagnostics |
| `event_source` | Button、scene、gesture 或 stateless event source |
| `diagnostic` | raw 或 support-only entity |

## 6. Canonical Capability 名稱

Capability name 必須在所有 adapter 之間保持穩定。

| 分類 | Canonical Capability |
|---|---|
| Control | `power` |
| Control | `brightness` |
| Control | `color_temperature` |
| Control | `rgb_color` |
| Control | `effect` |
| Control | `fan_speed` |
| Control | `mode_select` |
| Control | `position` |
| Control | `lock` |
| Sensor | `temperature` |
| Sensor | `humidity` |
| Sensor | `pressure` |
| Sensor | `illuminance` |
| Sensor | `motion` |
| Sensor | `presence` |
| Sensor | `open_close` |
| Sensor | `energy_meter` |
| Sensor | `power_meter` |
| Sensor | `voltage` |
| Sensor | `current` |
| Health | `battery` |
| Health | `signal_quality` |
| Event | `button_event` |
| Event | `scene_event` |
| Event | `gesture_event` |
| Media | `camera_stream` |
| Media | `snapshot` |
| Media | `microphone` |
| Media | `speaker` |

Source-specific alias 必須在資料送到 Platform 前完成映射。

Alias 範例：

| Alias | Canonical |
|---|---|
| `on_off` | `power` |
| `color_temp` | `color_temperature` |
| `signal_strength` | `signal_quality` |
| `occupancy` | `presence` |
| `contact` | `open_close` |
| `event` | 依 adapter context 映射成 `button_event` 或 `scene_event` |

## 7. Primary Type 與 Device Class

`primary_type` 是 logical device 的使用者面向產品分類。

`device_class` 是 Platform 或 Bridge 根據 `primary_type` 與 capabilities 選出的 UI strategy。

| Primary Type | Typical Device Class |
|---|---|
| `light` | `light_control` |
| `switch` | `switch_control` |
| `plug` | `plug_control` |
| `fan` | `fan_control` |
| `climate` | `climate_control` |
| `cover` | `cover_control` |
| `lock` | `lock_control` |
| `camera` | `camera_view` |
| `environment_sensor` | `environment_sensor` |
| `presence_sensor` | `presence_sensor` |
| `contact_sensor` | `contact_sensor` |
| `button` | `button_event_source` |
| `remote` | `remote_event_source` |
| `multi_function` | `multi_capability_device` |
| `unknown` | `unknown_device` |

規則：

- 一個 logical device 只能有一個 `primary_type`。
- 一個 logical device 可以有多個 capabilities。
- 一個 logical device 可以包含多個 source entities。
- 當 grouping evidence 顯示裝置由多個 entity 組成時，`primary_type` 不得只從單一 source domain 推導。
- 只有在無法安全選出單一主要用途時，才使用 `multi_function`。

## 8. Logical Device Grouping

Adapter 與 normalization pipeline 必須先把 source entities group 成 logical devices，再同步給 Platform。

Grouping evidence 由強到弱：

1. Protocol 或 platform 提供的穩定 source device ID。
2. 明確的 user 或 installer grouping override。
3. 共用硬體識別，例如 MAC、IEEE address、serial number、Matter node ID 或 ESPHome device name。
4. Source metadata 宣告的 parent device 或 endpoint relationship。
5. 只有在沒有更安全 metadata 時，才使用 naming convention。

Grouping output 必須為每個 source entity 指派一個 role：

```text
primary_control
secondary_control
sensor
health
event_source
diagnostic
```

Generic multi-capability logical device 範例：

```json
{
  "primary_type": "selected_primary_type",
  "device_class": "selected_device_class",
  "capabilities": [
    { "type": "primary_control_capability", "role": "primary" },
    { "type": "secondary_control_capability", "role": "secondary" },
    { "type": "event_capability", "role": "event_source" },
    { "type": "health_capability", "role": "health" }
  ],
  "source_entities": [
    { "source_entity_id": "source.primary_entity", "role": "primary_control" },
    { "source_entity_id": "source.secondary_entity", "role": "secondary_control" },
    { "source_entity_id": "source.event_entity", "role": "event_source" },
    { "source_entity_id": "source.health_entity", "role": "health" }
  ]
}
```

上方範例是 generic architecture case，不得綁定 ESP32、Zigbee2MQTT、Home Assistant 或任何特定現有裝置。

## 9. Primary Type 選擇規則

Primary type selection 必須 deterministic。

當存在多個 controllable capabilities 時，建議優先順序如下：

1. Lock、alarm、access control 等 safety-critical device type 必須要求 explicit classification。
2. 如果 source metadata 或 user override 標記了 primary source entity，使用該 entity 的 normalized type。
3. 如果 capabilities 包含 specialized control group，優先選擇該 group，而不是 generic `power`。
4. 如果只有 generic `power`，預設分類為 `switch`，除非 metadata 或 override 指向 light、fan、plug 或 appliance。
5. 如果只有 sensor capabilities，依主要 sensor category 分類。
6. 如果只有 event capabilities，分類為 `button` 或 `remote`。
7. 如果無法安全分類，分類為 `unknown`。

Specialized control groups：

| Capability Evidence | Preferred Primary Type |
|---|---|
| `fan_speed` | `fan` |
| `temperature` 加上 HVAC 用途的 `mode_select` | `climate` |
| `brightness`、`color_temperature` 或 `rgb_color` | `light` |
| `position` 加上 open/close 行為 | `cover` |
| `lock` | `lock` |
| `camera_stream` 或 `snapshot` | `camera` |

## 10. Adapter 架構

Adapter 必須把 source data normalize 成 Smartly contracts。

Adapter 類型：

| Adapter Type | 說明 |
|---|---|
| Protocol Adapter | 處理 source protocol，例如 Home Assistant、MQTT、ESPHome、Zigbee2MQTT、Matter |
| Brand Adapter | 處理跨 model 的 vendor conventions |
| Model Adapter | 處理精確 model 的 quirks |
| Generic Adapter | 提供安全 fallback behavior |

Adapter 選擇順序：

```text
Exact Model Adapter
    ↓
Brand Adapter
    ↓
Protocol Adapter
    ↓
Generic Adapter
    ↓
Unknown Adapter
```

Adapter 必須提供：

```text
discover source devices
discover source entities
normalize device identity
normalize capabilities
normalize states
normalize events
map commands
report health
preserve raw diagnostic data
```

Adapter 不得提供 Platform-specific card layouts。

## 11. Capability Contract 要求

每個 capability 必須定義：

```text
canonical type
state schema
command schema
event schema, if event-producing
readability
writability
unit
range or enum values
normalization rules
source alias rules
presentation hints
error behavior
security constraints
```

`fan_speed` contract 範例：

```json
{
  "type": "fan_speed",
  "state_schema": {
    "speed": {
      "type": "enum",
      "values": ["off", "low", "medium", "high", "auto"]
    },
    "percentage": {
      "type": "number",
      "min": 0,
      "max": 100,
      "unit": "%"
    }
  },
  "commands": {
    "set_fan_speed": {
      "speed": "string"
    },
    "set_fan_percentage": {
      "percentage": "number"
    }
  }
}
```

Capability contracts 必須可跨 protocol 重複使用。

## 12. State Model

State update 必須以 capability 為 scope。

```json
{
  "logical_device_id": "ldev_001",
  "capability_type": "power",
  "state": {
    "on": true
  },
  "source_entity_ref": "source.primary_entity",
  "observed_at": "2026-06-29T00:00:00Z",
  "raw_ref": "raw_001"
}
```

規則：

- Platform 不應為了正常 UI parse raw attributes。
- Raw state 只提供給 diagnostics 或 adapter development。
- Unknown 或 unavailable source state 必須 normalize 到 `status`，而不是任意 UI text。

## 13. Command Model

Command 必須以 capability 為 scope。

```json
{
  "command_id": "cmd_001",
  "logical_device_id": "ldev_001",
  "capability_type": "mode_select",
  "command": "set_mode",
  "params": {
    "mode": "auto"
  },
  "actor": {
    "type": "user",
    "id": "user_001"
  }
}
```

規則：

- Platform 只發送 Smartly command。
- Bridge 將 Smartly command map 到 source command。
- Adapter 必須用 structured error 拒絕 unsupported command。
- 除非在 diagnostic mode，command 必須 target capability，而不是 target source entity。

## 14. Event Model

Event 必須先 normalize，才能進入 automation 或 Platform rendering。

```json
{
  "event_id": "evt_001",
  "logical_device_id": "ldev_001",
  "capability_type": "button_event",
  "event": "long_press",
  "payload": {
    "button": "primary",
    "action": "long_press"
  },
  "occurred_at": "2026-06-29T00:00:00Z",
  "source_entity_ref": "source.event_entity",
  "raw_ref": "raw_002"
}
```

Button event vocabulary：

```text
single_press
double_press
triple_press
long_press
hold_start
hold_release
rotate_left
rotate_right
gesture
```

這份 vocabulary 只定義可用詞彙，不代表每台裝置都支援全部事件。Adapter 必須在
`button_event.constraints.channels` 逐 channel 宣告事件集合；`triple_press` 與 rotary
事件只有在 declared schema 中存在時才可接受。沒有 schema 的裝置不得推論
`triple_press` 支援。

Multi-button device 可以把 button identity 放在 payload 中，不需要為每顆按鍵建立新的 event name：

```json
{
  "event": "single_press",
  "payload": {
    "button": "left"
  }
}
```

## 15. Presentation Contract

Presentation 是 hint layer。Platform 可以使用它，但 capability contract 仍是 authoritative。

```json
{
  "card_template": "selected_card_template",
  "primary_control": "primary_control_capability",
  "primary_metric": "primary_metric_capability",
  "secondary_controls": ["secondary_control_capability"],
  "secondary_metrics": ["battery", "signal_quality"],
  "dashboard_priority": 50,
  "detail_sections": ["controls", "events", "health", "diagnostics"]
}
```

規則：

- Dashboard card 只顯示一個 primary purpose。
- 只有當 secondary control 明確屬於同一個 physical logical device 時，才可以嵌入主卡。
- Event-only capability 不得 render 成 toggle。
- Health 與 diagnostics 不得成為 primary dashboard control。
- Detail page 可以對有權限的使用者 expose 完整 capability controls 與 raw diagnostics。

## 16. Override Policy

Automatic classification 是預設路徑。

允許 override 的項目：

```text
primary_type
device_class
logical device grouping
source entity role
display name
dashboard visibility
favorite priority
```

Override source 由強到弱：

1. Platform admin override。
2. Bridge installer override。
3. Source labels 或 source metadata。
4. Adapter inference。
5. Generic fallback。

安全規則：

- Override 不得授予 unsupported capabilities。
- Override 不得繞過 safety restrictions。
- Lock、alarm、access control 等 unsafe domains 需要 explicit high-trust classification。
- 如果 override 與 capability evidence 衝突，device 必須 fallback 到 limited 或 read-only mode。

## 17. API 方向

未來 API 應同步 logical devices，而不是 raw source entities。

建議的 sync resources：

```text
Bridge registration
Logical device sync
Capability state sync
Event ingestion
Capability command dispatch
Raw diagnostic fetch
```

正常 Platform sync 應接收：

```text
logical devices
capabilities
presentation hints
current state summary
source entity references
raw references
```

正常 Platform sync 不應接收：

```text
vendor-specific command payloads
full raw upstream state for every card
source-specific classification as the final truth
```

## 18. Versioning 與 Migration

每個 contract 都必須包含 schema version。

建議 version fields：

```text
device_schema_version
capability_schema_version
adapter_contract_version
presentation_schema_version
```

Migration 規則：

- Minor version 允許 additive fields。
- 重新命名 canonical capability name 時，至少要在一個 major migration period 內支援 alias。
- Platform 應能 tolerate unknown capabilities，做法可以是忽略，或以安全 read-only detail 顯示。
- Bridge 只應在 migration window 內同時 emit canonical names 與 source-specific aliases。
- Existing entity-based sync 可以和 logical-device sync 共存，直到 Platform migration 完成。

## 19. 擴充性檢查清單

新增 device family、adapter 或 capability 前，必須回答：

```text
這是新的 capability，還只是新的 source mapping？
既有 primary_type 是否能代表這個裝置？
既有 device_class 是否能安全 render 這個裝置？
這是否需要 command support、event support，或只需要 read-only display？
哪些 raw source fields 必須保留？
哪個 fixture 可以證明 normalization 正確？
什麼 fallback behavior 是安全的？
允許哪些 override？
Platform 應在 dashboard render 什麼？
Platform 只應在 detail 或 diagnostics 顯示什麼？
```

## 20. 建議後續補充的 Spec 文件

本 architecture spec 之後應再拆出更窄的子規格：

```text
capability-contracts.md
logical-device-grouping.md
adapter-contract.md
presentation-contract.md
command-state-event-contract.md
normalization-fixtures.md
migration-plan.md
```

這些 spec 應 reference 本文件作為 architecture source of truth。
