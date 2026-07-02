# Smartly Bridge 彈性架構完整規劃

> 版本：v1.0  
> 日期：2026-06-28  
> 主題：Smartly Bridge 品牌 / 協定 / Home Assistant entity 轉換層架構設計  
> 目標：建立高彈性、高擴充性、低耦合的智慧家庭裝置 Bridge 架構

---

## 0. 階層式架構索引

本文件以「階層索引 + 詳細設計章節」維護。未來新增產品、品牌、協定、Capability、API 或實作文件時，優先在本章補上超連結，再視需要補充下方詳細內容。

### 0.0 文件角色與 Source of Truth

本文件是 Smartly Bridge 架構的 master plan，負責維護整體方向、分層、索引、roadmap 與跨章節關係。可被實作、測試、Platform 或 adapter 直接依賴的細節規格，應拆到 [docs/specs](specs/README.md)。

| 文件 | 角色 | Source of Truth 範圍 |
|---|---|---|
| `smartly_bridge_architecture_plan.md` | Master plan / index / roadmap | 系統方向、分層、演進順序、章節入口 |
| [specs/device-abstraction.md](specs/device-abstraction.md) | Device abstraction spec | Logical device、canonical capability、primary type、entity role、adapter normalization、state / command / event、presentation contract |

若 master plan 的摘要與子規格衝突，應以對應子規格為實作細節準則，並回頭更新本文件索引與摘要。

### 0.1 文件維護規則

```txt
第一層：架構領域
第二層：分類入口
第三層：具體 Capability / Adapter / Device Type / API
第四層：實作文件、規格文件、測試資料或外部參考連結
```

建議維護方式：

