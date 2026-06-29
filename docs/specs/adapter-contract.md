# Smartly Adapter Contract

> 版本：v0.1  
> 日期：2026-06-29  
> 狀態：Draft  
> 上層文件：[Smartly Bridge 架構規劃](../smartly_bridge_architecture_plan.md)  
> 相關規格：[Device Abstraction](device-abstraction.md)、[Capability Contracts](capability-contracts.md)

## 1. 目的

Adapter 是 Smartly Bridge 的主要擴充邊界。所有協定、品牌、型號、來源資料格式與特殊 command mapping 都應封裝在 adapter 或 adapter profile 內。

Bridge Core 不應包含品牌判斷。Platform 不應包含來源協定判斷。

```text
Raw Source
   ↓
Protocol Adapter
   ↓
Brand / Model Profile
   ↓
Capability Normalizer
   ↓
Smartly Contract
```

## 2. Adapter 類型

| 類型 | 範圍 | 例子 |
|---|---|---|
| Protocol Adapter | 理解來源協定與資料交換方式 | Home Assistant、Zigbee2MQTT、Matter、MQTT |
| Brand Adapter | 理解品牌通用語意與命名 | Tapo、Aqara、Sonoff、Philips Hue |
| Model Profile | 修正特定型號能力與事件 | Aqara D1、Tapo L530E |
| Generic Adapter | 沒有品牌 profile 時的 fallback | GenericLight、GenericSensor |
| Diagnostic Adapter | 未知或低信心裝置的唯讀呈現 | UnknownDevice |

優先順序：

```text
Model Profile > Brand Adapter > Protocol Adapter > Generic Adapter > Diagnostic Adapter
```

## 3. Manifest

每個 adapter 必須提供 manifest：

```json
{
  "id": "home_assistant.light",
  "name": "Home Assistant Light Adapter",
  "version": "0.1.0",
  "adapter_type": "protocol",
  "supported_sources": ["home_assistant"],
  "supported_domains": ["light"],
  "supported_capabilities": ["power", "brightness", "color_temperature", "rgb_color"],
  "match_priority": 500,
  "contract_versions": {
    "device_abstraction": "2026.06",
    "capability": "2026.06"
  },
  "permissions": {
    "network": false,
    "filesystem": "readonly",
    "secrets": []
  }
}
```

規則：

- `id` 必須穩定，不得因顯示名稱改變而改變。
- `match_priority` 越高越早被評估。
- `supported_capabilities` 是 adapter 可以輸出的 canonical capability。
- manifest 不得宣告無法通過 contract test 的能力。
- permissions 必須最小化；第三方 adapter 不得預設取得 secrets。

## 4. Interface

Adapter 需提供以下能力。實作語言可不同，但 Bridge Core 看到的行為必須一致。

```ts
export interface SmartlyAdapter {
  manifest: AdapterManifest
  health(): Promise<AdapterHealth>
  discover(context: DiscoverContext): Promise<RawDevice[]>
  match(rawDevice: RawDevice): Promise<MatchResult>
  normalizeDevice(rawDevice: RawDevice): Promise<SmartlyLogicalDevice>
  normalizeState(rawDevice: RawDevice, rawState: unknown): Promise<SmartlyStateUpdate[]>
  execute(command: SmartlyCommand): Promise<CommandResult>
  subscribe?(callback: (event: AdapterEvent) => void): Promise<SubscriptionHandle>
}
```

可選能力：

| 方法 | 使用情境 |
|---|---|
| `diagnose` | 回傳 raw diagnostic summary |
| `refreshMetadata` | 重新讀取來源能力或 exposes |
| `validateConfig` | 檢查 adapter 設定 |
| `migrateProfile` | profile schema 升級 |

## 5. Match Result

```json
{
  "matched": true,
  "confidence": 0.92,
  "adapter_id": "aqara.d1",
  "reason": "manufacturer+model matched",
  "fallback_allowed": true
}
```

Match 規則：

- `confidence >= 0.90` 可自動套用。
- `0.60 <= confidence < 0.90` 可套用 generic adapter，並提示可人工 override。
- `confidence < 0.60` 應使用 diagnostic adapter。
- 若多個 adapter 同分，選 `match_priority` 高者。
- 人工 override 優先於自動 match，但必須保留原 match result 供診斷。

## 6. Normalization Pipeline

Adapter normalize 應分成明確階段：

```text
1. Parse raw source payload
2. Identify source device and source entities
3. Select logical device grouping
4. Select primary type and device class
5. Map source fields to canonical capabilities
6. Apply constraints and unit conversion
7. Attach presentation hints
8. Store raw refs for diagnostics
9. Validate Smartly contract
```

任何階段失敗都應回傳可追蹤錯誤，不應產生半合法物件。

## 7. Command Mapping

Command mapping 只允許發生在 adapter 或 command mapper profile。

```text
SmartlyCommand
   ↓
Capability command schema validation
   ↓
Adapter command mapper
   ↓
Source protocol call
   ↓
CommandResult
```

CommandResult：

```json
{
  "command_id": "cmd_001",
  "status": "accepted",
  "adapter_id": "home_assistant.light",
  "source_request_id": "ha_context_id",
  "expected_state": {
    "power": { "value": true }
  }
}
```

`accepted` 不代表狀態已改變。狀態一致性應由後續 state update 或 timeout reconciliation 處理。

## 8. Event Mapping

Adapter 必須將 source event 映射成 SmartlyEvent：

```json
{
  "event_id": "evt_001",
  "device_id": "ldev_aqara_d1",
  "capability": "button_event",
  "event": "single_press",
  "payload": {
    "button": "left"
  },
  "raw_ref": "raw_evt_001"
}
```

Event 必須可去重：

- 同一 source event id 不得重複送出。
- 沒有 source event id 時，adapter 必須產生短時間去重 key。
- Bridge Core 應保留 event replay window，避免 reconnect 後重複觸發 automation。

## 9. Health

Adapter health：

```json
{
  "status": "healthy",
  "last_success_at": "2026-06-29T00:00:00Z",
  "last_error": null,
  "source_latency_ms": 42,
  "capabilities_degraded": []
}
```

狀態：

| Status | 說明 |
|---|---|
| `healthy` | 正常 |
| `degraded` | 部分來源或 capability 不可用 |
| `unavailable` | 無法連線或初始化失敗 |
| `disabled` | 被設定或安全策略停用 |

## 10. Sandbox 與安全

第三方 adapter 必須預設受限：

- 不可直接讀取 Bridge secrets。
- 不可任意讀寫檔案系統。
- 不可任意對外連線，除非 manifest 宣告且使用者允許。
- raw payload 必須走 Bridge diagnostic storage，不可自行上傳。
- adapter crash 不得中斷 Bridge Core。

## 11. Fixture 與測試要求

每個 adapter 至少提供：

- Raw device fixture
- Raw state fixture
- Raw event fixture
- Expected logical device snapshot
- Expected state update snapshot
- Expected command mapping snapshot
- Unsupported command case
- Offline / timeout case

Adapter 合併前必須通過：

- Manifest validation
- Contract validation
- Match priority collision test
- Normalization snapshot test
- Command mapping test
- Event dedupe test
- Health degradation test

