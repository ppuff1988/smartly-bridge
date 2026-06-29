# Smartly Bridge Migration Progress

> 日期：2026-06-29  
> 分支：`dev`  
> 目標：將 `main` 上的既有 entity-based 架構逐步遷移到六邊形架構與 logical-device / capability-based contract。  
> 原則：所有 runtime 行為變更以 TDD slice 推進，並保留 legacy endpoint 相容性。

## Current Status

- `dev` 已建立 application/domain/adapter/view 分層，並以 ports 讓主要 sync、control、event use case 可以脫離 Home Assistant runtime 測試。
- `/api/smartly/sync/states` 已雙軌輸出既有 entity state 與 shadow `logical_devices`。
- `use_logical_devices` feature flag 可讓 sync states response 標記 logical-device read path，同時保留 legacy `states` 供 rollback。
- Canonical `SmartlyCommand` path 已可解析 logical device capability target，並映射回 Home Assistant service call。
- SmartlyCommand success response 已保留 legacy top-level 欄位，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位。
- SmartlyCommand error response 已保留 legacy `error`，並同步輸出 API vNext `schema_version`、`data`、`warnings`、`errors[]` envelope 欄位。
- Device event ingestion 已輸出 canonical `button_event` envelope，支援去重與多種來源 action alias。
- Legacy control body 與既有 endpoint 仍保留，尚未進入 legacy cleanup。

## Recording Rule

- 每個重構 slice 都要依完成順序追加到 `Chronological Refactor Log`。
- 若 slice 有 runtime 行為變更，紀錄需包含 TDD RED/GREEN/verification 摘要。
- `Completed Slices` 保留為依功能區分的總覽，不取代依序紀錄。

## Chronological Refactor Log

| Order | Commit | Slice | Verification |
|---:|---|---|---|
| 1 | `0841be1` | 建立 flexible bridge architecture specs：總體架構、Device Abstraction、Capability Contracts、Adapter Contract、Presentation Contract、API vNext、Migration Plan | Docs only |
| 2 | `cf27b15` | 修正 devcontainer workspace 權限：改以 `vscode` user 執行，避免 host/container 權限衝突 | Devcontainer rebuild verified |
| 3 | `912b21c` | 建立 canonical capability migration 基礎：application/domain/ports 與初始 logical-device contracts | TDD application tests |
| 4 | `62f618d` | 依 source device ID group sibling entities 成單一 logical device | TDD sync/logical tests |
| 5 | `564c8c4` | 新增 canonical `SmartlyCommand` dispatcher，將 logical command 映射到 source entity | TDD control tests |
| 6 | `2dd37ac` | SmartlyCommand response 回傳 expected state，支援 command/state correlation | TDD control tests |
| 7 | `edb4a68` | 標準化 SmartlyCommand 錯誤 response | TDD control tests |
| 8 | `3b54b65` | Device event ingestion 回傳 canonical event envelope | TDD event tests |
| 9 | `42e0c61` | Canonical device event 去重，避免重複觸發 automation | TDD event tests |
| 10 | `e47050c` | logical device 輸出 Home Assistant entity alias | TDD sync tests |
| 11 | `040f769` | sync response 回報 normalization warnings | TDD sync tests |
| 12 | `adf268c` | color temperature constraints 由 mired metadata 正規化成 kelvin constraints | TDD logical-device tests |
| 13 | `59380db` | RGB color state 正規化成 canonical `{r,g,b}` contract | TDD logical-device tests |
| 14 | `69261c1` | signal quality 正規化成 percent 並保留 raw metric | TDD logical-device tests |
| 15 | `dc3da2c` | SmartlyCommand 拒絕 capability 不支援的 command | TDD control tests |
| 16 | `4e37faf` | SmartlyCommand params schema validation | TDD control tests |
| 17 | `1380499` | cover position canonical command 映射到 Home Assistant cover services | TDD control tests |
| 18 | `d5e802e` | fan speed canonical command 映射到 percentage / preset source services | TDD control tests |
| 19 | `e95d7ee` | fan speed state 正規化 percentage / preset mode | TDD logical-device tests |
| 20 | `824a555` | cover position state 正規化成 percent contract | TDD logical-device tests |
| 21 | `9ea1854` | lock state 與 lock/unlock command expected state | TDD logical/control tests |
| 22 | `53ac6c0` | climate HVAC mode 正規化成 `mode_select` | TDD logical/control tests |
| 23 | `f6daf58` | climate target temperature state/control contract | TDD logical/control tests |
| 24 | `f04b742` | scene/script `run` capability 與 command mapping | TDD logical/control tests |
| 25 | `0451e08` | climate fan modes 正規化成 `fan_speed` | TDD logical/control tests |
| 26 | `58ba900` | air quality measurements 正規化 | TDD logical-device tests |
| 27 | `3d8e865` | binary sensor states 正規化 presence/open-close 等 contracts | TDD logical-device tests |
| 28 | `0ec3497` | electrical measurements 正規化 current/voltage/power/energy | TDD logical-device tests |
| 29 | `844495c` | light effect metadata/state/control contract | TDD logical/control tests |
| 30 | `c02479b` | legacy cover `stop` 合併到 canonical `position` commands | TDD logical-device tests |
| 31 | `5e569e5` | cover tilt position state/control contract | TDD logical/control tests |
| 32 | `87723a4` | climate preset mode state/control contract | TDD logical/control tests |
| 33 | `0aff83a` | climate swing mode state/control contract | TDD logical/control tests |
| 34 | `e3583fc` | climate target temperature range state/control contract | TDD logical/control tests |
| 35 | `a1e6818` | fan direction state/control contract | TDD logical/control tests |
| 36 | `03abb58` | fan oscillation state/control contract | TDD logical/control tests |
| 37 | `3b48f87` | HS color fallback 正規化成 canonical RGB state | RED failed with `{}` state; full suite `515 passed` |
| 38 | `ddac6bb` | XY color fallback 正規化成 canonical RGB state | RED failed with `{}` state; full suite `516 passed` |
| 39 | `74fc92c` | brightness delta commands：`increase_brightness` / `decrease_brightness` 映射 `brightness_step_pct` | RED failed as `command_not_supported`; full suite `518 passed` |
| 40 | `ed729a1` | rotary button events：`rotate_left/right` 正規化成 canonical button events | RED failed as `invalid_action`; full suite `519 passed` |
| 41 | `3347735` | button action alias formats：`left_single`、`1_single` 正規化成 `single_press`，HTTP ingestion 使用同一 parser validation | RED failed as `invalid_action`; full suite `522 passed` |
| 42 | `4527bd5` | `use_logical_devices` read-path feature flag：sync states response 加上 logical `read_path`、`devices`、`device_count`，但保留 legacy `states` | RED failed with missing constructor flag / missing `read_path`; full suite `525 passed` |
| 43 | `df54f35` | SmartlyCommand error response 補上 API vNext `errors[]` structured error，同時保留 legacy `error` 相容欄位 | RED failed with missing `errors`; affected tests `106 passed`; full suite `526 passed` |
| 44 | `a073269` | SmartlyCommand success response 補上 API vNext `schema_version`、`data`、`warnings`、`errors` envelope 欄位，同時保留 legacy top-level 欄位 | RED failed with missing `schema_version`; affected tests `107 passed`; full suite `527 passed` |
| 45 | current slice | SmartlyCommand error response 補上 API vNext `schema_version`、`data`、`warnings` envelope 欄位，同時保留 legacy top-level error 欄位 | RED failed with missing `schema_version`; affected tests `108 passed`; full suite `528 passed` |