| 變更類型 | 優先補充位置 | 詳細內容位置 |
|---|---|---|
| 新增產品類型 | [0.6 產品類型索引](#06-產品類型索引) | [23. Smartly 目前裝置的實際 Mapping](#23-smartly-目前裝置的實際-mapping) |
| 新增品牌或型號 | [0.5 Adapter / 品牌 / 協定索引](#05-adapter--品牌--協定索引), [0.6 產品類型索引](#06-產品類型索引) | [8. Adapter Plugin 架構](#8-adapter-plugin-架構), [23. Smartly 目前裝置的實際 Mapping](#23-smartly-目前裝置的實際-mapping) |
| 新增 Capability | [0.4 Capability 索引](#04-capability-索引) | [5. 最核心抽象：Capability](#5-最核心抽象capability), [7. Capability Contract 設計](#7-capability-contract-設計), [Device Abstraction Spec](specs/device-abstraction.md) |
| 新增 API | [0.8 API / 資料流索引](#08-api--資料流索引) | [14. API 設計](#14-api-設計), [28. 最小可行資料流](#28-最小可行資料流) |
| 新增標準資料模型 / logical device 規則 | [0.7 資料模型索引](#07-資料模型索引) | [Device Abstraction Spec](specs/device-abstraction.md) |
| 新增實作文件 | [0.9 實作 / 測試 / Roadmap 索引](#09-實作--測試--roadmap-索引) | [20. 檔案結構建議](#20-檔案結構建議), [25. 測試策略](#25-測試策略), [26. 實作 Roadmap](#26-實作-roadmap) |

### 0.2 架構總覽索引

```txt
Smartly Bridge Architecture
  ├── 原則與邊界
  │   ├── 核心結論
  │   ├── Platform / Bridge Core / Adapter 分工
  │   └── 設計原則總結
  ├── 標準合約
  │   ├── Device
  │   ├── Capability
  │   ├── Command
  │   ├── Event
  │   └── State Update
  ├── 擴充邊界
  │   ├── Adapter Plugin
  │   ├── Adapter Match
  │   ├── Protocol Adapter
  │   ├── Brand Adapter
  │   ├── Model Adapter
  │   └── Generic Adapter
  ├── 產品與能力
  │   ├── 產品類型
  │   ├── Capability 分類
  │   ├── UI Render Contract
  │   └── 實際裝置 Mapping
  ├── Runtime 流程
  │   ├── Command Dispatcher
  │   ├── State Store
  │   ├── Event Bus
  │   ├── Automation
  │   └── Sync
  └── 工程落地
      ├── API
      ├── Database Schema
      ├── 檔案結構
      ├── 測試策略
      └── Roadmap
```

### 0.3 架構領域索引

| 領域 | 目的 | 入口章節 | 補充連結 |
|---|---|---|---|
| 架構原則 | 定義系統邊界與不可違反原則 | [1. 核心結論](#1-核心結論), [29. 設計原則總結](#29-設計原則總結), [0.11 擴充性決策矩陣](#011-擴充性決策矩陣) | [Migration Plan](specs/migration-plan.md) |
| 系統分層 | 定義 Platform、Bridge Core、Adapter 的責任 | [3. 系統總體架構](#3-系統總體架構), [4. 各層責任分工](#4-各層責任分工) | [Adapter Contract](specs/adapter-contract.md), [API vNext Contract](specs/api-vnext-contract.md) |
| 標準資料模型 | 定義 Platform 與 Bridge 之間的穩定資料格式 | [6. 標準資料模型](#6-標準資料模型) | [Device Abstraction Spec](specs/device-abstraction.md) |
| Capability Contract | 定義裝置能力、狀態、指令與 UI hint | [5. 最核心抽象：Capability](#5-最核心抽象capability), [7. Capability Contract 設計](#7-capability-contract-設計) | [Device Abstraction Spec](specs/device-abstraction.md) |
| Adapter 擴充 | 定義品牌 / 協定 / 型號差異的插件邊界 | [8. Adapter Plugin 架構](#8-adapter-plugin-架構), [9. Adapter Match 優先順序](#9-adapter-match-優先順序) | [Device Abstraction Spec](specs/device-abstraction.md) |
| 協定接入 | 定義 Home Assistant、Zigbee2MQTT 等來源如何標準化 | [10. Home Assistant Adapter 設計](#10-home-assistant-adapter-設計), [11. Zigbee2MQTT Adapter 設計](#11-zigbee2mqtt-adapter-設計) | [Device Abstraction Spec](specs/device-abstraction.md) |
| UI Render | 定義 Platform 如何根據 Capability render UI | [13. UI Render Contract](#13-ui-render-contract) | [Presentation Contract](specs/presentation-contract.md), [Device Abstraction Spec](specs/device-abstraction.md) |
| API | 定義 Bridge 與 Platform 通訊 | [14. API 設計](#14-api-設計) | [API vNext Contract](specs/api-vnext-contract.md), [OpenAPI](openapi.yaml) |
| Runtime | 定義 command、state、event、automation 的執行流程 | [15. Command Dispatcher 流程](#15-command-dispatcher-流程), [16. State Store 設計](#16-state-store-設計), [17. Event Bus 設計](#17-event-bus-設計), [22. Automation 設計](#22-automation-設計) | [Device Abstraction Spec](specs/device-abstraction.md) |
| 安全 | 定義 token、ACL、raw data 保護 | [18. 安全與權限模型](#18-安全與權限模型) | [Security Audit](security-audit.md) |
| 工程落地 | 定義檔案結構、DB、測試、Roadmap | [20. 檔案結構建議](#20-檔案結構建議), [21. Database Schema 建議](#21-database-schema-建議), [25. 測試策略](#25-測試策略), [26. 實作 Roadmap](#26-實作-roadmap) | [Migration Plan](specs/migration-plan.md), [Adapter Contract](specs/adapter-contract.md) |

### 0.4 Capability 索引

| 分類 | Capability | 代表產品類型 | Contract 章節 | 補充連結 |
|---|---|---|---|---|
| 控制 | power | light, switch, plug, climate | [7.1 Power Capability](#71-power-capability) | [Capability Contracts](specs/capability-contracts.md) |
| 控制 | brightness | light, light_strip | [7.2 Brightness Capability](#72-brightness-capability) | [Capability Contracts](specs/capability-contracts.md) |
| 控制 | color_temperature | light | [7.3 Color Temperature Capability](#73-color-temperature-capability) | [Capability Contracts](specs/capability-contracts.md) |
| 控制 | rgb_color, hsv_color | light, light_strip | [7.4 RGB Color Capability](#74-rgb-color-capability) | [Capability Contracts](specs/capability-contracts.md) |
| 控制 | effect | light_strip | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 控制 | fan_speed, mode_select | fan, climate | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 控制 | lock | lock | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 感測 | temperature, humidity, pressure | environment_sensor | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 感測 | illuminance | presence_sensor, light_sensor | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 感測 | motion, presence | motion_sensor, presence_sensor | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 感測 | open_close | contact_sensor, cover | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 感測 | battery | battery_device | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 感測 | signal_quality | wifi_device, zigbee_device | [7.5 Signal Quality Capability](#75-signal-quality-capability), [12. dBm / LQI / 百分比的統一策略](#12-dbm--lqi--百分比的統一策略) | [Capability Contracts](specs/capability-contracts.md) |
| 感測 | energy_meter, power_meter, voltage, current | plug, meter | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 事件 | button_event | button, button_switch, scene_switch | [7.6 Button Event Capability](#76-button-event-capability) | [Capability Contracts](specs/capability-contracts.md) |
| 事件 | scene_event, gesture_event | scene_controller, remote | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md) |
| 媒體 | camera_stream, snapshot | camera | [5.3 Capability 分類](#53-capability-分類) | [Camera API](camera-api.md), [WebRTC](webrtc.md) |
| 媒體 | microphone, speaker | camera, intercom | [5.3 Capability 分類](#53-capability-分類) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |

### 0.5 Adapter / 品牌 / 協定索引

| 層級 | 分類 | 目前項目 | 入口章節 | 補充連結 |
|---|---|---|---|---|
| Protocol Adapter | Home Assistant | light, switch, sensor, binary_sensor, event, camera | [10. Home Assistant Adapter 設計](#10-home-assistant-adapter-設計) | [Adapter Contract](specs/adapter-contract.md) |
| Protocol Adapter | Zigbee2MQTT | exposes, action, linkquality | [11. Zigbee2MQTT Adapter 設計](#11-zigbee2mqtt-adapter-設計) | [Adapter Contract](specs/adapter-contract.md) |
| Protocol Adapter | Matter | 後續規劃 | [26. 實作 Roadmap](#26-實作-roadmap) | [Adapter Contract](specs/adapter-contract.md), [Migration Plan](specs/migration-plan.md) |
| Protocol Adapter | MQTT / ESPHome | 後續規劃 | [8.3 Adapter 分類](#83-adapter-分類) | [Adapter Contract](specs/adapter-contract.md) |
| Brand Adapter | Tapo | L530E, L920 | [23.1 Tapo L530E](#231-tapo-l530e), [23.2 Tapo L920](#232-tapo-l920) | [Adapter Contract](specs/adapter-contract.md) |
| Brand Adapter | Aqara | D1, 溫濕度感測器 | [23.3 Aqara D1 雙鍵牆壁開關](#233-aqara-d1-雙鍵牆壁開關), [23.6 Aqara 溫濕度感測器](#236-aqara-溫濕度感測器) | [Adapter Contract](specs/adapter-contract.md) |
| Brand Adapter | Sonoff | SNZB-04P, SNZB-06P | [23.4 Sonoff SNZB-04P 門窗](#234-sonoff-snzb-04p-門窗), [23.5 Sonoff SNZB-06P 存在感測器](#235-sonoff-snzb-06p-存在感測器) | [Adapter Contract](specs/adapter-contract.md) |
| Brand Adapter | Philips Hue / Tuya | 後續規劃 | [24. 擴充新品牌流程](#24-擴充新品牌流程) | [Adapter Contract](specs/adapter-contract.md) |
| Generic Adapter | GenericLightAdapter | light fallback | [8.3 Adapter 分類](#83-adapter-分類) | [Adapter Contract](specs/adapter-contract.md), [Presentation Contract](specs/presentation-contract.md) |
| Generic Adapter | GenericSwitchAdapter | switch fallback | [8.3 Adapter 分類](#83-adapter-分類) | [Adapter Contract](specs/adapter-contract.md), [Presentation Contract](specs/presentation-contract.md) |
| Generic Adapter | GenericSensorAdapter | sensor fallback | [8.3 Adapter 分類](#83-adapter-分類) | [Adapter Contract](specs/adapter-contract.md), [Presentation Contract](specs/presentation-contract.md) |
| Generic Adapter | UnknownDeviceAdapter | unknown fallback | [8.3 Adapter 分類](#83-adapter-分類), [9. Adapter Match 優先順序](#9-adapter-match-優先順序) | [Adapter Contract](specs/adapter-contract.md), [Presentation Contract](specs/presentation-contract.md) |

### 0.6 產品類型索引

| 產品大類 | Device Type | 代表裝置 | 核心 Capability | UI 入口 | Mapping 入口 | 補充連結 |
|---|---|---|---|---|---|---|
| 照明 | light | Tapo L530E | power, brightness, color_temperature, rgb_color, signal_quality | [13.2 Light Control UI 判斷](#132-light-control-ui-判斷) | [23.1 Tapo L530E](#231-tapo-l530e) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |
| 照明 | light_strip | Tapo L920 | power, brightness, rgb_color, effect, signal_quality | [13.1 Widget Mapping](#131-widget-mapping) | [23.2 Tapo L920](#232-tapo-l920) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |
| 開關 / 按鍵 | button_switch | Aqara D1 | button_event, signal_quality, battery 或 power_source | [13.4 Button Automation UI 判斷](#134-button-automation-ui-判斷) | [23.3 Aqara D1 雙鍵牆壁開關](#233-aqara-d1-雙鍵牆壁開關) | [Capability Contracts](specs/capability-contracts.md), [Adapter Contract](specs/adapter-contract.md) |
| 門窗 / 開闔 | contact_sensor | Sonoff SNZB-04P | open_close, battery, signal_quality | [13.3 Sensor UI 判斷](#133-sensor-ui-判斷) | [23.4 Sonoff SNZB-04P 門窗](#234-sonoff-snzb-04p-門窗) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |
| 人體 / 存在 | presence_sensor | Sonoff SNZB-06P | presence, motion, illuminance, signal_quality | [13.3 Sensor UI 判斷](#133-sensor-ui-判斷) | [23.5 Sonoff SNZB-06P 存在感測器](#235-sonoff-snzb-06p-存在感測器) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |
| 環境 | environment_sensor | Aqara 溫濕度感測器 | temperature, humidity, pressure, battery, signal_quality | [13.3 Sensor UI 判斷](#133-sensor-ui-判斷) | [23.6 Aqara 溫濕度感測器](#236-aqara-溫濕度感測器) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |
| 電力 / 插座 | plug, energy_meter | 後續規劃 | power, energy_meter, power_meter, voltage, current | [13.1 Widget Mapping](#131-widget-mapping) | [24. 擴充新品牌流程](#24-擴充新品牌流程) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |
| 門鎖 | lock | 後續規劃 | lock, battery, signal_quality | [13.1 Widget Mapping](#131-widget-mapping) | [24. 擴充新品牌流程](#24-擴充新品牌流程) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |
| 空調 / 風扇 | climate, fan | 後續規劃 | power, temperature, mode_select, fan_speed | [13.1 Widget Mapping](#131-widget-mapping) | [24. 擴充新品牌流程](#24-擴充新品牌流程) | [Capability Contracts](specs/capability-contracts.md), [Presentation Contract](specs/presentation-contract.md) |
| 攝影機 | camera | 待補 | camera_stream, snapshot, microphone, speaker | [13.1 Widget Mapping](#131-widget-mapping) | 待補 | [Camera API](camera-api.md), [WebRTC](webrtc.md) |

### 0.7 資料模型索引

| Model | 用途 | 章節 | 補充連結 |
|---|---|---|---|
| SmartlyDevice / SmartlyLogicalDevice | 裝置標準描述 | [6.1 SmartlyDevice](#61-smartlydevice), [32. SmartlyDevice](#smartlydevice) | [Device Abstraction Spec](specs/device-abstraction.md) |
| SmartlyCapability | 裝置能力標準描述 | [6.2 SmartlyCapability](#62-smartlycapability), [32. SmartlyCapability](#smartlycapability) | [Device Abstraction Spec](specs/device-abstraction.md) |
| SmartlyCommand | Platform / Automation 下發指令 | [6.3 SmartlyCommand](#63-smartlycommand), [32. SmartlyCommand](#smartlycommand) | [Device Abstraction Spec](specs/device-abstraction.md) |
| SmartlyEvent | Adapter / Device 事件上報 | [6.4 SmartlyEvent](#64-smartlyevent), [32. SmartlyEvent](#smartlyevent) | [Device Abstraction Spec](specs/device-abstraction.md) |
| SmartlyStateUpdate | 裝置狀態更新 | [6.5 SmartlyStateUpdate](#65-smartlystateupdate) | [Device Abstraction Spec](specs/device-abstraction.md) |

### 0.8 API / 資料流索引

| 流程 | API / 機制 | 章節 | 補充連結 |
|---|---|---|---|
| Bridge 註冊 | `POST /api/bridges/register` | [14.1 Bridge → Platform：註冊 Bridge](#141-bridge--platform註冊-bridge) | [OpenAPI](openapi.yaml) |
| 裝置同步 | `POST /api/bridges/{bridge_id}/devices/sync` | [14.2 Bridge → Platform：同步裝置](#142-bridge--platform同步裝置), [28.1 裝置同步](#281-裝置同步) | [Sync API](sync-api.md) |
| 狀態更新 | `POST /api/bridges/{bridge_id}/state` | [14.3 Bridge → Platform：狀態更新](#143-bridge--platform狀態更新) | [History API](history-api.md) |
| 事件上報 | `POST /api/bridges/{bridge_id}/events` | [14.4 Bridge → Platform：事件上報](#144-bridge--platform事件上報) | [API vNext Contract](specs/api-vnext-contract.md), [Adapter Contract](specs/adapter-contract.md) |
| 裝置控制 | `POST /api/local/commands` | [14.5 Platform → Bridge：下發指令](#145-platform--bridge下發指令), [28.2 裝置控制](#282-裝置控制) | [Control API](control/README.md) |
| 按鍵自動化 | Event Bus + Local Automation | [22. Automation 設計](#22-automation-設計), [28.3 按鍵自動化](#283-按鍵自動化) | [Presentation Contract](specs/presentation-contract.md), [API vNext Contract](specs/api-vnext-contract.md) |

### 0.9 實作 / 測試 / Roadmap 索引

| 類別 | 入口章節 | 補充連結 |
|---|---|---|
| TypeScript / Node Bridge 檔案結構 | [20.1 TypeScript / Node Bridge](#201-typescript--node-bridge) | [Adapter Contract](specs/adapter-contract.md), [API vNext Contract](specs/api-vnext-contract.md) |
| Home Assistant Custom Component 檔案結構 | [20.2 Home Assistant Custom Component 版本](#202-home-assistant-custom-component-版本) | [Adapter Contract](specs/adapter-contract.md), [Migration Plan](specs/migration-plan.md) |
| Database Schema | [21. Database Schema 建議](#21-database-schema-建議) | [API vNext Contract](specs/api-vnext-contract.md), [Migration Plan](specs/migration-plan.md) |
| Contract Test | [25.1 Contract Test](#251-contract-test) | [Capability Contracts](specs/capability-contracts.md), [Adapter Contract](specs/adapter-contract.md) |
| Fixture Test | [25.2 Fixture Test](#252-fixture-test) | [Adapter Contract](specs/adapter-contract.md), [Migration Plan](specs/migration-plan.md) |
| Normalization Test | [25.3 Normalization Test](#253-normalization-test) | [Capability Contracts](specs/capability-contracts.md), [Adapter Contract](specs/adapter-contract.md) |
| Command Mapping Test | [25.4 Command Mapping Test](#254-command-mapping-test) | [Capability Contracts](specs/capability-contracts.md), [Adapter Contract](specs/adapter-contract.md) |
| Roadmap | [26. 實作 Roadmap](#26-實作-roadmap) | [Migration Plan](specs/migration-plan.md) |
| MVP | [27. MVP 建議範圍](#27-mvp-建議範圍) | [Migration Plan](specs/migration-plan.md) |

### 0.10 Spec 索引

| Spec | 負責範圍 | 狀態 |
|---|---|---|
| [Device Abstraction Spec](specs/device-abstraction.md) | Logical device、canonical capability、primary type、entity role、adapter normalization、state / command / event、presentation contract、versioning | Draft |
| [Capability Contracts](specs/capability-contracts.md) | 各 capability 的 state schema、command schema、event schema、單位、range、錯誤行為、擴充規則 | Draft |
| [Adapter Contract](specs/adapter-contract.md) | adapter manifest、match、normalize、execute、subscribe、health、fixture、sandbox、版本相容要求 | Draft |
| [Presentation Contract](specs/presentation-contract.md) | Platform card template、detail page、dashboard priority、secondary control render 規則、override 邊界 | Draft |
| [API vNext Contract](specs/api-vnext-contract.md) | logical device sync、capability state sync、event ingestion、command dispatch、raw diagnostic fetch、錯誤 envelope | Draft |
| [Migration Plan](specs/migration-plan.md) | 現有 entity-based sync 遷移到 logical-device sync 的階段、相容策略、alias window、rollback gate | Draft |

### 0.11 擴充性決策矩陣

任何新增需求都應先判斷它屬於哪一種變化軸，再決定要改哪一層。目標是讓新增品牌、協定、裝置型號、UI 呈現或 API 版本時，只修改最小且正確的 extension point。

| 變化軸 | 例子 | 優先修改位置 | 不應修改的位置 |
|---|---|---|---|
| 新來源協定 | Matter、Zigbee2MQTT、MQTT、ESPHome | Protocol Adapter、Adapter Manifest、source registry | Platform card、通用 command dispatcher |
| 新品牌 / 型號 | Tapo L930、Aqara FP2、Philips Hue Dimmer | Brand / Model Adapter profile、fixture、match rule | Platform API、Bridge Core if/else |
| 新能力 | `position`、`air_quality`、`water_leak` | Capability Contract、Capability Registry、Presentation Contract | 既有 capability 的語意 |
| 新 UI 形態 | energy dashboard、camera intercom、scene editor | Presentation Contract、Platform renderer | Adapter normalized payload |
| 新控制指令 | `set_position`、`identify`、`set_effect` | Capability command schema、Adapter command mapper | Platform 對品牌做特殊 service call |
| 新資料保存需求 | raw diagnostic、history aggregation、event replay | API vNext、state/event storage policy | sync response 直接塞完整 raw payload |
| 新權限規則 | per-room control、guest mode、maintenance role | Platform RBAC、Bridge ACL policy | Adapter 內硬編使用者規則 |

擴充性判斷順序：

```txt
1. 能不能用既有 canonical capability 表達？
2. 如果不能，是不是只需要新增 capability contract？
3. 如果資料來源不同，是否能只新增 protocol adapter？
4. 如果品牌語意不同，是否能只新增 brand/model adapter profile？
5. 如果 Platform UI 不夠用，是否能只擴充 presentation contract？
6. 如果 API shape 不夠用，是否能用 versioned endpoint 或 optional field 演進？
7. 只有以上都不成立，才考慮調整 Bridge Core。
```

Bridge Core 的變更門檻最高。只有當需求影響 adapter lifecycle、capability registry、command dispatch、state/event consistency 或安全邊界時，才應修改 Bridge Core。

---

## 1. 核心結論

Smartly Bridge 的定位不應該只是「把 Home Assistant 的 entity 傳給 platform」，而應該是：

> **品牌 / 協定 / 裝置資料格式的標準化轉換層。**

最重要的設計原則是：

```txt
Platform 不懂品牌
Bridge Core 不寫品牌邏輯
Adapter 負責品牌 / 協定差異
Capability Contract 統一裝置能力
Normalizer 統一資料單位與語意
Command Mapper 統一控制指令
Raw Data 永遠保留，方便除錯與進階顯示
```

簡化來說：

```txt
不同品牌 / 協定 / HA entity
        ↓
Adapter / Plugin
        ↓
Smartly 標準 Device + Capability
        ↓
Platform 根據 capability 自動 render UI
```

---

## 2. 為什麼不能讓 Platform 直接吃品牌資料？

如果 Platform 直接知道品牌，例如：

```txt
Tapo L530E → 顯示燈泡控制卡
Aqara D1 → 顯示雙鍵開關設定
Sonoff SNZB-06P → 顯示存在感測器卡
```

短期很快，長期會爆炸。

因為每新增一個品牌、裝置、協定，就會造成：

```txt
Platform UI 要改
Platform API 要改
Platform 自動化規則要改
Platform 權限模型要改
Platform 裝置邏輯越來越髒
```

正確做法是讓 Platform 只看到標準能力：

```txt
power
brightness
color_temperature
rgb_color
button_event
presence
motion
temperature
humidity
battery
signal_quality
```

Platform 根據能力 render UI，而不是根據品牌 render UI。

---

## 3. 系統總體架構

```txt
┌─────────────────────────────────────────────┐
│             Smartly Platform / App           │
│                                             │
│  - 使用者 / 場域 / 房間                      │
│  - UI Render                                │
│  - 自動化規則                                │
│  - 權限管理                                  │
│  - 遠端控制 API                              │
└─────────────────────▲───────────────────────┘
                      │
                      │ Smartly Standard API
                      │ Device / Capability / Command / Event
                      │
┌─────────────────────┴───────────────────────┐
│               Smartly Bridge Core            │
│                                             │
│  - Device Registry                          │
│  - Capability Registry                      │
│  - Adapter Loader                           │
│  - State Store                              │
│  - Command Dispatcher                       │
│  - Event Bus                                │
│  - Normalizer                               │
│  - Sync Manager                             │
└─────────────────────▲───────────────────────┘
                      │
                      │ Adapter Interface
                      │
┌─────────────────────┴───────────────────────┐
│                 Adapter Layer                │
│                                             │
│  ┌───────────────┐ ┌─────────────────────┐  │
│  │ HA Adapter    │ │ Zigbee2MQTT Adapter  │  │
│  └───────────────┘ └─────────────────────┘  │
│  ┌───────────────┐ ┌─────────────────────┐  │
│  │ Tapo Adapter  │ │ Matter Adapter       │  │
│  └───────────────┘ └─────────────────────┘  │
│  ┌───────────────┐ ┌─────────────────────┐  │
│  │ Aqara Adapter │ │ Sonoff Adapter       │  │
│  └───────────────┘ └─────────────────────┘  │
└─────────────────────▲───────────────────────┘
                      │
                      │ Raw Protocol / Raw Device Data
                      │
┌─────────────────────┴───────────────────────┐
│          Real Devices / HA / MQTT / Matter   │
└─────────────────────────────────────────────┘
```

---

## 4. 各層責任分工

### 4.1 Platform 負責

Platform 是使用者體驗與商業邏輯層，不應該直接處理品牌差異。

Platform 負責：

```txt
- 使用者帳號
- 家庭 / 場域 / 房間
- 裝置顯示
- 自動化規則設定
- 權限管理
- 遠端控制
- Dashboard / Widget Render
- 裝置分組
- 使用紀錄
```

Platform 不應該負責：

```txt
- 判斷 Tapo L530E 有哪些欄位
- 判斷 Aqara D1 的 action 是 single_left 還是 left_single
- 判斷 Zigbee2MQTT 的 LQI 要怎麼換成訊號強度
- 判斷 Home Assistant 的 brightness 0-255 要怎麼換成 0-100%
- 判斷 HA 的 light.turn_on 服務怎麼呼叫
```

---

### 4.2 Bridge Core 負責

Bridge Core 是標準化核心。

Bridge Core 負責：

```txt
- 載入 Adapter
- 建立 Device Registry
- 建立 Capability Registry
- 維護目前裝置狀態
- 接收 Platform command
- 找到正確 adapter
- 發送指令給 adapter
- 接收 adapter event
- 回報狀態給 Platform
```

Bridge Core 不應該負責：

```txt
- 寫死 Tapo API
- 寫死 Aqara event mapping
- 寫死 Sonoff sensor mapping
- 寫死 HA entity 到 device 的所有規則
```

Bridge Core 只負責抽象流程。

---

### 4.3 Adapter 負責

Adapter 是所有品牌 / 協定 / entity 差異的邊界。

Adapter 負責：

```txt
- discover raw device
- match raw device
- normalize raw device
- normalize raw state
- map Smartly command to raw command
- subscribe raw event
- map raw event to Smartly event
- 回報 adapter 健康狀態
```

例如：

```txt
Tapo Adapter
  - 知道 L530E 有 brightness / color_temp / hsv
  - 知道 Tapo API 指令格式
  - 知道 Tapo brightness 是 1-100

HA Adapter
  - 知道 light.turn_on / switch.turn_off / climate.set_temperature
  - 知道 HA brightness 是 0-255
  - 知道 supported_color_modes 的意義

Zigbee2MQTT Adapter
  - 知道 topic 結構
  - 知道 LQI
  - 知道 action event
```

---

## 5. 最核心抽象：Capability

### 5.1 Device 不應該以品牌為核心

錯誤抽象：

```txt
TapoLight
AqaraSwitch
SonoffPresenceSensor
PhilipsHueLight
```

正確抽象：

```txt
Device
  ├── power
  ├── brightness
  ├── color_temperature
  ├── rgb_color
  ├── signal_quality
  └── battery
```

也就是：

```txt
品牌是 metadata
能力才是 platform 的主抽象
```

---

### 5.2 建議的 Capability 清單

第一階段建議先支援這些能力：

```txt
power
brightness
color_temperature
rgb_color
hsv_color
effect
open_close
motion
presence
temperature
humidity
illuminance
battery
signal_quality
button_event
energy_meter
power_meter
voltage
current
lock
fan_speed
mode_select
camera_stream
```

---

### 5.3 Capability 分類

#### 控制類

```txt
power
brightness
color_temperature
rgb_color
hsv_color
effect
fan_speed
mode_select
lock
```

#### 感測類

```txt
temperature
humidity
illuminance
motion
presence
open_close
battery
signal_quality
energy_meter
power_meter
voltage
current
```

#### 事件類

```txt
button_event
scene_event
gesture_event
```

#### 媒體類

```txt
camera_stream
snapshot
microphone
speaker
```

---

## 6. 標準資料模型

### 6.1 SmartlyDevice

```json
{
  "id": "dev_001",
  "bridge_id": "bridge_home_001",
  "name": "客廳主燈",
  "type": "light",
  "manufacturer": "TP-Link",
  "model": "Tapo L530E",
  "adapter_id": "home_assistant",
  "online": true,
  "room_id": "room_living",
  "source": {
    "type": "home_assistant",
    "entity_id": "light.living_room_main",
    "unique_id": "tapo_l530e_abc123"
  },
  "capabilities": [
    {
      "type": "power",
      "readable": true,
      "writable": true
    },
    {
      "type": "brightness",
      "readable": true,
      "writable": true
    },
    {
      "type": "color_temperature",
      "readable": true,
      "writable": true
    },
    {
      "type": "rgb_color",
      "readable": true,
      "writable": true
    },
    {
      "type": "signal_quality",
      "readable": true,
      "writable": false
    }
  ],
  "raw": {
    "ha_entity_id": "light.living_room_main",
    "ha_domain": "light"
  }
}
```

---

### 6.2 SmartlyCapability

```json
{
  "type": "brightness",
  "readable": true,
  "writable": true,
  "subscribable": true,
  "commands": [
    "set_brightness"
  ],
  "state": {
    "brightness": 72
  },
  "range": {
    "min": 1,
    "max": 100,
    "unit": "%"
  },
  "ui": {
    "widget": "slider",
    "group": "light_control",
    "priority": 20
  },
  "raw": {
    "source_unit": "ha_brightness_0_255",
    "source_value": 184
  }
}
```

---

### 6.3 SmartlyCommand

```json
{
  "command_id": "cmd_001",
  "device_id": "dev_001",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "brightness": 80
  },
  "source": {
    "type": "platform",
    "user_id": "user_001"
  },
  "timestamp": "2026-06-28T23:55:00+08:00"
}
```

---

### 6.4 SmartlyEvent

```json
{
  "event_id": "evt_001",
  "device_id": "dev_button_001",
  "capability": "button_event",
  "event": "left_double_press",
  "payload": {
    "button": "left",
    "action": "double_press"
  },
  "timestamp": "2026-06-28T23:55:00+08:00",
  "raw": {
    "action": "double_left"
  }
}
```

---

### 6.5 SmartlyStateUpdate

```json
{
  "device_id": "dev_001",
  "capability": "brightness",
  "state": {
    "brightness": 60
  },
  "timestamp": "2026-06-28T23:55:00+08:00",
  "raw": {
    "ha_brightness": 153
  }
}
```

---

## 7. Capability Contract 設計

每個 capability 都要有明確合約。

### 7.1 Power Capability

```json
{
  "type": "power",
  "state_schema": {
    "on": "boolean"
  },
  "commands": {
    "turn_on": {},
    "turn_off": {},
    "toggle": {}
  },
  "ui": {
    "widget": "switch"
  }
}
```

---

### 7.2 Brightness Capability

```json
{
  "type": "brightness",
  "state_schema": {
    "brightness": {
      "type": "number",
      "min": 1,
      "max": 100,
      "unit": "%"
    }
  },
  "commands": {
    "set_brightness": {
      "brightness": {
        "type": "number",
        "min": 1,
        "max": 100
      }
    }
  },
  "ui": {
    "widget": "slider",
    "variant": "circular"
  }
}
```

---

### 7.3 Color Temperature Capability

```json
{
  "type": "color_temperature",
  "state_schema": {
    "color_temperature": {
      "type": "number",
      "min": 2000,
      "max": 6500,
      "unit": "K"
    }
  },
  "commands": {
    "set_color_temperature": {
      "color_temperature": {
        "type": "number",
        "unit": "K"
      }
    }
  },
  "ui": {
    "widget": "slider",
    "variant": "warm_cool_bar"
  }
}
```

---

### 7.4 RGB Color Capability

```json
{
  "type": "rgb_color",
  "state_schema": {
    "rgb": {
      "type": "array",
      "items": "number",
      "length": 3,
      "range": [0, 255]
    }
  },
  "commands": {
    "set_rgb_color": {
      "rgb": {
        "type": "array",
        "length": 3
      }
    }
  },
  "ui": {
    "widget": "color_picker"
  }
}
```

---

### 7.5 Signal Quality Capability

```json
{
  "type": "signal_quality",
  "state_schema": {
    "normalized": {
      "value": {
        "type": "number",
        "min": 0,
        "max": 100,
        "unit": "%"
      },
      "level": {
        "type": "enum",
        "values": ["excellent", "good", "fair", "poor", "unknown"]
      }
    },
    "raw": {
      "metric": "string",
      "value": "number",
      "unit": "string"
    }
  },
  "commands": {},
  "ui": {
    "widget": "status_badge"
  }
}
```

---

### 7.6 Button Event Capability

```json
{
  "type": "button_event",
  "events": [
    "single_press",
    "double_press",
    "long_press",
    "left_single_press",
    "left_double_press",
    "left_long_press",
    "right_single_press",
    "right_double_press",
    "right_long_press"
  ],
  "ui": {
    "widget": "event_mapping_editor"
  }
}
```

---

## 8. Adapter Plugin 架構

### 8.1 Adapter Interface

TypeScript 版本：

```ts
export interface DeviceAdapter {
  id: string
  name: string
  version: string

  init(config: AdapterConfig): Promise<void>

  discover(): Promise<RawDevice[]>

  match(rawDevice: RawDevice): boolean

  normalizeDevice(rawDevice: RawDevice): Promise<SmartlyDevice>

  normalizeState(rawDevice: RawDevice, rawState: unknown): Promise<SmartlyStateUpdate[]>

  execute(command: SmartlyCommand): Promise<CommandResult>

  subscribe(callback: AdapterEventCallback): Promise<void>

  getHealth(): Promise<AdapterHealth>
}
```

Python 版本：

```python
from abc import ABC, abstractmethod

class DeviceAdapter(ABC):
    adapter_id: str
    name: str
    version: str

    @abstractmethod
    async def init(self, config: dict) -> None:
        pass

    @abstractmethod
    async def discover(self) -> list[dict]:
        pass

    @abstractmethod
    def match(self, raw_device: dict) -> bool:
        pass

    @abstractmethod
    async def normalize_device(self, raw_device: dict) -> dict:
        pass

    @abstractmethod
    async def normalize_state(self, raw_device: dict, raw_state: dict) -> list[dict]:
        pass

    @abstractmethod
    async def execute(self, command: dict) -> dict:
        pass

    @abstractmethod
    async def subscribe(self, callback) -> None:
        pass

    @abstractmethod
    async def get_health(self) -> dict:
        pass
```

---

### 8.2 Adapter Manifest

每個 adapter 應該有 manifest。

```json
{
  "adapter_id": "tapo",
  "name": "TP-Link Tapo Adapter",
  "version": "1.0.0",
  "type": "brand",
  "supported_protocols": [
    "tapo_local",
    "tapo_cloud"
  ],
  "supported_devices": [
    {
      "manufacturer": "TP-Link",
      "model": "Tapo L530E",
      "device_type": "light",
      "capabilities": [
        "power",
        "brightness",
        "color_temperature",
        "rgb_color"
      ]
    },
    {
      "manufacturer": "TP-Link",
      "model": "Tapo L920",
      "device_type": "light_strip",
      "capabilities": [
        "power",
        "brightness",
        "rgb_color",
        "effect"
      ]
    }
  ]
}
```

---

### 8.3 Adapter 分類

建議分成四種：

```txt
Protocol Adapter
Brand Adapter
Model Adapter
Generic Adapter
```

#### Protocol Adapter

負責協定。

```txt
Home Assistant
MQTT
Zigbee2MQTT
Matter
ESPHome
```

#### Brand Adapter

負責品牌通用邏輯。

```txt
Tapo
Aqara
Sonoff
Philips Hue
Tuya
```

#### Model Adapter

負責特定型號特殊能力。

```txt
Tapo L530E
Tapo L920
Aqara D1
Sonoff SNZB-06P
```

#### Generic Adapter

負責 fallback。

```txt
GenericLightAdapter
GenericSwitchAdapter
GenericSensorAdapter
GenericBinarySensorAdapter
UnknownDeviceAdapter
```

---

## 9. Adapter Match 優先順序

裝置進來後，Bridge 應該照以下順序選 adapter：

```txt
1. Exact Model Adapter
2. Manufacturer / Brand Adapter
3. Protocol Adapter
4. Generic Domain Adapter
5. Unknown Device Adapter
```

例如：

```txt
Tapo L530E from Home Assistant
    ↓
TapoL530EAdapter 有 match → 使用
    ↓ 如果沒有
TapoAdapter 有 match → 使用
    ↓ 如果沒有
HALightAdapter 有 match → 使用
    ↓ 如果沒有
GenericLightAdapter 有 match → 使用
    ↓ 如果沒有
UnknownDeviceAdapter
```

這可以確保：

```txt
已知裝置有最佳體驗
未知裝置仍能基本使用
平台不會因不支援品牌而壞掉
```

---

## 10. Home Assistant Adapter 設計

### 10.1 HA Adapter 的角色

HA Adapter 不是把 HA entity 原封不動傳給 Platform。

HA Adapter 應該把：

```txt
light.xxx
switch.xxx
sensor.xxx
binary_sensor.xxx
climate.xxx
cover.xxx
lock.xxx
button.xxx
event.xxx
```

轉成 SmartlyDevice + SmartlyCapability。

---

### 10.2 HA Entity 到 Smartly Device Mapping

| HA Domain | Smartly Device Type | 可能 Capability |
|---|---|---|
| light | light | power, brightness, color_temperature, rgb_color, effect |
| switch | switch | power |
| sensor | sensor | temperature, humidity, illuminance, battery, signal_quality |
| binary_sensor | binary_sensor | motion, presence, open_close |
| climate | climate | power, temperature, mode_select, fan_speed |
| cover | cover | open_close, position |
| lock | lock | lock |
| button | button | button_event |
| event | event_source | button_event, scene_event |
| camera | camera | camera_stream, snapshot |

---

### 10.3 HA Light Normalization

HA raw：

```json
{
  "entity_id": "light.tapo_l530e",
  "state": "on",
  "attributes": {
    "brightness": 184,
    "supported_color_modes": ["color_temp", "hs"],
    "color_temp_kelvin": 4200,
    "hs_color": [35, 70]
  }
}
```

Smartly normalized：

```json
{
  "device_id": "dev_001",
  "type": "light",
  "capabilities": [
    {
      "type": "power",
      "state": {
        "on": true
      }
    },
    {
      "type": "brightness",
      "state": {
        "brightness": 72
      },
      "raw": {
        "ha_brightness": 184
      }
    },
    {
      "type": "color_temperature",
      "state": {
        "color_temperature": 4200
      }
    },
    {
      "type": "hsv_color",
      "state": {
        "hue": 35,
        "saturation": 70
      }
    }
  ]
}
```

HA brightness 轉換：

```txt
HA brightness: 0-255
Smartly brightness: 1-100
```

公式：

```txt
smartly_brightness = round(ha_brightness / 255 * 100)
ha_brightness = round(smartly_brightness / 100 * 255)
```

---

### 10.4 HA Command Mapping

Smartly command：

```json
{
  "device_id": "dev_001",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "value": 80
  }
}
```

HA command：

```json
{
  "service": "light.turn_on",
  "target": {
    "entity_id": "light.tapo_l530e"
  },
  "data": {
    "brightness_pct": 80
  }
}
```

---

## 11. Zigbee2MQTT Adapter 設計

### 11.1 Zigbee2MQTT 裝置資料

Raw：

```json
{
  "friendly_name": "aqara_d1_switch",
  "ieee_address": "0x00158d000xxxxxxx",
  "definition": {
    "vendor": "Aqara",
    "model": "QBKG24LM",
    "description": "D1 2 gang switch"
  },
  "exposes": [
    {
      "type": "enum",
      "property": "action",
      "values": [
        "single_left",
        "double_left",
        "hold_left",
        "single_right",
        "double_right",
        "hold_right"
      ]
    },
    {
      "type": "numeric",
      "property": "linkquality"
    }
  ]
}
```

Normalized：

```json
{
  "id": "dev_aqara_d1",
  "type": "button_switch",
  "manufacturer": "Aqara",
  "model": "QBKG24LM",
  "capabilities": [
    {
      "type": "button_event"
    },
    {
      "type": "signal_quality"
    }
  ]
}
```

---

### 11.2 Button Event Mapping

Raw Zigbee2MQTT：

```json
{
  "action": "single_left"
}
```

Smartly Event：

```json
{
  "capability": "button_event",
  "event": "left_single_press",
  "payload": {
    "button": "left",
    "action": "single_press"
  },
  "raw": {
    "action": "single_left"
  }
}
```

Mapping 表：

| Raw Action | Smartly Event |
|---|---|
| single_left | left_single_press |
| double_left | left_double_press |
| hold_left | left_long_press |
| single_right | right_single_press |
| double_right | right_double_press |
| hold_right | right_long_press |
| single_both | both_single_press |
| double_both | both_double_press |
| hold_both | both_long_press |

---

## 12. dBm / LQI / 百分比的統一策略

這是 Bridge 架構裡很關鍵的一點。

不同品牌可能回傳：

```txt
Wi-Fi 裝置：RSSI / dBm
Zigbee 裝置：LQI
某些雲端 API：0-100%
某些裝置：訊號格數 1-5
```

Platform 不應該知道這些差異。

### 12.1 標準 Signal Quality Model

```json
{
  "type": "signal_quality",
  "state": {
    "normalized": {
      "value": 82,
      "unit": "%",
      "level": "good"
    },
    "raw": {
      "metric": "lqi",
      "value": 210,
      "unit": "lqi"
    }
  }
}
```

---

### 12.2 RSSI dBm 轉百分比

建議初版採用簡單區間：

```txt
>= -50 dBm       → excellent / 100%
-51 to -60 dBm   → good / 80%
-61 to -70 dBm   → fair / 60%
-71 to -80 dBm   → poor / 30%
< -80 dBm        → poor / 10%
unknown          → unknown
```

可用公式：

```txt
percent = clamp(2 * (rssi + 100), 0, 100)
```

例如：

```txt
-50 dBm → 100%
-60 dBm → 80%
-70 dBm → 60%
-80 dBm → 40%
-90 dBm → 20%
```

---

### 12.3 LQI 轉百分比

常見 LQI 範圍是 0-255。

```txt
percent = round(lqi / 255 * 100)
```

例如：

```txt
255 → 100%
210 → 82%
128 → 50%
60  → 24%
```

---

### 12.4 訊號等級

```txt
90-100 → excellent
70-89  → good
40-69  → fair
1-39   → poor
0/null → unknown
```

---

## 13. UI Render Contract

Platform UI 不根據品牌 render，而是根據 Capability 組合 render。

### 13.1 Widget Mapping

| Capability | UI Widget |
|---|---|
| power | switch button |
| brightness | circular slider / horizontal slider |
| color_temperature | warm-cool bar |
| rgb_color | color picker / color bar |
| hsv_color | color picker |
| effect | effect dropdown |
| temperature | sensor value card |
| humidity | sensor value card |
| motion | status badge |
| presence | presence card |
| open_close | door/window status |
| battery | battery badge |
| signal_quality | signal badge |
| button_event | automation trigger editor |
| camera_stream | camera card |

---

### 13.2 Light Control UI 判斷

如果裝置有：

```txt
power + brightness + color_temperature + rgb_color
```

Platform render：

```txt
智慧燈泡完整控制卡
  - 開關按鈕
  - 亮度圓形滑桿
  - 色溫 bar
  - 顏色 bar / color picker
```

如果只有：

```txt
power + brightness
```

Platform render：

```txt
可調光燈控制卡
  - 開關按鈕
  - 亮度 slider
```

如果只有：

```txt
power
```

Platform render：

```txt
普通開關卡
  - 開關按鈕
```

---

### 13.3 Sensor UI 判斷

如果裝置有：

```txt
temperature + humidity + battery + signal_quality
```

Platform render：

```txt
環境感測器卡
  - 溫度
  - 濕度
  - 電量
  - 訊號
```

---

### 13.4 Button Automation UI 判斷

如果裝置有：

```txt
button_event
```

Platform render：

```txt
按鍵自動化設定卡
  - 單擊
  - 雙擊
  - 長按
  - 左鍵 / 右鍵 / 雙鍵
```

例如 Aqara D1：

```txt
左鍵單擊 → Toggle Light
左鍵雙擊 → Random Color
右鍵單擊 → Brightness +
右鍵雙擊 → Brightness -
左鍵長按 → Party Mode
右鍵長按 → Color Temperature Mode
```

---

## 14. API 設計

### 14.1 Bridge → Platform：註冊 Bridge

```http
POST /api/bridges/register
```

Request：

```json
{
  "bridge_id": "bridge_home_001",
  "name": "Jordan Home Bridge",
  "version": "1.0.0",
  "capabilities": [
    "home_assistant",
    "zigbee2mqtt",
    "matter"
  ]
}
```

---

### 14.2 Bridge → Platform：同步裝置

```http
POST /api/bridges/{bridge_id}/devices/sync
```

Request：

```json
{
  "devices": [
    {
      "id": "dev_001",
      "name": "客廳主燈",
      "type": "light",
      "manufacturer": "TP-Link",
      "model": "Tapo L530E",
      "capabilities": [
        {
          "type": "power",
          "readable": true,
          "writable": true
        },
        {
          "type": "brightness",
          "readable": true,
          "writable": true,
          "range": {
            "min": 1,
            "max": 100,
            "unit": "%"
          }
        }
      ]
    }
  ]
}
```

---

### 14.3 Bridge → Platform：狀態更新

```http
POST /api/bridges/{bridge_id}/state
```

Request：

```json
{
  "updates": [
    {
      "device_id": "dev_001",
      "capability": "power",
      "state": {
        "on": true
      },
      "timestamp": "2026-06-28T23:55:00+08:00"
    }
  ]
}
```

---

### 14.4 Bridge → Platform：事件上報

```http
POST /api/bridges/{bridge_id}/events
```

Request：

```json
{
  "events": [
    {
      "device_id": "dev_button_001",
      "capability": "button_event",
      "event": "left_double_press",
      "payload": {
        "button": "left",
        "action": "double_press"
      },
      "timestamp": "2026-06-28T23:55:00+08:00"
    }
  ]
}
```

---

### 14.5 Platform → Bridge：下發指令

```http
POST /api/local/commands
```

Request：

```json
{
  "command_id": "cmd_001",
  "device_id": "dev_001",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "brightness": 80
  }
}
```

Response：

```json
{
  "schema_version": "2026.06",
  "data": {
    "command_id": "cmd_001",
    "status": "completed",
    "device_id": "dev_001",
    "capability": "brightness",
    "command": "set_brightness"
  },
  "warnings": [],
  "errors": []
}
```

---

## 15. Command Dispatcher 流程

```txt
Platform command
    ↓
Bridge API 接收
    ↓
驗證 command schema
    ↓
查 Device Registry
    ↓
找到 device 對應 adapter_id
    ↓
Command Dispatcher 呼叫 adapter.execute(command)
    ↓
Adapter 轉換成 raw command
    ↓
送到 HA / MQTT / Matter / 品牌 API
    ↓
回傳 CommandResult
    ↓
Bridge 更新 State Store
    ↓
回報 Platform
```

範例：

```txt
Platform:
set_brightness 80%

Bridge:
找到 dev_001 → adapter = home_assistant

HA Adapter:
轉成 light.turn_on brightness_pct=80

Home Assistant:
執行 service call

Bridge:
回傳 API vNext `data.status=completed`
```

---

## 16. State Store 設計

Bridge 應該保留本地狀態快取。

目的：

```txt
- 減少 platform 查詢延遲
- 支援 local-first 控制
- 支援離線後恢復同步
- 支援 command 前後狀態比對
- 支援 automation 本地執行
```

### 16.1 State Store 資料

```json
{
  "device_id": "dev_001",
  "states": {
    "power": {
      "on": true
    },
    "brightness": {
      "brightness": 72
    },
    "color_temperature": {
      "color_temperature": 4200
    }
  },
  "last_seen": "2026-06-28T23:55:00+08:00",
  "online": true
}
```

---

## 17. Event Bus 設計

Bridge 裡面所有事件都應該走 Event Bus。

```txt
Adapter raw event
    ↓
Normalizer
    ↓
SmartlyEvent
    ↓
Event Bus
    ├── State Store
    ├── Platform Sync
    ├── Local Automation
    └── Audit Log
```

### 17.1 Event Types

```txt
device.discovered
device.updated
device.removed
device.online
device.offline
state.changed
command.received
command.succeeded
command.failed
button.pressed
adapter.connected
adapter.disconnected
adapter.error
```

---

## 18. 安全與權限模型

### 18.1 Bridge Token

Bridge 與 Platform 通訊應該使用 Bridge Token。

```txt
bridge_id
bridge_secret
access_token
refresh_token
```

Bridge 註冊後，Platform 發放 token。

---

### 18.2 裝置控制權限

Platform 控制裝置前應檢查：

```txt
user_id 是否屬於 home
user_id 是否有 room 權限
user_id 是否有 device 權限
command 是否允許
```

Bridge 本地也應做基本 ACL。

例如：

```json
{
  "device_id": "dev_001",
  "allowed_commands": [
    "turn_on",
    "turn_off",
    "toggle",
    "set_brightness"
  ],
  "blocked_commands": [
    "factory_reset",
    "delete_device"
  ]
}
```

---

### 18.3 Raw Data 保護

Raw Data 很有用，但不應該全部上傳 Platform。

建議：

```txt
Platform 一般只收 normalized data
Bridge 本地保留完整 raw data
Debug 模式才允許上傳 raw snippet
敏感資訊，例如 token / IP / MAC，需要遮罩
```

---

## 19. 錯誤處理策略

### 19.1 Command Error

```json
{
  "schema_version": "2026.06",
  "data": {
    "command_id": "cmd_001",
    "status": "rejected",
    "device_id": "ldev_light",
    "capability": "power",
    "command": "turn_on",
    "adapter_id": "home_assistant",
    "correlation_id": "cmd_001",
    "expected_state": {},
    "source_entity_id": "light.kitchen"
  },
  "warnings": [],
  "errors": [
    {
      "code": "DEVICE_OFFLINE",
      "message": "Device is offline",
      "target": "device",
      "retryable": true
    }
  ]
}
```

常見錯誤碼：

```txt
DEVICE_NOT_FOUND
DEVICE_OFFLINE
CAPABILITY_NOT_SUPPORTED
COMMAND_NOT_SUPPORTED
INVALID_PARAMS
ADAPTER_UNAVAILABLE
PROTOCOL_ERROR
TIMEOUT
UNAUTHORIZED
RATE_LIMITED
UNKNOWN_ERROR
```

---

### 19.2 Adapter Health

```json
{
  "adapter_id": "home_assistant",
  "status": "connected",
  "last_connected_at": "2026-06-28T23:55:00+08:00",
  "last_error": null
}
```

狀態：

```txt
connected
disconnected
degraded
auth_required
error
```

---

## 20. 檔案結構建議

### 20.1 TypeScript / Node Bridge

```txt
smartly-bridge/
  src/
    core/
      bridge-core.ts
      adapter-loader.ts
      device-registry.ts
      capability-registry.ts
      command-dispatcher.ts
      event-bus.ts
      state-store.ts
      sync-manager.ts

    contracts/
      adapter.ts
      device.ts
      capability.ts
      command.ts
      event.ts
      state.ts
      error.ts

    capabilities/
      power.ts
      brightness.ts
      color-temperature.ts
      rgb-color.ts
      hsv-color.ts
      effect.ts
      battery.ts
      signal-quality.ts
      button-event.ts
      temperature.ts
      humidity.ts
      presence.ts
      motion.ts
      open-close.ts

    adapters/
      home-assistant/
        index.ts
        manifest.json
        ha-client.ts
        ha-discovery.ts
        ha-normalizer.ts
        ha-command-mapper.ts
        ha-event-mapper.ts

      zigbee2mqtt/
        index.ts
        manifest.json
        mqtt-client.ts
        z2m-discovery.ts
        z2m-normalizer.ts
        z2m-command-mapper.ts
        z2m-event-mapper.ts

      tapo/
        index.ts
        manifest.json
        tapo-client.ts
        tapo-normalizer.ts
        tapo-command-mapper.ts

      aqara/
        index.ts
        manifest.json
        aqara-normalizer.ts
        aqara-event-mapper.ts

      sonoff/
        index.ts
        manifest.json
        sonoff-normalizer.ts

      generic/
        generic-light.ts
        generic-switch.ts
        generic-sensor.ts
        generic-binary-sensor.ts
        unknown-device.ts

    api/
      bridge.controller.ts
      devices.controller.ts
      commands.controller.ts
      events.controller.ts
      health.controller.ts

    security/
      auth.ts
      acl.ts
      token-store.ts

    utils/
      unit-converter.ts
      signal-quality.ts
      color-converter.ts
      schema-validator.ts
```

---

### 20.2 Home Assistant Custom Component 版本

如果 Bridge 目前仍放在 Home Assistant integration 內，可以這樣切：

```txt
custom_components/smartly_bridge/
  __init__.py
  manifest.json
  const.py
  config_flow.py

  core/
    bridge_core.py
    adapter_loader.py
    device_registry.py
    capability_registry.py
    command_dispatcher.py
    event_bus.py
    state_store.py
    sync_manager.py

  contracts/
    adapter.py
    device.py
    capability.py
    command.py
    event.py
    state.py
    error.py

  capabilities/
    power.py
    brightness.py
    color_temperature.py
    rgb_color.py
    hsv_color.py
    effect.py
    battery.py
    signal_quality.py
    button_event.py
    temperature.py
    humidity.py
    presence.py
    motion.py
    open_close.py

  adapters/
    home_assistant/
      __init__.py
      manifest.json
      discovery.py
      normalizer.py
      command_mapper.py
      event_mapper.py

    zigbee2mqtt/
      __init__.py
      manifest.json
      mqtt_client.py
      discovery.py
      normalizer.py
      command_mapper.py
      event_mapper.py

    tapo/
      __init__.py
      manifest.json
      client.py
      normalizer.py
      command_mapper.py

    aqara/
      __init__.py
      manifest.json
      normalizer.py
      event_mapper.py

    sonoff/
      __init__.py
      manifest.json
      normalizer.py

    generic/
      light.py
      switch.py
      sensor.py
      binary_sensor.py
      unknown.py

  api/
    http.py
    routes_devices.py
    routes_commands.py
    routes_events.py
    routes_health.py

  security/
    auth.py
    acl.py
    token_store.py

  utils/
    unit_converter.py
    signal_quality.py
    color_converter.py
    schema_validator.py
```

---

## 21. Database Schema 建議

Platform 端可以存標準化結果，不直接存品牌細節為主。

### 21.1 bridges

```sql
CREATE TABLE bridges (
  id TEXT PRIMARY KEY,
  home_id TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT,
  status TEXT NOT NULL,
  last_seen_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);
```

---

### 21.2 devices

```sql
CREATE TABLE devices (
  id TEXT PRIMARY KEY,
  bridge_id TEXT NOT NULL REFERENCES bridges(id),
  home_id TEXT NOT NULL,
  room_id TEXT,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  manufacturer TEXT,
  model TEXT,
  adapter_id TEXT,
  online BOOLEAN NOT NULL DEFAULT false,
  source_type TEXT,
  source_ref TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);
```

---

### 21.3 device_capabilities

```sql
CREATE TABLE device_capabilities (
  id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(id),
  capability_type TEXT NOT NULL,
  readable BOOLEAN NOT NULL DEFAULT true,
  writable BOOLEAN NOT NULL DEFAULT false,
  subscribable BOOLEAN NOT NULL DEFAULT true,
  schema JSONB NOT NULL DEFAULT '{}',
  ui JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(device_id, capability_type)
);
```

---

### 21.4 device_states

```sql
CREATE TABLE device_states (
  device_id TEXT NOT NULL REFERENCES devices(id),
  capability_type TEXT NOT NULL,
  state JSONB NOT NULL,
  raw JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  PRIMARY KEY(device_id, capability_type)
);
```

---

### 21.5 device_events

```sql
CREATE TABLE device_events (
  id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(id),
  capability_type TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  raw JSONB NOT NULL DEFAULT '{}',
  occurred_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

---

### 21.6 command_logs

```sql
CREATE TABLE command_logs (
  id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(id),
  user_id TEXT,
  capability_type TEXT NOT NULL,
  command TEXT NOT NULL,
  params JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL,
  error JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  completed_at TIMESTAMP
);
```

---

## 22. Automation 設計

### 22.1 Automation Trigger

Automation trigger 不應該綁品牌。

錯誤：

```txt
Aqara D1 single_left
```

正確：

```txt
device button_event left_single_press
```

範例：

```json
{
  "trigger": {
    "type": "device_event",
    "device_id": "dev_aqara_d1",
    "capability": "button_event",
    "event": "left_single_press"
  },
  "actions": [
    {
      "type": "device_command",
      "device_id": "dev_tapo_l530e",
      "capability": "power",
      "command": "toggle"
    }
  ]
}
```

---

### 22.2 Automation Action

```json
{
  "type": "device_command",
  "device_id": "dev_light_001",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "brightness": 80
  }
}
```

---

### 22.3 Local Automation

建議 Bridge 支援基本 Local Automation。

理由：

```txt
- 網路斷線時仍可控制
- 延遲更低
- 按鍵控制燈泡不需要經過雲端
```

Platform 可以負責設定規則，Bridge 負責執行簡單規則。

```txt
Platform 儲存完整規則
Bridge 快取 local executable rules
```

---

## 23. Smartly 目前裝置的實際 Mapping

本章作為目前支援與規劃支援裝置的產品型錄。新增產品時，先補 [0.6 產品類型索引](#06-產品類型索引)，再在本章依產品類型新增 mapping。

### 23.0 產品類型分類索引

| 產品大類 | Device Type | 品牌 / 型號 | Adapter 層級 | Capability | 狀態 | 補充連結 |
|---|---|---|---|---|---|---|
| 照明 | light | Tapo L530E | Brand / Model | power, brightness, color_temperature, rgb_color, signal_quality | MVP | [23.1 Tapo L530E](#231-tapo-l530e) |
| 照明 | light_strip | Tapo L920 | Brand / Model | power, brightness, rgb_color, effect, signal_quality | MVP 後 | [23.2 Tapo L920](#232-tapo-l920) |
| 開關 / 按鍵 | button_switch | Aqara D1 | Brand / Model | button_event, signal_quality, battery 或 power_source | MVP | [23.3 Aqara D1 雙鍵牆壁開關](#233-aqara-d1-雙鍵牆壁開關) |
| 門窗 / 開闔 | contact_sensor | Sonoff SNZB-04P | Brand / Model | open_close, battery, signal_quality | MVP | [23.4 Sonoff SNZB-04P 門窗](#234-sonoff-snzb-04p-門窗) |
| 人體 / 存在 | presence_sensor | Sonoff SNZB-06P | Brand / Model | presence, motion, illuminance, signal_quality | MVP | [23.5 Sonoff SNZB-06P 存在感測器](#235-sonoff-snzb-06p-存在感測器) |
| 環境 | environment_sensor | Aqara 溫濕度感測器 | Brand / Model | temperature, humidity, pressure, battery, signal_quality | MVP | [23.6 Aqara 溫濕度感測器](#236-aqara-溫濕度感測器) |
| 電力 / 插座 | plug | 待補 | Generic / Brand | power, energy_meter, power_meter, voltage, current | Backlog | 待補 |
| 門鎖 | lock | 待補 | Generic / Brand | lock, battery, signal_quality | Backlog | 待補 |
| 空調 / 風扇 | climate, fan | 待補 | Protocol / Brand | power, temperature, mode_select, fan_speed | Backlog | 待補 |
| 攝影機 | camera | 待補 | Protocol / Brand | camera_stream, snapshot, microphone, speaker | Backlog | [Camera API](camera-api.md), [WebRTC](webrtc.md) |

### 23.1 Tapo L530E

```txt
Device Type: light
Capabilities:
  - power
  - brightness
  - color_temperature
  - rgb_color
  - signal_quality
```

UI：

```txt
智慧燈泡控制卡
  - 開關按鈕
  - 亮度圓形滑桿
  - 色溫橫向 bar
  - 顏色橫向 bar / color picker
```

---

### 23.2 Tapo L920

```txt
Device Type: light_strip
Capabilities:
  - power
  - brightness
  - rgb_color
  - effect
  - signal_quality
```

UI：

```txt
燈帶控制卡
  - 開關
  - 亮度
  - 顏色
  - 情境效果
```

---

### 23.3 Aqara D1 雙鍵牆壁開關

```txt
Device Type: button_switch
Capabilities:
  - button_event
  - signal_quality
  - battery 或 power_source
```

Events：

```txt
left_single_press
left_double_press
left_long_press
right_single_press
right_double_press
right_long_press
both_single_press
both_double_press
both_long_press
```

---

### 23.4 Sonoff SNZB-04P 門窗

```txt
Device Type: contact_sensor
Capabilities:
  - open_close
  - battery
  - signal_quality
```

---

### 23.5 Sonoff SNZB-06P 存在感測器

```txt
Device Type: presence_sensor
Capabilities:
  - presence
  - motion
  - illuminance
  - signal_quality
```

---

### 23.6 Aqara 溫濕度感測器

```txt
Device Type: environment_sensor
Capabilities:
  - temperature
  - humidity
  - pressure
  - battery
  - signal_quality
```

---

## 24. 擴充新品牌流程

新增品牌時，不要修改 Platform。

流程：

```txt
1. 新增 adapter folder
2. 定義 manifest.json
3. 實作 match(raw_device)
4. 實作 normalizeDevice(raw_device)
5. 實作 normalizeState(raw_state)
6. 實作 execute(command)
7. 實作 event mapping
8. 加入測試資料 fixtures
9. 通過 contract tests
10. Bridge 載入 adapter
```

例如新增 Philips Hue：

```txt
adapters/philips-hue/
  index.ts
  manifest.json
  hue-client.ts
  hue-normalizer.ts
  hue-command-mapper.ts
  hue-event-mapper.ts
  fixtures/
    hue_light.json
    hue_motion_sensor.json
```

---

## 25. 測試策略

### 25.1 Contract Test

每個 adapter 都必須通過：

```txt
- discover 回傳 RawDevice[]
- normalizeDevice 回傳合法 SmartlyDevice
- normalizeState 回傳合法 SmartlyStateUpdate[]
- execute 支援 manifest 宣告的 command
- 不支援的 command 必須回傳 COMMAND_NOT_SUPPORTED
```

---

### 25.2 Fixture Test

保留各品牌 raw data 範例。

```txt
fixtures/
  home_assistant/
    light_tapo_l530e.json
    switch_aqara_d1.json
    sensor_sonoff_presence.json

  zigbee2mqtt/
    aqara_d1_device.json
    sonoff_snzb_06p.json
    aqara_temperature_sensor.json
```

---

### 25.3 Normalization Test

測試單位轉換：

```txt
HA brightness 255 → Smartly brightness 100
HA brightness 128 → Smartly brightness 50
RSSI -60 dBm → signal 80%
LQI 210 → signal 82%
```

---

### 25.4 Command Mapping Test

```txt
Smartly set_brightness 80
  → HA light.turn_on brightness_pct 80

Smartly turn_off
  → HA light.turn_off

Smartly left_double_press event
  → automation trigger matched
```

---

## 26. 實作 Roadmap

### Phase 1：核心 Contract

目標：先把標準資料模型定下來。

```txt
- SmartlyDevice
- SmartlyCapability
- SmartlyCommand
- SmartlyEvent
- SmartlyStateUpdate
- Capability Registry
- 基本 schema validation
```

完成後，Platform 與 Bridge 可以先用 mock device 串起來。

---

### Phase 2：Home Assistant Adapter

目標：用 HA 當第一個主要資料來源。

支援：

```txt
- light
- switch
- sensor
- binary_sensor
- event
```

完成：

```txt
- HA discovery
- HA normalize
- HA command mapper
- HA event mapper
- HA websocket 訂閱 state_changed
```

---

### Phase 3：Smartly Platform UI Render

目標：Platform 開始根據 capability render UI。

先做：

```txt
- light card
- switch card
- sensor card
- button automation card
```

---

### Phase 4：Zigbee2MQTT Adapter

目標：不完全依賴 HA，也可以直接接 Zigbee2MQTT。

支援：

```txt
- MQTT discovery
- exposes parser
- action event mapping
- linkquality normalize
```

---

### Phase 5：Local Automation

目標：Bridge 本地執行低延遲控制。

支援：

```txt
- button_event trigger
- device_command action
- condition
- delay
- toggle
- brightness +/-
- random color
```

---

### Phase 6：Plugin Marketplace / Custom Adapter

長期目標：

```txt
- 第三方 adapter
- manifest validation
- adapter sandbox
- adapter versioning
- adapter install / update
```

---

## 27. MVP 建議範圍

你現在不要一次做太大。

建議 MVP：

```txt
1. Bridge Core
2. Capability Contract
3. HA Adapter
4. Generic Light / Switch / Sensor / Binary Sensor
5. Tapo L530E profile
6. Aqara D1 button_event profile
7. Sonoff SNZB-04P / SNZB-06P profile
8. Platform capability-based render
9. 基本 command dispatch
10. 基本 state sync
```

MVP 先不用做：

```txt
- Matter
- Tuya
- Philips Hue
- Plugin marketplace
- 複雜 automation engine
- Camera stream
- 第三方 adapter 安裝
```

---

## 28. 最小可行資料流

### 28.1 裝置同步

```txt
HA state registry
    ↓
HA Adapter discover
    ↓
HA Adapter normalize
    ↓
Bridge Device Registry
    ↓
Bridge sync to Platform
    ↓
Platform render cards
```

---

### 28.2 裝置控制

```txt
User click brightness slider
    ↓
Platform sends SmartlyCommand
    ↓
Bridge Command Dispatcher
    ↓
HA Adapter command mapper
    ↓
HA service call
    ↓
HA state_changed
    ↓
Bridge State Store update
    ↓
Platform state update
```

---

### 28.3 按鍵自動化

```txt
Aqara D1 raw event: single_left
    ↓
HA / Zigbee2MQTT Adapter
    ↓
SmartlyEvent: left_single_press
    ↓
Bridge Event Bus
    ↓
Local Automation Engine
    ↓
SmartlyCommand: toggle light
    ↓
Command Dispatcher
    ↓
Light Adapter
```

---

## 29. 設計原則總結

### 必須做

```txt
- Capability-first
- Adapter plugin 化
- Raw data 保留
- Command / State / Event 標準化
- Platform 不依賴品牌
- Bridge Core 不寫死品牌
- Generic fallback
- Schema validation
- Contract test
```

### 不要做

```txt
- Platform 根據品牌 render UI
- Bridge Core 寫滿 if brand == Tapo
- 直接把 HA entity 給 Platform
- 不保留 raw data
- 不定義 capability contract 就開始寫 UI
- 每新增品牌都改 Platform
```

---

## 30. 最終推薦架構一句話

> Smartly Bridge 應該設計成「Capability-based Device Abstraction Layer」：  
> 透過 Adapter 把 Home Assistant、Zigbee2MQTT、Matter、Tapo、Aqara、Sonoff 等差異全部轉成 Smartly 標準 Device / Capability / Command / Event，讓 Platform 永遠只面對穩定的標準模型。

這樣架構的好處是：

```txt
- 新增品牌容易
- Platform 穩定
- UI 可自動生成
- 自動化規則不綁品牌
- 未知裝置仍可 fallback
- 未來可脫離 Home Assistant
- 可以支援本地控制與雲端控制並存
```

---

## 31. 建議下一步

建議你下一步先做這三件事：

```txt
1. 定義 contracts/
   - device
   - capability
   - command
   - event
   - state

2. 實作 HA Adapter MVP
   - light
   - switch
   - sensor
   - binary_sensor
   - event

3. 做 Platform 的 capability-based render
   - light control card
   - switch card
   - sensor card
   - button automation editor
```

先把這三個跑通，後面再擴充 Zigbee2MQTT / Matter / 品牌 Adapter。

---

## 32. 最小 Interface 範例

### DeviceAdapter

```ts
export interface DeviceAdapter {
  id: string

  discover(): Promise<RawDevice[]>

  match(rawDevice: RawDevice): boolean

  normalizeDevice(rawDevice: RawDevice): Promise<SmartlyDevice>

  normalizeState(rawDevice: RawDevice, rawState: unknown): Promise<SmartlyStateUpdate[]>

  execute(command: SmartlyCommand): Promise<CommandResult>

  subscribe(callback: (event: AdapterEvent) => void): Promise<void>
}
```

---

### Capability

```ts
export type CapabilityType =
  | 'power'
  | 'brightness'
  | 'color_temperature'
  | 'rgb_color'
  | 'hsv_color'
  | 'effect'
  | 'open_close'
  | 'motion'
  | 'presence'
  | 'temperature'
  | 'humidity'
  | 'illuminance'
  | 'battery'
  | 'signal_quality'
  | 'button_event'
  | 'energy_meter'
  | 'lock'
  | 'fan_speed'
  | 'mode_select'
  | 'camera_stream'
```

---

### SmartlyDevice

```ts
export interface SmartlyDevice {
  id: string
  bridgeId: string
  name: string
  type: string
  manufacturer?: string
  model?: string
  adapterId: string
  online: boolean
  source: {
    type: string
    ref: string
  }
  capabilities: SmartlyCapability[]
  raw?: Record<string, unknown>
}
```

---

### SmartlyCapability

```ts
export interface SmartlyCapability {
  type: CapabilityType
  readable: boolean
  writable: boolean
  subscribable?: boolean
  commands?: string[]
  state?: Record<string, unknown>
  range?: {
    min: number
    max: number
    unit: string
  }
  ui?: {
    widget: string
    group?: string
    priority?: number
  }
  raw?: Record<string, unknown>
}
```

---

### SmartlyCommand

```ts
export interface SmartlyCommand {
  commandId: string
  deviceId: string
  capability: CapabilityType
  command: string
  params: Record<string, unknown>
  source?: {
    type: 'platform' | 'automation' | 'local'
    userId?: string
  }
  timestamp: string
}
```

---

### SmartlyEvent

```ts
export interface SmartlyEvent {
  eventId: string
  deviceId: string
  capability: CapabilityType
  event: string
  payload: Record<string, unknown>
  timestamp: string
  raw?: Record<string, unknown>
}
```

---

## 33. 一句工程判斷

如果你問：「Bridge 到底要不要知道品牌？」

答案是：

> **要，但只能讓 Adapter 知道品牌，不要讓 Bridge Core 和 Platform 知道品牌邏輯。**

這就是整個架構最重要的邊界。
