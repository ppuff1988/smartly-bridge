# Smartly Bridge Migration Plan

> 版本：v0.1  
> 日期：2026-06-29  
> 狀態：Draft  
> 上層文件：[Smartly Bridge 架構規劃](../smartly_bridge_architecture_plan.md)  
> 相關規格：[Device Abstraction](device-abstraction.md)、[API vNext](api-vnext-contract.md)

## 1. 目的

本文件定義 Smartly Bridge 從目前偏 entity-based 的 API 與資料模型，遷移到 logical-device / capability-based 架構的路線。

遷移原則：

- 不一次切斷現有 API。
- 先雙軌產生資料，再逐步切換 consumer。
- ID、alias、state 與 command 需要可追蹤。
- 每階段都要可 rollback。
- Contract test 先於正式切流。

## 2. 階段總覽

| Phase | 目標 | 主要輸出 | Rollback |
|---|---|---|---|
| 0 | 盤點現況 | entity inventory、API consumer list、fixture | 無變更 |
| 1 | 建立 contract | schema、capability registry、adapter interface | 不啟用 runtime |
| 2 | 雙軌 normalize | entity response + logical device shadow payload | 停用 shadow |
| 3 | Platform read path 切換 | Platform 讀 logical device | 回 entity response |
| 4 | Command path 切換 | Platform 下 SmartlyCommand | 回既有 control API |
| 5 | Event / automation 切換 | canonical event 驅動 automation | 回 raw/entity trigger |
| 6 | 清理 legacy | 移除過期 alias 與 deprecated endpoint | 保留長期 LTS endpoint |

## 3. Phase 0：Inventory

需要盤點：

- 現有 `/api/smartly/sync/states` response shape。
- 現有 control API command shape。
- Home Assistant domain / device_class / attributes 使用情況。
- Platform 目前依賴哪些欄位。
- 哪些欄位是 UI 用、控制用、診斷用。
- 哪些 entity 實際屬於同一台硬體。

輸出：

- `fixtures/current-sync/*.json`
- entity to logical device mapping table
- API consumer compatibility matrix

## 4. Phase 1：Contract First

先落地不可執行但可驗證的 contract：

- Device abstraction schema
- Capability contracts
- Adapter manifest schema
- API vNext envelope
- Presentation fallback
- Migration alias model

Gate：

- Schema validation 可執行。
- Fixture snapshot 可比較。
- Platform 可用 mock logical devices render 基本 card。

## 5. Phase 2：Shadow Normalize

Bridge 在既有 sync response 之外，產生 shadow logical device payload。

```text
Current HA entities
   ↓
Existing sync payload
   ↓
Shadow adapter normalize
   ↓
Logical device snapshot
   ↓
Comparison report
```

規則：

- Shadow payload 不影響正式 UI。
- 每次 sync 都記錄 normalization warning。
- 不能 normalize 的 entity 進入 diagnostic device。
- 建立 entity ID 到 logical device ID 的 alias。

Gate：

- 主要裝置類型 normalize coverage >= 90%。
- 既有 MVP 裝置 fixture 全部通過。
- 沒有 P0 command mapping 缺口。

## 6. Phase 3：Platform Read Path

Platform 開始優先讀 logical device。

策略：

- Feature flag：`use_logical_devices`
- Room / device display 仍保留既有 alias。
- 不支援的 card 使用 legacy render fallback。
- Unknown device 用 diagnostic UI，不中斷 dashboard。

Rollback：

- 關閉 feature flag。
- Platform 回讀既有 entity payload。

## 7. Phase 4：Command Path

Platform 從 source-specific command 改成 SmartlyCommand。

遷移策略：

- 新 UI 發 SmartlyCommand。
- 舊 UI 或舊 app 仍可使用 legacy command endpoint。
- Bridge command dispatcher 將 SmartlyCommand 映射到 source call。
- 所有 command log 同時記錄 logical device ID 與 legacy entity ID。

Gate：

- power / brightness / color temperature / switch / button automation command mapping 通過。
- command accepted 與後續 state update 可以 correlation。
- timeout 和 source rejected 有標準錯誤。

## 8. Phase 5：Event 與 Automation

Raw event 轉 canonical event：

```text
single_left
   ↓
button_event / single_press / button=left
```

策略：

- Automation editor 只顯示 canonical event。
- 既有 automation 規則保留 alias。
- Event ingestion 以 event_id 去重。
- Local automation 先支援 button_event + device_command。

## 9. Phase 6：Legacy Cleanup

清理前必須符合：

- 所有活躍 Platform client 都支援 API vNext。
- Legacy endpoint 使用率低於門檻。
- alias window 已公告並過期。
- rollback playbook 已驗證。

可移除：

- Platform 對品牌欄位的直接判斷。
- Bridge Core 的 source-specific fallback。
- sync response 中不必要的 raw payload。

不可移除：

- raw diagnostic storage。
- alias mapping history。
- migration audit log。

## 10. Alias Policy

Alias 用於保留遷移期間的 ID 穩定性。

```json
{
  "logical_device_id": "ldev_001",
  "aliases": [
    {
      "kind": "home_assistant_entity_id",
      "value": "light.living_room",
      "valid_from": "2026-06-29T00:00:00Z",
      "valid_until": null
    }
  ]
}
```

規則：

- Alias 不可成為 canonical ID。
- Alias 變更必須留歷史。
- Command log 必須記錄當時使用的 alias。
- 刪除 alias 前需要至少一個 release window。

## 11. Completion Criteria

遷移完成需同時滿足：

- Platform dashboard 不依賴品牌或 source entity render。
- Control path 使用 SmartlyCommand。
- State path 使用 capability state。
- Event path 使用 canonical event。
- Adapter contract test 作為新增裝置的入口。
- Unknown device 有安全 fallback。
- Legacy API 有明確 LTS 或移除策略。