## Completed Slices

| Area | Done | Evidence |
|---|---|---|
| Architecture specs | 新增總體架構、Device Abstraction、Capability Contracts、Adapter Contract、Presentation Contract、API vNext、Migration Plan | `0841be1` |
| Devcontainer permissions | devcontainer workspace 改以 `vscode` user 執行，避免 host/container 權限互相衝突 | `cf27b15` |
| Hexagonal application base | 建立 canonical capability migration 基礎 use cases 與 application ports | `912b21c` |
| Logical device grouping | 以 Home Assistant source device ID 將 sibling entities group 成同一 logical device | `62f618d` |
| Command path | 新增 canonical `SmartlyCommand` dispatcher、target resolver、expected state、standard error shape，並為 command success/error 補上 API vNext envelope/error fields | `564c8c4`, `2dd37ac`, `edb4a68`, `df54f35`, `a073269`, current slice |
| Event path | 新增 canonical event envelope 與 event deduplication | `3b54b65`, `42e0c61` |
| Sync aliases, warnings, and read path | logical devices 輸出 migration aliases、normalization warnings，並支援 `use_logical_devices` read-path flag | `e47050c`, `040f769`, `4527bd5` |
| Light capabilities | 色溫 constraints、RGB contract、effects、HS/XY color fallback、brightness delta commands | `adf268c`, `59380db`, `844495c`, `3b48f87`, `ddac6bb`, `74fc92c` |
| Sensors | signal quality、air quality、binary sensor、electrical measurements normalization | `69261c1`, `58ba900`, `3d8e865`, `0ec3497` |
| Cover | position、stop merge、tilt position control | `824a555`, `c02479b`, `5e569e5` |
| Fan | fan speed state/control、direction、oscillation | `e95d7ee`, `d5e802e`, `a1e6818`, `03abb58` |
| Climate | mode select、target temperature、fan modes、preset mode、swing mode、temperature range | `53ac6c0`, `f6daf58`, `0451e08`, `87723a4`, `0aff83a`, `e3583fc` |
| Scene/script | scene/script `run` capability and command mapping | `f04b742` |
| Lock | lock state and command expected-state contract | `9ea1854` |
| Button events | rotary `rotate_left/right` normalization; source alias formats such as `left_single` and `1_single` normalize to canonical `single_press` | `ed729a1`, `3347735` |

## Latest Verification

- Targeted command error vNext envelope test: `1 passed`
- Affected command/application tests: `108 passed`
- Full suite: `528 passed`

## Remaining Work

- Finish a requirement-by-requirement audit against `migration-plan.md`, `api-vnext-contract.md`, and `capability-contracts.md`.
- Add stronger fixture coverage for current-sync snapshots and API vNext contract snapshots.
- Continue API vNext envelope migration for endpoints beyond SmartlyCommand command responses.
- Decide whether editable sibling `number` / `select` setting controls should remain presentation-only or become canonical command capabilities.
- Continue filling P0 command mapping and event automation gaps before Platform read/write path cutover.
- Do not start Phase 6 legacy cleanup until legacy endpoint usage and rollback requirements are proven.
