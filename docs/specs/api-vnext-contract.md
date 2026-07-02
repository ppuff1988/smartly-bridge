# Smartly API vNext Contract

> 版本：v0.1  
> 日期：2026-06-29  
> 狀態：Draft  
> 上層文件：[Smartly Bridge 架構規劃](../smartly_bridge_architecture_plan.md)  
> 相關規格：[Device Abstraction](device-abstraction.md)、[Adapter Contract](adapter-contract.md)

## 1. 目的

API vNext 的目標是讓 Bridge 與 Platform 交換 logical device、capability state、event 與 command，而不是直接交換 Home Assistant entity shape。

API 必須支援：

- Versioned contract
- Idempotency
- Partial sync
- Backward compatible optional fields
- Command correlation
- Event dedupe
- Raw diagnostic fetch
- Rollback-friendly migration

## 2. 通用 Envelope

所有 JSON API response 應有一致 envelope：

```json
{
  "schema_version": "2026.06",
  "request_id": "req_001",
  "correlation_id": "corr_001",
  "data": {},
  "warnings": [],
  "errors": []
}
```

例外：

- `304 Not Modified` / empty HTTP responses 不得包含 JSON body，需以 `X-Smartly-Response-Mode: empty` 標示。
- MJPEG / binary / streaming responses 不得包成 JSON envelope，需以 `X-Smartly-Response-Mode: stream` 標示並保留原始 streaming headers。

錯誤：

```json
{
  "code": "INVALID_PARAMS",
  "message": "brightness must be between 0 and 100",
  "target": "command.params.value",
  "retryable": false
}
```

## 3. Device Sync

`POST /api/vnext/bridges/{bridge_id}/devices:sync`

Request：

```json
{
  "sync_mode": "full",
  "since": null,
  "devices": []
}
```

Response：

```json
{
  "data": {
    "accepted": true,
    "sync_cursor": "cursor_001",
    "device_count": 12,
    "warnings": []
  }
}
```

規則：

- Full sync 用於首次同步或重大 schema migration。
- Incremental sync 用於一般變更。
- Logical device ID 必須穩定。
- Source entity ID 應放在 alias，不應成為主 ID。
- Raw payload 不應放在 sync body；只傳 `raw_refs`。

## 4. State Sync

`POST /api/vnext/bridges/{bridge_id}/states`

```json
{
  "updates": [
    {
      "device_id": "ldev_001",
      "capability": "brightness",
      "state": {
        "value": 80,
        "unit": "percent",
        "quality": "good",
        "updated_at": "2026-06-29T00:00:00Z"
      }
    }
  ]
}
```

規則：

- State update 可以 partial。
- 每筆 update 必須包含 capability。
- Platform 應以 `updated_at` 和 monotonic sequence 防止舊狀態覆蓋新狀態。
- Bridge 可以 batch，但應保留每筆狀態的來源時間。

## 5. Event Ingestion

`POST /api/vnext/bridges/{bridge_id}/events`

```json
{
  "events": [
    {
      "event_id": "evt_001",
      "device_id": "ldev_button",
      "capability": "button_event",
      "event": "single_press",
      "payload": {
        "button": "left"
      },
      "occurred_at": "2026-06-29T00:00:00Z"
    }
  ]
}
```

規則：

- `event_id` 在 Bridge scope 內必須可去重。
- Platform 必須以 `event_id` idempotent ingest。
- Event 不應被 state polling 模擬成重複事件。
- Automation engine 應以 canonical event 判斷，不應使用 raw action。

## 6. Command Dispatch

`POST /api/vnext/bridges/{bridge_id}/commands`

```json
{
  "command_id": "cmd_001",
  "device_id": "ldev_light",
  "capability": "brightness",
  "command": "set_brightness",
  "params": {
    "value": 80
  },
  "source": {
    "type": "platform",
    "user_id": "user_001"
  }
}
```

Response：

```json
{
  "data": {
    "command_id": "cmd_001",
    "status": "accepted",
    "expected_state": {
      "brightness": {
        "value": 80,
        "unit": "percent"
      }
    }
  }
}
```

Status：

| Status | 說明 |
|---|---|
| `accepted` | Bridge 已接受並送往 source |
| `completed` | 已確認狀態改變 |
| `rejected` | schema、權限或 capability 不符 |
| `failed` | source 或 adapter 執行失敗 |
| `timeout` | 未在期限內得到結果 |

## 7. Raw Diagnostic Fetch

`GET /api/vnext/bridges/{bridge_id}/diagnostics/raw/{raw_ref}`

規則：

- 需要管理員或維運權限。
- 回傳需遮罩 secrets、tokens、IP 等敏感資訊。
- raw_ref 有 TTL。
- raw data 不得進入一般 device sync response。

## 8. Versioning

API versioning 原則：

- 新增 optional field：允許。
- 新增 enum value：允許，但 consumer 必須有 unknown fallback。
- 改變既有欄位語意：不允許，必須升版。
- 移除欄位：只允許在 migration window 後。
- command schema breaking change：必須新增 command version 或新 command name。
