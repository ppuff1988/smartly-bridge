# Smartly Presentation Contract

> 版本：v0.1  
> 日期：2026-06-29  
> 狀態：Draft  
> 上層文件：[Smartly Bridge 架構規劃](../smartly_bridge_architecture_plan.md)  
> 相關規格：[Device Abstraction](device-abstraction.md)、[Capability Contracts](capability-contracts.md)

## 1. 目的

Presentation contract 定義 Platform 如何根據 logical device 與 capabilities 產生 UI。

Platform 可以有自己的視覺設計，但不可用品牌、協定或 source entity 作為主要 render 判斷。UI 應依賴：

- `primary_type`
- `device_class`
- `capabilities`
- `capability.presentation`
- 使用者 override

## 2. Presentation Envelope

```json
{
  "template": "light_control",
  "priority": 100,
  "icon": "lightbulb",
  "primary_controls": ["power", "brightness"],
  "secondary_controls": ["color_temperature", "rgb_color", "effect"],
  "status_badges": ["signal_quality", "battery"],
  "detail_sections": ["controls", "history", "diagnostics"],
  "automation_triggers": ["button_event"],
  "density": "normal"
}
```

規則：

- `template` 是 UI strategy，不是 React component 名稱。
- `primary_controls` 應少而穩定，避免 dashboard 過載。
- `secondary_controls` 放進 detail 或 expandable controls。
- `status_badges` 只顯示健康、電量、連線、警示。
- `diagnostics` 需要權限，不應對一般使用者預設顯示 raw payload。

## 3. Template 選擇

| 條件 | Template |
|---|---|
| `primary_type=light` 且有 `power` | `light_control` |
| 有 `power` 但無亮度 / 顏色 | `switch_control` |
| 只有 sensor capabilities | `sensor_summary` |
| 有 `button_event` 且 event_only | `button_automation` |
| `primary_type=camera` | `camera_view` |
| 無法辨識 | `diagnostic_device` |

Adapter 可以提供 presentation hint，但 Platform renderer 必須保留 fallback。

## 4. Dashboard 優先順序

Dashboard 應以使用者行為頻率和安全性決定優先順序：

| 優先級 | 類型 | 範例 |
|---|---|---|
| P0 | 安全 / 警示 | lock、water_leak、smoke、offline critical |
| P1 | 常用控制 | light power、switch power、climate mode |
| P2 | 常用感測 | temperature、humidity、presence |
| P3 | 健康狀態 | battery、signal_quality |
| P4 | 診斷 | raw refs、adapter health、source ids |

一般 dashboard 不應直接顯示 P4。

## 5. Override Policy

使用者或管理員可以 override：

- 顯示名稱
- 房間 / 區域
- icon
- dashboard 是否顯示
- primary / secondary control 排序
- device grouping
- adapter match profile

不可 override：

- Capability canonical 語意
- 權限結果
- source authentication
- raw payload 內容
- command schema validation

Override 必須可回復，且應保留 override source：

```json
{
  "field": "presentation.icon",
  "value": "ceiling-light",
  "source": "user",
  "updated_at": "2026-06-29T00:00:00Z"
}
```

## 6. Unknown Device

未知裝置仍應可見，但只能用安全 fallback：

- Template：`diagnostic_device`
- 預設唯讀
- 顯示 source、adapter match confidence、raw summary
- 不顯示危險 command
- 提供「指派 adapter profile」或「回報 fixture」流程

這讓系統可以持續學習新裝置，而不需要 Platform 先支援每個品牌。

## 7. Automation UI

Automation UI 應依 capability 產生 trigger/action。

| Capability | Trigger | Action |
|---|---|---|
| `button_event` | button event occurred | 無 |
| `open_close` | opened / closed | 無 |
| `presence` | presence detected / cleared | 無 |
| `power` | state changed | turn_on / turn_off / toggle |
| `brightness` | value changed | set / increase / decrease |
| `lock` | locked / unlocked | lock / unlock |

Automation 不應使用 source event name，例如 `single_left`。必須使用 canonical event，例如 `single_press` + `button=left`。

